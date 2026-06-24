"""Orchestrate dikw-core retrieval/synth evaluation over dikw-data datasets.

This is the thin wrapper specified in ``docs/dikw-eval-plan.md`` (Part I §1.4). It
hands datasets to a read-only ``dikw-core`` engine by absolute path, captures each
``dikw client eval`` NDJSON report under ``reports/``, and rolls the run up into a
``summary.json`` whose exit code CI can gate on.

Secrets come from ``.env.eval`` (loaded in-process, never printed). No API calls are
made in ``--dry-run``; that mode validates datasets, checks that the required key
*names* are populated, and prints the exact commands it would run.

Usage:
    uv run python scripts/run_eval.py --dry-run
    uv run python scripts/run_eval.py --datasets synthetic-diverse-v2 --retrieval all
    uv run python scripts/run_eval.py --mode serve --server http://127.0.0.1:8765
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _candidate in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    _entry = str(_candidate)
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from dikw_data.config import load_dotenv  # noqa: E402
from scripts.validate_dataset import validate  # noqa: E402

DIKW_LAUNCH: tuple[str, ...] = ("uv", "run", "dikw")
DEFAULT_REQUIRED_KEYS: tuple[str, ...] = ("MINIMAX_API_KEY", "GITEE_API_KEY")
DEFAULT_ENV_EVAL = PROJECT_ROOT / ".env.eval"
DEFAULT_BASE = PROJECT_ROOT / "bases" / "eval-base"
DEFAULT_BASE_TEMPLATE = PROJECT_ROOT / "configs" / "eval-base.dikw.yml"
DEFAULT_DATASETS_DIR = PROJECT_ROOT / "datasets"
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports"


# --- pure helpers (unit-tested) --------------------------------------------


def build_eval_command(
    *,
    dataset: Path,
    base: Path,
    mode: str = "serve-and-run",
    retrieval: str = "hybrid",
    eval_modes: list[str] | None = None,
    cache: str = "read_write",
    server: str | None = None,
    judge: bool = False,
    judge_sample: str | None = None,
    against: Path | None = None,
    write_baseline: Path | None = None,
    tolerance: float | None = None,
    pretty: bool = False,
    launch: tuple[str, ...] = DIKW_LAUNCH,
) -> list[str]:
    """Build the argv for one ``dikw client eval`` invocation.

    ``serve-and-run`` wraps the eval in a one-shot server; ``serve`` targets an
    already-running server (optionally via ``--server``). Returns a plain list so
    callers can print it (dry-run) or hand it to ``subprocess``.
    """
    if mode not in ("serve-and-run", "serve"):
        raise ValueError(f"unknown mode: {mode!r} (expected 'serve-and-run' or 'serve')")
    if against is not None and write_baseline is not None:
        raise ValueError("--against and --write-baseline are mutually exclusive")

    eval_args = ["eval", "--dataset", str(dataset), "--retrieval", retrieval]
    for mode_name in eval_modes or ["retrieval"]:
        eval_args += ["--eval", mode_name]
    # --plain disables the rich progress widget, whose ANSI bytes otherwise pollute
    # stdout and make the captured NDJSON (and thus parse_eval_report) unparseable.
    eval_args += ["--cache", cache, "--wait", "--plain"]
    if judge:
        eval_args.append("--judge")
        if judge_sample:
            eval_args += ["--judge-sample", judge_sample]
    if against is not None:
        eval_args += ["--against", str(against)]
    if write_baseline is not None:
        eval_args += ["--write-baseline", str(write_baseline)]
    if tolerance is not None:
        eval_args += ["--tolerance", f"{tolerance:g}"]
    if pretty:
        eval_args.append("--pretty")

    client = list(launch) + ["client"]
    if mode == "serve-and-run":
        return client + ["serve-and-run", "--base", str(base), "--"] + eval_args
    cmd = client + eval_args
    if server:
        cmd += ["--server", server]
    return cmd


def parse_eval_report(text: str) -> dict:
    """Return the last EvalReport-shaped JSON object in an NDJSON stream, or {}."""
    report: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(obj, dict) and "metrics" in obj and ("passed" in obj or "thresholds" in obj):
            report = obj
    return report


def worst_exit_code(codes: list[int]) -> int:
    """Aggregate per-run exit codes: 2 (bad spec) > 1 (regression) > 0 (pass)."""
    codes = list(codes)
    if not codes:
        return 0
    if 2 in codes:
        return 2
    if any(code != 0 for code in codes):
        return 1
    return 0


def missing_keys(env_values: dict[str, str], required: list[str]) -> list[str]:
    """Names in ``required`` that are absent or empty in ``env_values``."""
    return [key for key in required if not env_values.get(key)]


def resolve_datasets(datasets_dir: Path, names: list[str] | None) -> list[Path]:
    """Resolve dataset packages to absolute paths.

    With ``names``: each is treated as an absolute/relative path if it exists,
    otherwise as a name under ``datasets_dir``. Without ``names``: discover every
    subdirectory of ``datasets_dir`` that carries a ``dataset.yaml``.
    """
    datasets_dir = Path(datasets_dir)
    if names:
        resolved: list[Path] = []
        for name in names:
            path = Path(name)
            if not path.is_absolute():
                candidate = datasets_dir / name
                if candidate.exists():
                    path = candidate
            resolved.append(path.resolve())
        return resolved
    if not datasets_dir.is_dir():
        return []
    return [
        child.resolve()
        for child in sorted(datasets_dir.iterdir())
        if (child / "dataset.yaml").is_file()
    ]


def merge_env(base_env: dict[str, str], overrides: dict[str, str]) -> dict[str, str]:
    """Overlay non-empty secret values onto a base environment for child processes.

    The dikw-core server reads provider keys straight from ``os.environ`` (e.g.
    ``GITEE_API_KEY``) and ``serve-and-run`` forwards the parent environment to the
    server it spawns. We never export ``.env.eval`` globally; instead we hand the
    loaded values to each eval subprocess via its ``env=``. Empty values are dropped
    so a blank line in ``.env.eval`` can't shadow a real key already in the env.
    """
    merged = dict(base_env)
    merged.update({key: value for key, value in overrides.items() if value})
    return merged


def summarize(rows: list[dict]) -> dict:
    """Roll per-(dataset, mode) results into a single gate-able summary.

    Pass/fail counts follow the *exit code*, not ``report.passed``: the exit code is
    the authoritative gate result (0 pass / 1 regression or threshold-fail / 2
    bad-spec). ``--against`` trips the exit code to 1 on a regression without flipping
    the report's own ``passed`` flag (which reflects only the dataset's thresholds), so
    counting by ``report.passed`` would disagree with ``worst_exit_code``.
    """
    codes = [row["exit_code"] for row in rows]
    passed = sum(1 for row in rows if row["exit_code"] == 0)
    failed = len(rows) - passed
    worst = worst_exit_code(codes)
    return {
        "worst_exit_code": worst,
        "passed": worst == 0,
        "counts": {"total": len(rows), "passed": passed, "failed": failed},
        "results": rows,
    }


# --- side-effecting orchestration ------------------------------------------


def ensure_base(base: Path, template: Path, *, launch: tuple[str, ...] = DIKW_LAUNCH) -> None:
    """Materialise the eval base if absent: ``dikw init`` then drop our template."""
    base = Path(base)
    config_path = base / "dikw.yml"
    if config_path.is_file():
        return
    base.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([*launch, "init", str(base)], check=True)
    template = Path(template)
    if template.is_file():
        config_path.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run dikw-core eval over dikw-data datasets.")
    parser.add_argument("--datasets", help="Comma-separated dataset names or paths (default: all under datasets/).")
    parser.add_argument("--retrieval", default="hybrid", choices=["hybrid", "bm25", "vector", "all"])
    parser.add_argument("--eval", dest="eval_modes", action="append", choices=["retrieval", "synth"],
                        help="Eval family (repeatable). Default: retrieval.")
    parser.add_argument("--cache", default="read_write", choices=["read_write", "rebuild", "off"])
    parser.add_argument("--mode", default="serve-and-run", choices=["serve-and-run", "serve"])
    parser.add_argument("--server", help="Server URL for --mode serve (default: dikw's own default).")
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--judge-sample", dest="judge_sample")
    parser.add_argument("--against", type=Path)
    parser.add_argument("--write-baseline", dest="write_baseline", type=Path)
    parser.add_argument("--tolerance", type=float)
    parser.add_argument("--base", type=Path, default=DEFAULT_BASE)
    parser.add_argument("--base-template", type=Path, default=DEFAULT_BASE_TEMPLATE)
    parser.add_argument("--datasets-dir", type=Path, default=DEFAULT_DATASETS_DIR)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV_EVAL)
    parser.add_argument("--out", type=Path, help="Report directory (default: reports/<UTC-ts>).")
    parser.add_argument("--skip-validate", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Print plan; no base, no API, no spend.")
    args = parser.parse_args(argv)

    names = [n.strip() for n in args.datasets.split(",") if n.strip()] if args.datasets else None
    datasets = resolve_datasets(args.datasets_dir, names)
    if not datasets:
        print(f"ERROR: no datasets found (datasets-dir={args.datasets_dir}, names={names})")
        return 2

    # Shape gate before any spend.
    if not args.skip_validate:
        had_errors = False
        for dataset in datasets:
            errors = validate(dataset)
            if errors:
                had_errors = True
                print(f"ERROR: {dataset.name} failed validation:")
                for error in errors:
                    print(f"  - {error}")
        if had_errors:
            return 2

    # Secrets check (names only; values never printed).
    env_values = load_dotenv(args.env_file)
    absent = missing_keys(env_values, list(DEFAULT_REQUIRED_KEYS))
    if absent:
        message = f"missing required keys in {args.env_file}: {', '.join(absent)}"
        if args.dry_run:
            print(f"WARN: {message}")
        else:
            print(f"ERROR: {message}")
            return 2

    eval_modes = args.eval_modes or ["retrieval"]
    commands = []
    for dataset in datasets:
        commands.append(
            (
                dataset,
                build_eval_command(
                    dataset=dataset,
                    base=args.base,
                    mode=args.mode,
                    retrieval=args.retrieval,
                    eval_modes=eval_modes,
                    cache=args.cache,
                    server=args.server,
                    judge=args.judge,
                    judge_sample=args.judge_sample,
                    against=args.against,
                    write_baseline=args.write_baseline,
                    tolerance=args.tolerance,
                ),
            )
        )

    if args.dry_run:
        print(f"# dry-run: {len(commands)} dataset(s), retrieval={args.retrieval}, eval={','.join(eval_modes)}")
        for dataset, command in commands:
            print(f"# {dataset.name}")
            print("  " + " ".join(command))
        return 0

    out_dir = args.out or (DEFAULT_REPORTS_DIR / _utc_stamp())
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.mode == "serve-and-run":
        ensure_base(args.base, args.base_template)

    # dikw-core reads provider keys from the process environment; inject the loaded
    # .env.eval values into each child's env (never exported globally, never printed).
    run_env = merge_env(dict(os.environ), env_values)

    rows: list[dict] = []
    for dataset, command in commands:
        label = f"{dataset.name}__{args.retrieval}"
        print(f"==> {label}: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, env=run_env)
        report_path = out_dir / f"{label}.ndjson"
        report_path.write_text(result.stdout, encoding="utf-8")
        if result.stderr:
            (out_dir / f"{label}.stderr.txt").write_text(result.stderr, encoding="utf-8")
        report = parse_eval_report(result.stdout)
        rows.append(
            {
                "dataset": dataset.name,
                "mode": args.retrieval,
                "exit_code": result.returncode,
                "report_path": str(report_path),
                "report": report,
            }
        )
        print(f"    exit={result.returncode} passed={report.get('passed')}")

    summary = summarize(rows)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"summary: {summary['counts']} -> {out_dir / 'summary.json'}")
    return summary["worst_exit_code"]


if __name__ == "__main__":
    sys.exit(main())

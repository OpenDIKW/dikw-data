"""Retrieval-config ablation harness (rrf_k / weights / fusion / rerank sweep).

The snapshot cache bakes ``RetrievalConfig`` at first ingest and reloads the
*stale* baked config on a cache hit (dikw-core#250), so a config sweep under
``--cache read_write`` silently re-reports the first variant's numbers. This
harness therefore **forces ``--cache off``** for every variant — the documented
#250 workaround — at the cost of a fresh embed per variant. When #250 lands,
flip ``FORCED_CACHE`` to ``"rebuild"`` (one fresh snapshot per variant without
re-embedding unrelated runs) and delete this note.

Retrieval config lives in the eval base's ``dikw.yml`` ``retrieval:`` block, not
on the eval CLI, so each variant runs against a temp base carrying its overrides.

Pure helpers (override-merge, label, table) are unit-tested; the run loop shells
out to ``dikw client eval`` via ``run_eval``'s command builder.

Usage:
    uv run python scripts/ablate_retrieval.py --dataset domain-bilingual-v1 \\
        --variants '[{"rrf_k": 30}, {"rrf_k": 60}, {"rrf_k": 90}]' --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for _candidate in (PROJECT_ROOT, PROJECT_ROOT / "src"):
    _entry = str(_candidate)
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from scripts.run_eval import (  # noqa: E402
    DEFAULT_BASE_TEMPLATE,
    build_eval_command,
    ensure_base,
    merge_env,
    parse_eval_report,
)

from dikw_data.config import load_dotenv  # noqa: E402

# dikw-core#250 workaround. The cache key omits RetrievalConfig, so only a fresh
# snapshot reflects a changed retrieval block. Flip to "rebuild" once #250 ships.
FORCED_CACHE = "off"

DEFAULT_METRIC_KEYS: tuple[str, ...] = (
    "hit_at_3",
    "hit_at_10",
    "mrr",
    "ndcg_at_10",
    "recall_at_100",
)
DEFAULT_ENV = PROJECT_ROOT / ".env"
DEFAULT_REQUIRED_KEYS: tuple[str, ...] = ("MINIMAX_API_KEY", "GITEE_API_KEY")


# --- pure helpers (unit-tested) --------------------------------------------


def apply_retrieval_overrides(base_yaml: str, overrides: dict[str, Any]) -> str:
    """Merge ``overrides`` into the base ``dikw.yml``'s ``retrieval:`` block.

    Keys present in ``overrides`` replace (or add) entries under ``retrieval``;
    every other block (``provider``, ``storage``, …) is preserved verbatim. An
    empty override returns an equivalent document (round-tripped through yaml).
    """
    doc = yaml.safe_load(base_yaml) or {}
    if not isinstance(doc, dict):
        raise ValueError("base dikw.yml is not a mapping")
    retrieval = dict(doc.get("retrieval") or {})
    retrieval.update(overrides)
    doc["retrieval"] = retrieval
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def variant_label(overrides: dict[str, Any]) -> str:
    """Stable, filesystem-safe label for an override set, e.g. ``rrf_k=60``.

    Empty overrides label as ``baseline`` (the template's own retrieval config).
    """
    if not overrides:
        return "baseline"
    return ",".join(f"{k}={overrides[k]}" for k in sorted(overrides))


def metrics_table(rows: list[dict[str, Any]], metric_keys: tuple[str, ...] = DEFAULT_METRIC_KEYS) -> str:
    """Markdown comparison table, one row per variant.

    Each ``rows`` item is ``{"label": str, "exit_code": int, "metrics": {...}}``.
    Missing metrics render as ``-`` so a partial sweep is still readable.
    """
    head = "| variant | exit | " + " | ".join(metric_keys) + " |"
    sep = "|" + "---|" * (2 + len(metric_keys))
    lines = [head, sep]
    for row in rows:
        metrics = row.get("metrics") or {}
        cells = " | ".join(
            f"{metrics[k]:.3f}" if isinstance(metrics.get(k), (int, float)) else "-"
            for k in metric_keys
        )
        lines.append(f"| {row['label']} | {row.get('exit_code', '')} | {cells} |")
    return "\n".join(lines)


def parse_variants(spec: str) -> list[dict[str, Any]]:
    """Parse a ``--variants`` JSON list of override dicts (validates shape)."""
    parsed = json.loads(spec)
    if not isinstance(parsed, list) or not all(isinstance(v, dict) for v in parsed):
        raise ValueError("--variants must be a JSON list of objects")
    return parsed


# --- side-effecting orchestration ------------------------------------------


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def run_variant(
    *,
    dataset: Path,
    overrides: dict[str, Any],
    base_template_text: str,
    work_dir: Path,
    retrieval: str,
    run_env: dict[str, str],
) -> dict[str, Any]:
    """Materialise a temp base with ``overrides`` and run one eval (cache forced
    off). Returns ``{"label", "exit_code", "metrics", "report_path"}``."""
    label = variant_label(overrides)
    variant_yaml = apply_retrieval_overrides(base_template_text, overrides)
    template_path = work_dir / f"{label}.dikw.yml"
    template_path.write_text(variant_yaml, encoding="utf-8")
    base_dir = work_dir / f"base-{label}"
    ensure_base(base_dir, template_path)
    command = build_eval_command(
        dataset=dataset,
        base=base_dir,
        mode="serve-and-run",
        retrieval=retrieval,
        cache=FORCED_CACHE,
    )
    result = subprocess.run(command, capture_output=True, text=True, env=run_env)
    report_path = work_dir / f"{label}.ndjson"
    report_path.write_text(result.stdout, encoding="utf-8")
    report = parse_eval_report(result.stdout)
    return {
        "label": label,
        "overrides": overrides,
        "exit_code": result.returncode,
        "metrics": report.get("metrics", {}),
        "report_path": str(report_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", required=True, help="dataset name (under datasets/) or absolute path")
    parser.add_argument("--variants", required=True, help='JSON list of retrieval-override dicts, e.g. \'[{"rrf_k":30}]\'')
    parser.add_argument("--retrieval", default="hybrid", choices=["hybrid", "bm25", "vector", "all"])
    parser.add_argument("--base-template", type=Path, default=DEFAULT_BASE_TEMPLATE)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--out", type=Path, help="work dir (default: reports/<UTC-ts>-ablation)")
    parser.add_argument("--dry-run", action="store_true", help="print variants + commands; no base, no API, no spend")
    args = parser.parse_args(argv)

    variants = parse_variants(args.variants)
    dataset = Path(args.dataset)
    if not dataset.is_absolute():
        candidate = PROJECT_ROOT / "datasets" / args.dataset
        dataset = candidate.resolve() if candidate.exists() else dataset.resolve()
    base_template_text = Path(args.base_template).read_text(encoding="utf-8")

    if args.dry_run:
        print(f"# dry-run: {len(variants)} variant(s) over {dataset.name}, cache FORCED {FORCED_CACHE} (#250)")
        for overrides in variants:
            label = variant_label(overrides)
            cmd = build_eval_command(
                dataset=dataset, base=PROJECT_ROOT / "bases" / f"ablation-{label}",
                retrieval=args.retrieval, cache=FORCED_CACHE,
            )
            print(f"# {label}: retrieval overrides = {overrides}")
            print("  " + " ".join(cmd))
        return 0

    env_values = load_dotenv(args.env_file)
    absent = [k for k in DEFAULT_REQUIRED_KEYS if not env_values.get(k)]
    if absent:
        print(f"ERROR: missing required keys in {args.env_file}: {', '.join(absent)}")
        return 2
    run_env = merge_env(dict(os.environ), env_values)

    work_dir = args.out or (PROJECT_ROOT / "reports" / f"{_utc_stamp()}-ablation")
    work_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for overrides in variants:
        row = run_variant(
            dataset=dataset, overrides=overrides, base_template_text=base_template_text,
            work_dir=work_dir, retrieval=args.retrieval, run_env=run_env,
        )
        print(f"==> {row['label']}: exit={row['exit_code']}")
        rows.append(row)

    table = metrics_table(rows)
    (work_dir / "ablation.md").write_text(table + "\n", encoding="utf-8")
    (work_dir / "ablation.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(table)
    print(f"\nwrote {work_dir / 'ablation.md'}")
    return 0 if all(r["exit_code"] == 0 for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())

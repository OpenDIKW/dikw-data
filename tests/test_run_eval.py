from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_eval import (
    build_eval_command,
    merge_env,
    missing_keys,
    parse_eval_report,
    resolve_datasets,
    summarize,
    worst_exit_code,
)


def test_build_serve_and_run_command_basic() -> None:
    cmd = build_eval_command(
        dataset=Path("/abs/ds"),
        base=Path("bases/eval-base"),
        mode="serve-and-run",
        retrieval="all",
        eval_modes=["retrieval"],
        cache="read_write",
    )
    assert cmd[:5] == ["uv", "run", "dikw", "client", "serve-and-run"]
    assert cmd[cmd.index("--base") + 1] == "bases/eval-base"
    inner = cmd[cmd.index("--") + 1 :]
    assert inner[0] == "eval"
    assert inner[inner.index("--dataset") + 1] == "/abs/ds"
    assert inner[inner.index("--retrieval") + 1] == "all"
    assert inner[inner.index("--eval") + 1] == "retrieval"
    assert inner[inner.index("--cache") + 1] == "read_write"
    assert "--wait" in inner
    assert "--plain" in inner  # progress widget off -> clean NDJSON on stdout
    assert "--pretty" not in inner  # default is NDJSON


def test_build_serve_mode_uses_server_and_no_separator() -> None:
    cmd = build_eval_command(
        dataset=Path("/abs/ds"),
        base=Path("b"),
        mode="serve",
        server="http://127.0.0.1:8765",
        retrieval="hybrid",
        eval_modes=["retrieval"],
    )
    assert "serve-and-run" not in cmd
    assert cmd[:5] == ["uv", "run", "dikw", "client", "eval"]
    assert cmd[cmd.index("--server") + 1] == "http://127.0.0.1:8765"
    assert "--" not in cmd


def test_build_multiple_eval_modes_and_gate_flags() -> None:
    cmd = build_eval_command(
        dataset=Path("/abs/ds"),
        base=Path("b"),
        mode="serve-and-run",
        eval_modes=["retrieval", "synth"],
        judge=True,
        judge_sample="auto",
        against=Path("base.json"),
        tolerance=0.05,
    )
    inner = cmd[cmd.index("--") + 1 :]
    assert inner.count("--eval") == 2
    assert "--judge" in inner
    assert inner[inner.index("--judge-sample") + 1] == "auto"
    assert inner[inner.index("--against") + 1] == "base.json"
    assert inner[inner.index("--tolerance") + 1] == "0.05"


def test_against_and_write_baseline_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError):
        build_eval_command(
            dataset=Path("/d"),
            base=Path("b"),
            against=Path("a.json"),
            write_baseline=Path("w.json"),
        )


def test_unknown_mode_rejected() -> None:
    with pytest.raises(ValueError):
        build_eval_command(dataset=Path("/d"), base=Path("b"), mode="nope")


def test_worst_exit_code() -> None:
    assert worst_exit_code([]) == 0
    assert worst_exit_code([0, 0]) == 0
    assert worst_exit_code([0, 1]) == 1
    assert worst_exit_code([1, 2]) == 2
    assert worst_exit_code([0, 2, 1]) == 2


def test_missing_keys() -> None:
    assert missing_keys({"A": "x", "B": ""}, ["A", "B", "C"]) == ["B", "C"]
    assert missing_keys({"A": "x"}, ["A"]) == []


def test_merge_env_overlays_nonempty_secrets() -> None:
    base = {"PATH": "/usr/bin", "GITEE_API_KEY": "stale"}
    merged = merge_env(base, {"GITEE_API_KEY": "fresh", "MINIMAX_API_KEY": "m", "EMPTY": ""})
    assert merged["GITEE_API_KEY"] == "fresh"  # non-empty override wins
    assert merged["MINIMAX_API_KEY"] == "m"  # new key added
    assert merged["PATH"] == "/usr/bin"  # base preserved
    assert "EMPTY" not in merged  # blank value never shadows
    assert "GITEE_API_KEY" not in base or base["GITEE_API_KEY"] == "stale"  # base not mutated


def test_parse_eval_report_picks_last_report_line() -> None:
    ndjson = "\n".join(
        [
            '{"event":"progress","msg":"ingesting"}',
            '{"dataset_name":"mvp","metrics":{"hit_at_3":0.8},'
            '"thresholds":{"hit_at_3":0.7},"passed":true}',
        ]
    )
    rep = parse_eval_report(ndjson)
    assert rep["dataset_name"] == "mvp"
    assert rep["metrics"]["hit_at_3"] == 0.8
    assert rep["passed"] is True


def test_parse_eval_report_handles_no_report() -> None:
    assert parse_eval_report('{"event":"x"}\nnot json\n') == {}


def test_resolve_datasets_by_name(tmp_path: Path) -> None:
    ds = tmp_path / "datasets" / "foo"
    ds.mkdir(parents=True)
    (ds / "dataset.yaml").write_text("name: foo\n", encoding="utf-8")
    assert resolve_datasets(tmp_path / "datasets", ["foo"]) == [ds.resolve()]


def test_resolve_datasets_discovery_skips_dirs_without_manifest(tmp_path: Path) -> None:
    root = tmp_path / "datasets"
    for name in ("a", "b"):
        (root / name).mkdir(parents=True)
        (root / name / "dataset.yaml").write_text(f"name: {name}\n", encoding="utf-8")
    (root / "notds").mkdir(parents=True)  # no dataset.yaml -> skipped
    assert [p.name for p in resolve_datasets(root, None)] == ["a", "b"]


def test_resolve_datasets_absolute_path_passthrough(tmp_path: Path) -> None:
    ds = tmp_path / "somewhere"
    ds.mkdir()
    (ds / "dataset.yaml").write_text("name: x\n", encoding="utf-8")
    assert resolve_datasets(tmp_path / "datasets", [str(ds)]) == [ds.resolve()]


def test_summarize_rolls_up_pass_fail() -> None:
    rows = [
        {"dataset": "a", "mode": "retrieval", "exit_code": 0,
         "report": {"passed": True, "metrics": {"hit_at_3": 0.9}}},
        {"dataset": "b", "mode": "retrieval", "exit_code": 1,
         "report": {"passed": False, "metrics": {"hit_at_3": 0.4}}},
    ]
    summary = summarize(rows)
    assert summary["worst_exit_code"] == 1
    assert summary["passed"] is False
    assert summary["counts"] == {"total": 2, "passed": 1, "failed": 1}
    assert summary["results"][0]["dataset"] == "a"


def test_summarize_counts_by_exit_code_not_report_passed() -> None:
    # --against regression: exit 1 but the dataset's own thresholds still "passed".
    rows = [
        {"dataset": "a", "mode": "retrieval", "exit_code": 1,
         "report": {"passed": True, "metrics": {"hit_at_3": 1.0}}},
    ]
    summary = summarize(rows)
    assert summary["worst_exit_code"] == 1
    assert summary["passed"] is False
    assert summary["counts"] == {"total": 1, "passed": 0, "failed": 1}  # exit code wins

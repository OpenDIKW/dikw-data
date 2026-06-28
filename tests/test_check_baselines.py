"""Unit tests for the pure baseline-content check behind eval-gate.yml."""

from __future__ import annotations

from tools.check_baselines import check_baseline_addition

# A well-formed new entry: dated header + a retrieval metric on the added lines.
GOOD_ENTRY = [
    "## 2026-06-25 — scifact + cmteb anchor calibration",
    "",
    "dikw-core v0.6.1, MiniMax+Gitee, --retrieval all.",
    "scifact: ndcg_at_10 0.67, hit_at_3 0.71, recall_at_100 0.92.",
]


def test_passes_with_new_dated_entry_and_metric():
    assert (
        check_baseline_addition(
            GOOD_ENTRY, existing_headers=set(), touches_datasets=True
        )
        == []
    )


def test_noop_when_datasets_untouched():
    # No dataset change → the gate does not apply, even with no entry at all.
    assert (
        check_baseline_addition([], existing_headers=set(), touches_datasets=False)
        == []
    )


def test_fails_without_new_header():
    violations = check_baseline_addition(
        ["Tweaked some prose, ndcg_at_10 still 0.67."],
        existing_headers=set(),
        touches_datasets=True,
    )
    assert any("no NEW dated/versioned entry header" in v for v in violations)


def test_fails_when_header_is_reused():
    header = "## 2026-06-25 — scifact + cmteb anchor calibration"
    # Header already exists at base → not a genuinely new entry.
    violations = check_baseline_addition(
        [header, "ndcg_at_10 0.67"],
        existing_headers={header},
        touches_datasets=True,
    )
    assert any("no NEW dated/versioned entry header" in v for v in violations)


def test_fails_without_retrieval_metric():
    violations = check_baseline_addition(
        ["## 2026-06-25 — new dataset", "", "Added a corpus, looks good."],
        existing_headers=set(),
        touches_datasets=True,
    )
    assert any("names no" in v and "retrieval metric" in v for v in violations)


def test_subsection_header_does_not_count_as_entry():
    # `### ` is a sub-section, not a top-level dated entry.
    violations = check_baseline_addition(
        ["### 2026-06-25 details", "ndcg_at_10 0.67"],
        existing_headers=set(),
        touches_datasets=True,
    )
    assert any("no NEW dated/versioned entry header" in v for v in violations)

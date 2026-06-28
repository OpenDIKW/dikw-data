"""Unit tests for the pos-vs-neg relevance-score separation tool.

Two schemas are exercised: the current diagnostic-only rows (no scores → graceful
degrade) and the post-#249 rows that carry a score field (under any probed name).
"""

from __future__ import annotations

import json

import pytest
from tools.negatives_separation import (
    eval_report,
    expect_none_satisfaction,
    separation,
    top1_score,
)

# Pre-#249: rows carry only q / ranked / expect_any (no score anywhere).
PRE_POS = [
    {"id": "zh-a", "expect_any": ["doc_a"], "ranked": ["doc_a", "x"]},
    {"id": "en-b", "expect_any": ["doc_b"], "ranked": ["doc_b", "y"]},
]
PRE_NEG = [
    {"q": "off-corpus quantum cooking", "ranked": ["doc_x", "doc_y"]},
    {"q": "off-corpus mars law", "ranked": ["doc_z"]},
]

# Post-#249: positives score high, negatives score low. Each side uses a
# *different* candidate key name to prove the probe is name-agnostic.
POST_POS = [
    {"id": "zh-a", "expect_any": ["doc_a"], "ranked": ["doc_a"], "scores": [0.81, 0.40]},
    {"id": "en-b", "expect_any": ["doc_b"], "ranked": ["doc_b"], "scores": [0.79, 0.31]},
]
POST_NEG = [
    {"q": "off-corpus a", "ranked": ["doc_x"], "top1_score": 0.22},
    {"q": "off-corpus b", "ranked": ["doc_y"], "top1_score": 0.18},
]


def test_top1_score_probes_names_and_ignores_missing():
    assert top1_score({"scores": [0.81, 0.4]}) == pytest.approx(0.81)
    assert top1_score({"ranked_scores": [0.5]}) == pytest.approx(0.5)
    assert top1_score({"top1_score": 0.22}) == pytest.approx(0.22)
    assert top1_score({"ranked": ["doc_a"]}) is None  # pre-#249 row
    assert top1_score({"scores": []}) is None  # empty list
    assert top1_score({"top1_score": True}) is None  # bool is not a score


def test_separation_degrades_without_scores():
    result = separation(PRE_POS, PRE_NEG)
    assert result["scores_available"] is False
    assert result["counts"] == {"positives": 2, "negatives": 2}
    assert result["negative_leaks_sample"][0]["top_stem"] == "doc_x"


def test_separation_with_scores_computes_margin():
    result = separation(POST_POS, POST_NEG)
    assert result["scores_available"] is True
    assert result["positive_top1"]["mean"] == pytest.approx(0.80)
    assert result["negative_top1"]["mean"] == pytest.approx(0.20)
    assert result["separation_margin"] == pytest.approx(0.60)
    # Default cutoff is the pos/neg midpoint (0.50); both negatives fall below it.
    assert result["cutoff"] == pytest.approx(0.50)
    assert result["expect_none_satisfaction"] == pytest.approx(1.0)


def test_expect_none_satisfaction_cutoff():
    assert expect_none_satisfaction(POST_NEG, cutoff=0.20) == pytest.approx(0.5)
    assert expect_none_satisfaction(POST_NEG, cutoff=0.10) == pytest.approx(0.0)
    assert expect_none_satisfaction(PRE_NEG, cutoff=0.5) is None  # no scores


def test_eval_report_picks_richest_report_line(tmp_path):
    path = tmp_path / "run.ndjson"
    lines = [
        {"event": "progress"},  # noise
        {"metrics": {"hit_at_3": 1.0}, "per_query": [POST_POS[0]], "negative_diagnostics": []},
        {"metrics": {"hit_at_3": 1.0}, "per_query": POST_POS, "negative_diagnostics": POST_NEG},
    ]
    path.write_text("\n".join(json.dumps(obj) for obj in lines), encoding="utf-8")
    report = eval_report(str(path))
    assert len(report["per_query"]) == 2
    assert len(report["negative_diagnostics"]) == 2

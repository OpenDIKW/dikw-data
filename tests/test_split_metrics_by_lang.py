"""Unit tests for the offline per-language metric splitter."""

from __future__ import annotations

import math

import pytest
from tools.split_metrics_by_lang import aggregate, lang_of, split_metrics

# Four queries; ranked lists place the gold stem at known ranks.
ROWS = [
    {"id": "zh-a", "expect_any": ["doc_a"], "ranked": ["doc_a", "x", "y"]},       # rank 1
    {"id": "zh-b", "expect_any": ["doc_b"], "ranked": ["x", "doc_b", "y"]},       # rank 2
    {"id": "en-c", "expect_any": ["doc_c"], "ranked": ["x", "y", "z", "doc_c"]},  # rank 4
    {"id": "en-d", "expect_any": ["doc_d"], "ranked": ["x", "y", "z"]},           # miss
]


def test_lang_of_prefix():
    assert lang_of("zh-a") == "zh"
    assert lang_of("en-c") == "en"
    assert lang_of("scifact_q1") == "other"


def test_zh_bucket_metrics():
    m = split_metrics(ROWS)["zh"]
    assert m["hit_at_3"] == pytest.approx(1.0)
    assert m["mrr"] == pytest.approx((1.0 + 0.5) / 2)
    assert m["ndcg_at_10"] == pytest.approx((1.0 + 1.0 / math.log2(3)) / 2)
    assert m["recall_at_100"] == pytest.approx(1.0)


def test_en_bucket_metrics():
    m = split_metrics(ROWS)["en"]
    assert m["hit_at_3"] == pytest.approx(0.0)
    assert m["hit_at_10"] == pytest.approx(0.5)
    assert m["mrr"] == pytest.approx((0.25 + 0.0) / 2)
    assert m["ndcg_at_10"] == pytest.approx((1.0 / math.log2(5) + 0.0) / 2)


def test_all_reconciles_with_full_aggregate():
    split = split_metrics(ROWS)
    assert split["all"] == aggregate(ROWS)
    assert split["counts"] == {"all": 4, "zh": 2, "en": 2}

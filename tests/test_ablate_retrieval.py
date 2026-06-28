"""Unit tests for the retrieval-config ablation harness's pure helpers."""

from __future__ import annotations

import pytest
import yaml
from scripts.ablate_retrieval import (
    FORCED_CACHE,
    apply_retrieval_overrides,
    metrics_table,
    parse_variants,
    variant_label,
)

BASE_YAML = """\
provider:
  llm_model: MiniMax-M3
  embedding_dim: 1024
retrieval:
  cjk_tokenizer: jieba
storage:
  backend: sqlite
"""


def test_forced_cache_is_off_until_250():
    # The #250 workaround: a config sweep must not reuse a stale baked snapshot.
    assert FORCED_CACHE == "off"


def test_apply_overrides_merges_into_retrieval_only():
    out = apply_retrieval_overrides(BASE_YAML, {"rrf_k": 30, "bm25_weight": 0.5})
    doc = yaml.safe_load(out)
    assert doc["retrieval"] == {"cjk_tokenizer": "jieba", "rrf_k": 30, "bm25_weight": 0.5}
    # other blocks preserved verbatim
    assert doc["provider"]["llm_model"] == "MiniMax-M3"
    assert doc["storage"]["backend"] == "sqlite"


def test_apply_overrides_can_replace_existing_key():
    out = apply_retrieval_overrides(BASE_YAML, {"cjk_tokenizer": "none"})
    assert yaml.safe_load(out)["retrieval"]["cjk_tokenizer"] == "none"


def test_empty_overrides_round_trips():
    doc = yaml.safe_load(apply_retrieval_overrides(BASE_YAML, {}))
    assert doc["retrieval"] == {"cjk_tokenizer": "jieba"}


def test_variant_label():
    assert variant_label({}) == "baseline"
    assert variant_label({"rrf_k": 60}) == "rrf_k=60"
    # sorted keys -> stable label regardless of dict order
    assert variant_label({"vector_weight": 1.5, "bm25_weight": 0.3}) == "bm25_weight=0.3,vector_weight=1.5"


def test_metrics_table_renders_missing_as_dash():
    rows = [
        {"label": "rrf_k=30", "exit_code": 0, "metrics": {"hit_at_3": 0.7, "mrr": 0.61}},
        {"label": "rrf_k=60", "exit_code": 0, "metrics": {"hit_at_3": 0.72}},  # mrr missing
    ]
    table = metrics_table(rows, metric_keys=("hit_at_3", "mrr"))
    assert "| rrf_k=30 | 0 | 0.700 | 0.610 |" in table
    assert "| rrf_k=60 | 0 | 0.720 | - |" in table


def test_parse_variants_validates_shape():
    assert parse_variants('[{"rrf_k": 30}, {"rrf_k": 60}]') == [{"rrf_k": 30}, {"rrf_k": 60}]
    with pytest.raises(ValueError):
        parse_variants('{"rrf_k": 30}')  # not a list
    with pytest.raises(ValueError):
        parse_variants("[1, 2, 3]")  # not objects

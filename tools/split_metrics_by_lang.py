"""Offline per-language split of an eval NDJSON's per-query rows.

The dataset contract's ``thresholds:`` map is flat (no per-language nesting), so a
bilingual dataset is gated on one blended set. This tool recovers the zh/en split
that ``docs/dikw-eval-plan.md`` §2.4 asks for, for ``reports/BASELINES.md``: read an
eval NDJSON, take the EvalReport's ``per_query`` rows, bucket by query-id prefix
(``zh-`` / ``en-``), and recompute the five retrieval metrics per bucket.

The metric formulas mirror ``dikw-core/src/dikw_core/eval/metrics.py`` exactly
(binary ``expect_any`` relevance) so ``split_metrics(rows)["all"]`` reconciles with
the engine's reported blended doc metrics — the calibration run asserts that
equality.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Iterable, Sequence
from typing import Any

METRIC_KEYS = ("hit_at_3", "hit_at_10", "mrr", "ndcg_at_10", "recall_at_100")


def hit_at_k(ranked: Sequence[str], expected_any: Iterable[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top = set(ranked[:k])
    return 1.0 if any(e in top for e in expected_any) else 0.0


def reciprocal_rank(ranked: Sequence[str], expected_any: Iterable[str]) -> float:
    expected = set(expected_any)
    for idx, key in enumerate(ranked, start=1):
        if key in expected:
            return 1.0 / idx
    return 0.0


def ndcg_at_k(ranked: Sequence[str], expected_any: Iterable[str], k: int) -> float:
    if k <= 0:
        return 0.0
    expected = set(expected_any)
    if not expected:
        return 0.0
    dcg = 0.0
    for idx, key in enumerate(ranked[:k], start=1):
        if key in expected:
            dcg += 1.0 / math.log2(idx + 1)
    n_rel = min(len(expected), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, n_rel + 1))
    return dcg / idcg if idcg > 0 else 0.0


def recall_at_k(ranked: Sequence[str], expected_any: Iterable[str], k: int) -> float:
    if k <= 0:
        return 0.0
    expected = set(expected_any)
    if not expected:
        return 0.0
    return len(set(ranked[:k]) & expected) / len(expected)


def aggregate(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Mean of each metric across rows. Empty input → all zeros."""
    if not rows:
        return dict.fromkeys(METRIC_KEYS, 0.0)
    n = len(rows)
    pairs = [(r.get("ranked", []), r.get("expect_any", [])) for r in rows]
    return {
        "hit_at_3": sum(hit_at_k(rk, ex, 3) for rk, ex in pairs) / n,
        "hit_at_10": sum(hit_at_k(rk, ex, 10) for rk, ex in pairs) / n,
        "mrr": sum(reciprocal_rank(rk, ex) for rk, ex in pairs) / n,
        "ndcg_at_10": sum(ndcg_at_k(rk, ex, 10) for rk, ex in pairs) / n,
        "recall_at_100": sum(recall_at_k(rk, ex, 100) for rk, ex in pairs) / n,
    }


def lang_of(qid: str) -> str:
    if qid.startswith("zh-"):
        return "zh"
    if qid.startswith("en-"):
        return "en"
    return "other"


def split_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {"zh": [], "en": [], "other": []}
    for r in rows:
        buckets[lang_of(str(r.get("id", "")))].append(r)
    out: dict[str, Any] = {"all": aggregate(rows), "counts": {"all": len(rows)}}
    for lang in ("zh", "en", "other"):
        if buckets[lang]:
            out[lang] = aggregate(buckets[lang])
            out["counts"][lang] = len(buckets[lang])
    return out


def per_query_rows(ndjson_path: str) -> list[dict[str, Any]]:
    """Extract the EvalReport ``per_query`` rows from an eval NDJSON file.

    The stream carries progress events plus the final EvalReport; the report is the
    line with the longest ``per_query`` list.
    """
    best: list[dict[str, Any]] = []
    with open(ndjson_path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            pq = obj.get("per_query") if isinstance(obj, dict) else None
            if isinstance(pq, list) and len(pq) >= len(best):
                best = pq
    return best


def format_markdown(name: str, split: dict[str, Any]) -> str:
    head = "| lang | n | " + " | ".join(METRIC_KEYS) + " |"
    sep = "|" + "---|" * (2 + len(METRIC_KEYS))
    lines = [f"### {name}", "", head, sep]
    for lang in ("all", "zh", "en", "other"):
        if lang not in split:
            continue
        m = split[lang]
        n = split["counts"].get(lang, "")
        cells = " | ".join(f"{m[k]:.3f}" for k in METRIC_KEYS)
        lines.append(f"| {lang} | {n} | {cells} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Per-language split of an eval NDJSON.")
    p.add_argument("ndjson", help="path to an eval NDJSON with per_query rows")
    p.add_argument("--name", default="dataset")
    args = p.parse_args(argv)
    rows = per_query_rows(args.ndjson)
    if not rows:
        print(f"::error::no per_query rows in {args.ndjson}", file=sys.stderr)
        return 1
    print(format_markdown(args.name, split_metrics(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

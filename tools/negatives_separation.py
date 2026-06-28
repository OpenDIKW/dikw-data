"""Offline pos-vs-neg relevance-score separation for an eval NDJSON.

An ``expect_none=True`` (off-corpus) query is "satisfied" when the engine's top
hit for it scores *low* — a healthy engine surfaces nothing relevant. dikw-core
emits negatives as ``negative_diagnostics`` (``{q, ranked}``) and positives as
``per_query`` (``{q, id?, expect_any, ranked}``). Both are **diagnostic-only**
today: neither row carries an absolute relevance score, so "low" is not
measurable (dikw-core#249). This tool reads whatever score field #249 lands — it
probes a small list of candidate key names — and computes the pos-vs-neg top-1
score separation plus the ``expect_none`` satisfaction at a cutoff.

Until #249 ships it degrades gracefully: ``separation`` reports
``scores_available: false`` with a rank-only observation (counts + the leaked
top stems) so the caller knows the separation is not yet computable rather than
silently reporting a bogus zero. The moment #249 lands — under any of the probed
key names — the same tool yields the real margin with no code change.

Mirrors ``tools/split_metrics_by_lang.py``: the pure functions (probe + compute)
are unit-tested; a thin CLI reads the NDJSON's EvalReport line.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Sequence
from typing import Any

# Candidate names for the per-hit score list #249 will align with ``ranked``,
# and for a precomputed top-1 score. Probed in order; first present wins. Listing
# several keeps the tool robust to the exact key #249 chooses.
_SCORES_KEYS = ("scores", "ranked_scores", "hit_scores", "doc_scores")
_TOP1_KEYS = ("top1_score", "top_score", "max_score")


def top1_score(row: dict[str, Any]) -> float | None:
    """A row's top-ranked absolute relevance score, or ``None`` when the eval
    output carries no score yet (pre-#249).

    Prefers an explicit precomputed top-1 score; otherwise takes the first
    element of a per-hit score list aligned with ``ranked``.
    """
    for key in _TOP1_KEYS:
        value = row.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    for key in _SCORES_KEYS:
        value = row.get(key)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) and value:
            first = value[0]
            if isinstance(first, (int, float)) and not isinstance(first, bool):
                return float(first)
    return None


def _scores(rows: list[dict[str, Any]]) -> list[float]:
    """Top-1 scores of the rows that carry one (drops scoreless rows)."""
    return [s for s in (top1_score(r) for r in rows) if s is not None]


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def expect_none_satisfaction(negatives: list[dict[str, Any]], cutoff: float) -> float | None:
    """Fraction of negatives whose top-1 score falls below ``cutoff`` (a healthy
    off-corpus query scores low). ``None`` when no negative carries a score.
    """
    scores = _scores(negatives)
    if not scores:
        return None
    return sum(1 for s in scores if s < cutoff) / len(scores)


def _leak_sample(negatives: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Rank-only observational fallback: the top stem each negative surfaced."""
    out: list[dict[str, Any]] = []
    for row in negatives[:limit]:
        ranked = row.get("ranked") or []
        out.append({"q": row.get("q", ""), "top_stem": ranked[0] if ranked else None})
    return out


def separation(
    per_query: list[dict[str, Any]],
    negatives: list[dict[str, Any]],
    *,
    cutoff: float | None = None,
) -> dict[str, Any]:
    """Pos-vs-neg top-1 score separation.

    ``cutoff`` for ``expect_none`` satisfaction defaults to the midpoint between
    the negative and positive top-1 means — the natural decision boundary once a
    separation exists. Degrades to a rank-only observation (``scores_available:
    False``) when the eval output predates #249.
    """
    pos = _scores(per_query)
    neg = _scores(negatives)
    counts = {"positives": len(per_query), "negatives": len(negatives)}
    if not pos or not neg:
        return {
            "scores_available": False,
            "counts": counts,
            "note": (
                "no absolute relevance scores in eval output (pre-dikw-core#249); "
                "pos-vs-neg separation is not computable. Showing rank-only "
                "negative observations."
            ),
            "negative_leaks_sample": _leak_sample(negatives),
        }
    pos_s, neg_s = _summary(pos), _summary(neg)
    if cutoff is None:
        cutoff = (pos_s["mean"] + neg_s["mean"]) / 2
    return {
        "scores_available": True,
        "counts": counts,
        "positive_top1": pos_s,
        "negative_top1": neg_s,
        "separation_margin": pos_s["mean"] - neg_s["mean"],
        "cutoff": cutoff,
        "expect_none_satisfaction": expect_none_satisfaction(negatives, cutoff),
    }


def eval_report(ndjson_path: str) -> dict[str, Any]:
    """The EvalReport object from an eval NDJSON stream.

    The stream carries progress events plus the final EvalReport; the report is
    the dict line carrying ``metrics`` with the most ``per_query`` rows (mirrors
    ``run_eval.parse_eval_report`` / ``split_metrics_by_lang.per_query_rows``).
    """
    best: dict[str, Any] = {}
    best_len = -1
    with open(ndjson_path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict) or "metrics" not in obj:
                continue
            pq = obj.get("per_query")
            n = len(pq) if isinstance(pq, list) else 0
            if n >= best_len:
                best, best_len = obj, n
    return best


def format_markdown(name: str, result: dict[str, Any]) -> str:
    lines = [f"### {name} — negatives separation", ""]
    counts = result["counts"]
    lines.append(f"- positives: {counts['positives']}  negatives: {counts['negatives']}")
    if not result["scores_available"]:
        lines.append(f"- **scores unavailable** — {result['note']}")
        if result.get("negative_leaks_sample"):
            lines.append("- negative top-stems (rank-only):")
            for leak in result["negative_leaks_sample"]:
                lines.append(f"  - `{leak['q']}` -> `{leak['top_stem']}`")
        return "\n".join(lines)
    pos, neg = result["positive_top1"], result["negative_top1"]
    lines += [
        f"- positive top-1 score: mean {pos['mean']:.4f} (min {pos['min']:.4f})",
        f"- negative top-1 score: mean {neg['mean']:.4f} (max {neg['max']:.4f})",
        f"- **separation margin**: {result['separation_margin']:.4f}",
        f"- expect_none satisfaction @ cutoff {result['cutoff']:.4f}: "
        f"{result['expect_none_satisfaction']:.3f}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Pos-vs-neg relevance-score separation for an eval NDJSON "
        "(degrades to rank-only until dikw-core#249 surfaces scores)."
    )
    p.add_argument("ndjson", help="path to an eval NDJSON (per_query + negative_diagnostics)")
    p.add_argument("--name", default="dataset")
    p.add_argument("--cutoff", type=float, default=None, help="expect_none score cutoff (default: pos/neg midpoint)")
    args = p.parse_args(argv)
    report = eval_report(args.ndjson)
    if not report:
        print(f"::error::no EvalReport in {args.ndjson}", file=sys.stderr)
        return 1
    result = separation(
        report.get("per_query", []),
        report.get("negative_diagnostics", []),
        cutoff=args.cutoff,
    )
    print(format_markdown(args.name, result))
    return 0


if __name__ == "__main__":
    sys.exit(main())

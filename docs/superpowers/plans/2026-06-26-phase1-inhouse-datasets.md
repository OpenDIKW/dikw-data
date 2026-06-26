# Phase 1 In-House Datasets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and calibrate two in-house retrieval datasets — `domain-bilingual-v1` (the gate that matters) and `negatives-ood-v1` (off-corpus robustness) — per `docs/dikw-eval-plan.md` §2.2, with thresholds set at `observed − margin` from one real-vector run.

**Architecture:** Reuse `synthetic-diverse-v2`'s 24-doc corpus (12 zh / 12 en). LLM-generate queries through the existing MiniMax factory, curate them, materialize two contract-conformant dataset packages. Calibrate with one `run_eval.py` pass; the engine gates one blended flat-threshold set while a new offline tool recovers the zh/en split for `reports/BASELINES.md`. `dikw-core` stays read-only.

**Tech Stack:** Python 3.12/3.13, uv, ruff, mypy (strict, `src` only), pytest; `dikw-core` v0.6.1 (editable); MiniMax (LLM) + Gitee `Qwen3-Embedding-0.6B`@1024 (embeddings).

## Global Constraints

- `dikw-core` is **read-only** — never modify a tracked `dikw-core` file; verify `git -C ../dikw-core status` is clean after every step that touches it.
- Secrets load **in-process only**; key **values are never echoed or committed**. `.env` and `.env.eval` are gitignored.
- Dataset contract (`scripts/validate_dataset.py`): each dataset dir has `dataset.yaml` + `queries.yaml` + `corpus/*.md`; every query needs `id` + `q` + exactly one of `expect_any: [stem]` / `expect_none: true`; `thresholds:` is a **flat** map; only `hit_at_3`, `hit_at_10`, `mrr`, `ndcg_at_10`, `recall_at_100` are valid threshold keys.
- Query ids are **language-prefixed** `zh-…` / `en-…` (a query's language matches its gold doc's frontmatter `language:`).
- Threshold margins (§2.3): gate at `observed − 0.03` for `ndcg_at_10`/`recall_at_100`, `observed − 0.05` for `hit_at_3`/`hit_at_10`.
- Branch `eval/phase1-inhouse-datasets` is stacked on `eval/anchor-calibration` (#6); the new PR (#7) bases on `eval/anchor-calibration`.

---

### Task 1: `split_metrics_by_lang` tool (offline per-language metric split)

**Files:**
- Create: `tools/split_metrics_by_lang.py`
- Test: `tests/test_split_metrics_by_lang.py`

**Interfaces:**
- Produces: `split_metrics(rows: list[dict]) -> dict` returning `{"all": {<5 metrics>}, "zh": {...}, "en": {...}, "counts": {...}}`; `aggregate(rows) -> dict[str,float]`; `per_query_rows(ndjson_path: str) -> list[dict]`; `format_markdown(name, split) -> str`; CLI `python tools/split_metrics_by_lang.py <ndjson> --name <n>`.
- Metric formulas mirror `dikw-core/src/dikw_core/eval/metrics.py` exactly (binary `expect_any` relevance), so `split_metrics(all_rows)["all"]` reconciles with the engine's blended doc metrics.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_split_metrics_by_lang.py
"""Unit tests for the offline per-language metric splitter."""

from __future__ import annotations

import math

import pytest

from tools.split_metrics_by_lang import aggregate, lang_of, split_metrics

# Four queries; ranked lists are gold-stem placements at known ranks.
ROWS = [
    {"id": "zh-a", "expect_any": ["doc_a"], "ranked": ["doc_a", "x", "y"]},      # rank 1
    {"id": "zh-b", "expect_any": ["doc_b"], "ranked": ["x", "doc_b", "y"]},      # rank 2
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_split_metrics_by_lang.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.split_metrics_by_lang'`.

- [ ] **Step 3: Write the implementation**

```python
# tools/split_metrics_by_lang.py
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
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
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
```

- [ ] **Step 4: Run tests + lint to verify they pass**

Run: `uv run pytest tests/test_split_metrics_by_lang.py -q && uv run ruff check tools/split_metrics_by_lang.py tests/test_split_metrics_by_lang.py`
Expected: tests PASS, ruff clean.

- [ ] **Step 5: Commit**

```bash
git add tools/split_metrics_by_lang.py tests/test_split_metrics_by_lang.py
git commit -m "feat(tools): per-language metric splitter for bilingual eval NDJSON"
```

---

### Task 2: Scaffold both dataset packages (corpus copy)

**Files:**
- Create: `datasets/domain-bilingual-v1/corpus/*.md` (24 files), `datasets/negatives-ood-v1/corpus/*.md` (24 files)
- Create: `datasets/domain-bilingual-v1/dataset.yaml`, `datasets/negatives-ood-v1/dataset.yaml` (thresholds empty for now)

- [ ] **Step 1: Copy the reused corpus into both datasets**

```bash
cd /Users/hele/Projects/opendikw/dikw-data/.claude/worktrees/dikw-data-ci-flag
for d in domain-bilingual-v1 negatives-ood-v1; do
  mkdir -p "datasets/$d/corpus"
  cp datasets/synthetic-diverse-v2/corpus/*.md "datasets/$d/corpus/"
done
ls datasets/domain-bilingual-v1/corpus/*.md | wc -l   # expect 24
ls datasets/negatives-ood-v1/corpus/*.md | wc -l       # expect 24
```

- [ ] **Step 2: Write placeholder `dataset.yaml` (thresholds filled in Task 6)**

`datasets/domain-bilingual-v1/dataset.yaml`:

```yaml
name: domain-bilingual-v1
description: >
  In-house bilingual (50/50 zh+en) domain retrieval set over the diverse-v2
  corpus. The Phase-1 retrieval gate. Engine gates one blended flat-threshold
  set; the zh/en split is recorded in reports/BASELINES.md (see
  docs/dikw-eval-plan.md §2.4). Thresholds set at observed − margin.
thresholds: {}
```

`datasets/negatives-ood-v1/dataset.yaml`:

```yaml
name: negatives-ood-v1
description: >
  Off-corpus negatives (expect_none) riding the diverse-v2 corpus: plausible but
  unanswerable zh+en queries that a healthy engine returns nothing relevant for.
  expect_none is diagnostic-only in dikw-core (no threshold key), so this set is
  observe-only — see reports/BASELINES.md negative diagnostics.
thresholds: {}
```

- [ ] **Step 3: Verify dikw-core untouched + commit the scaffold**

```bash
git -C ../../../../dikw-core status --short   # expect empty
git add datasets/domain-bilingual-v1 datasets/negatives-ood-v1
git commit -m "feat(datasets): scaffold domain-bilingual-v1 + negatives-ood-v1 (corpus copy)"
```

> NOTE: `validate_dataset.py` will fail until `queries.yaml` exists (Task 4) — that's expected; do not run it yet.

---

### Task 3: LLM-generate query candidates (real MiniMax spend)

**Files:**
- Create (gitignored): `.env` (factory key), `generated/<dataset>/…` candidate audit
- Verify: `configs/minimax.yml` exists

- [ ] **Step 1: Wire the factory key without echoing its value**

The factory transport reads `ANTHROPIC_API_KEY` from `.env` (`src/dikw_data/config.py`), while the eval key lives in `.env.eval` as `MINIMAX_API_KEY`. Copy the value across without printing it:

```bash
test -f configs/minimax.yml || echo "MISSING configs/minimax.yml"
grep -q '^ANTHROPIC_API_KEY=' .env 2>/dev/null || \
  grep '^MINIMAX_API_KEY=' .env.eval | sed 's/^MINIMAX_API_KEY=/ANTHROPIC_API_KEY=/' >> .env
grep -c '^ANTHROPIC_API_KEY=' .env   # expect 1; value never printed
```

- [ ] **Step 2: Dry-run the generator (no spend) to confirm wiring**

```bash
UV_NO_SYNC=1 uv run python scripts/generate_candidates.py --dataset domain-bilingual-v1 --queries 30 --dry-run
```
Expected: JSON status lines with `"status": "dry_run"`, exit 0.

- [ ] **Step 3: Generate positives for `domain-bilingual-v1` (real spend)**

```bash
UV_NO_SYNC=1 uv run python scripts/generate_candidates.py --dataset domain-bilingual-v1 --queries 50 --resume
```
Generates ~50 candidates (so curation can keep ~40 with each doc covered). Candidates land in the AuditStore under `generated/domain-bilingual-v1/`. Re-run with `--resume` if it stalls.

- [ ] **Step 4: Generate negatives for `negatives-ood-v1` (real spend)**

```bash
UV_NO_SYNC=1 uv run python scripts/generate_candidates.py --dataset negatives-ood-v1 --queries 35 --resume
```
The generator's prompt already supports `expect_none=true` negatives. Aim for ~35 candidates to curate down to ~25.

- [ ] **Step 5: Export candidates to a readable JSON for curation**

Read the AuditStore results (the generator persists each task's `result_json`). Dump the candidate arrays to `$CLAUDE_JOB_DIR/tmp/<dataset>-candidates.json` for the curation pass in Task 4. (Inspect `src/dikw_data/audit.py` for the read API; the candidates are the JSON array in the successful task's `result_json`.)

> No commit — `.env` and `generated/` are gitignored.

---

### Task 4: Curate + materialize `queries.yaml` (the human-verify gate)

**Files:**
- Create: `datasets/domain-bilingual-v1/queries.yaml`, `datasets/negatives-ood-v1/queries.yaml`

- [ ] **Step 1: Curate `domain-bilingual-v1` positives**

For each candidate, confirm: the `expect_any` stem exists in the corpus and genuinely answers the query; the query language matches that stem's frontmatter `language:`; drop low-`confidence`/ambiguous/duplicate items. Keep ~40 with **every doc covered ≥ 1** and **zh/en balanced (~20/~20)**. Deliberately retain a handful of **intra-cluster-confusable** queries within `chinese-history`×4 and `world-history`×4 (e.g. a vaguely-phrased "中国某王朝的中央集权改革" that plausibly matches qin/tang/wang-anshi) so ranking has signal. Optionally run `scripts/llm_review.py` for a second opinion.

- [ ] **Step 2: Write `datasets/domain-bilingual-v1/queries.yaml`**

Shape (ids language-prefixed; a query's language = its gold doc's language):

```yaml
queries:
  - id: zh-tang-founding-basis
    q: "唐朝建立的核心政治基础是什么？"
    expect_any: [chinese-history-tang-founding]
  - id: en-photosynthesis-chlorophyll
    q: "What role does chlorophyll play in photosynthesis?"
    expect_any: [science-photosynthesis]
  # … ~40 total, ~20 zh + ~20 en, every corpus stem covered ≥ 1
```

- [ ] **Step 3: Curate + write `datasets/negatives-ood-v1/queries.yaml`**

~25 `expect_none` queries, plausible-but-uncovered, mixed zh/en, ids prefixed:

```yaml
queries:
  - id: en-docker-bridge-network
    q: "How do I configure a Docker bridge network?"
    expect_none: true
  - id: zh-bike-derailleur-repair
    q: "如何修理自行车变速器？"
    expect_none: true
  # … ~25 total, ~12 zh + ~13 en
```

- [ ] **Step 4: Validate both datasets ($0, before any eval spend)**

```bash
uv run python scripts/validate_dataset.py datasets/domain-bilingual-v1
uv run python scripts/validate_dataset.py datasets/negatives-ood-v1
```
Expected: both report OK / exit 0. Fix any unresolved-stem or duplicate-id errors.

- [ ] **Step 5: Commit**

```bash
git add datasets/domain-bilingual-v1/queries.yaml datasets/negatives-ood-v1/queries.yaml
git commit -m "feat(datasets): curated bilingual positives + ood negatives queries"
```

---

### Task 5: Calibration eval run (real Gitee spend) + reconcile splitter

**Files:**
- Create (gitignored): `reports/<UTC-ts>/…` NDJSON + `summary.json`

- [ ] **Step 1: Run the real-vector eval over both datasets**

```bash
UV_NO_SYNC=1 uv run python scripts/run_eval.py \
  --datasets "$PWD/datasets/domain-bilingual-v1,$PWD/datasets/negatives-ood-v1" \
  --retrieval all
```
Cold run pays Gitee embedding; warm reruns hit the snapshot cache. Capture the printed `reports/<UTC-ts>/` path.

- [ ] **Step 2: Confirm exit health + per-mode views**

```bash
cat reports/<UTC-ts>/summary.json   # worst_exit_code == 0
```
Expected: `worst_exit_code == 0`; per-mode `bm25/vector/hybrid` blocks present for `domain-bilingual-v1`.

- [ ] **Step 3: Reconcile the splitter against the engine (catches formula drift)**

Run the splitter on the hybrid NDJSON and confirm its `all` block equals the engine's blended doc metrics in `summary.json` (within 1e-9):

```bash
uv run python tools/split_metrics_by_lang.py \
  reports/<UTC-ts>/domain-bilingual-v1__hybrid.ndjson --name domain-bilingual-v1
```
Compare the `all` row to the engine's reported `doc/hybrid` metrics. If they diverge, the splitter formulas are wrong — fix before proceeding. (The actual NDJSON filename may differ; use the hybrid/doc report that carries `per_query`.)

> No commit — `reports/<ts>/` is gitignored (only `reports/BASELINES.md` is tracked).

---

### Task 6: Set thresholds at `observed − margin` + re-validate

**Files:**
- Modify: `datasets/domain-bilingual-v1/dataset.yaml`

- [ ] **Step 1: Fill `domain-bilingual-v1` thresholds from observed blended (doc/hybrid)**

Using the `all` row from Task 5: gate at `observed − 0.03` for `ndcg_at_10`/`recall_at_100`, `observed − 0.05` for `hit_at_3`/`hit_at_10`; `mrr` at `observed − 0.05`. Replace `thresholds: {}` with the computed values, e.g.:

```yaml
thresholds:
  hit_at_3: 0.XX        # observed_hit_at_3 − 0.05
  hit_at_10: 0.XX       # observed_hit_at_10 − 0.05
  mrr: 0.XX             # observed_mrr − 0.05
  ndcg_at_10: 0.XX      # observed_ndcg_at_10 − 0.03
  recall_at_100: 0.XX   # observed_recall_at_100 − 0.03
```
`negatives-ood-v1/dataset.yaml` stays `thresholds: {}` (observe-only).

- [ ] **Step 2: Re-validate + re-run to confirm the gate passes**

```bash
uv run python scripts/validate_dataset.py datasets/domain-bilingual-v1
UV_NO_SYNC=1 uv run python scripts/run_eval.py \
  --datasets "$PWD/datasets/domain-bilingual-v1" --retrieval all
cat reports/<UTC-ts>/summary.json   # worst_exit_code == 0 (warm; cache hit)
```
Expected: validation OK; eval exit 0 (observed clears the just-set floor by the margin).

- [ ] **Step 3: Commit**

```bash
git add datasets/domain-bilingual-v1/dataset.yaml
git commit -m "feat(datasets): calibrate domain-bilingual-v1 thresholds at observed-margin"
```

---

### Task 7: Record the baseline entry (satisfies eval-gate)

**Files:**
- Modify: `reports/BASELINES.md`

- [ ] **Step 1: Append a new dated entry**

Add a `## 2026-06-26 — domain-bilingual-v1 + negatives-ood-v1 (Phase 1 calibration)` entry. Include: dikw-core v0.6.1 + MiniMax+Gitee + `--retrieval all`; the per-mode blended table for `domain-bilingual-v1`; the **zh/en split** table from `tools/split_metrics_by_lang.py`; the chosen `observed − margin` thresholds; `negatives-ood-v1` diagnostics (how many negatives leaked, pos-vs-neg top-1 score separation); and a saturation note if metrics ran high. Name at least one retrieval metric (the eval-gate content check requires a new dated header + a metric token).

- [ ] **Step 2: Verify the eval-gate content check passes locally**

```bash
uv run python -c "from tools.check_baselines import check_baseline_addition as c; \
import sys; \
lines=open('reports/BASELINES.md',encoding='utf-8').read().splitlines(); \
print(c([l for l in lines if '2026-06-26' in l or 'ndcg' in l], existing_headers=set(), touches_datasets=True))"
```
Expected: `[]` (no violations) — a new dated header + a retrieval metric are present.

- [ ] **Step 3: Commit**

```bash
git add reports/BASELINES.md
git commit -m "eval: record Phase 1 in-house dataset calibration (blended + zh/en split)"
```

---

### Task 8: Final gates + PR #7

- [ ] **Step 1: Run the full local CI floor**

```bash
uv run ruff check . && uv run mypy src && uv run pytest -q
for d in domain-bilingual-v1 negatives-ood-v1; do
  uv run python scripts/validate_dataset.py "datasets/$d"
done
git -C ../../../../dikw-core status --short   # expect empty (read-only held)
```
Expected: all green; dikw-core clean.

- [ ] **Step 2: Push the stacked branch**

```bash
git push -u origin eval/phase1-inhouse-datasets
```

- [ ] **Step 3: Open PR #7 stacked on #6**

```bash
gh pr create --base eval/anchor-calibration --head eval/phase1-inhouse-datasets \
  --title "feat(datasets): Phase 1 in-house sets — domain-bilingual-v1 + negatives-ood-v1" \
  --body "Implements eval-plan datasets ii/iii. Single bilingual dataset with engine-gated blended thresholds (observed−margin) + offline zh/en split recorded in BASELINES.md; observe-only off-corpus negatives. dikw-core read-only. Merge order #5 → #6 → #7.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

- [ ] **Step 4: Confirm cloud CI green**

```bash
gh pr checks   # lint-type-test (3.12 + 3.13) + eval-gate all pass
```
Expected: all checks green. If `eval-gate` is red, the BASELINES.md entry shape is wrong (Task 7) — fix and re-push.

---

## Self-Review

**Spec coverage:** §2 decisions → Tasks 2/3/4 (single dataset, reuse corpus, LLM-gen). §3 dataset specs → Tasks 2/4. §4 generation+verify → Tasks 3/4. §5 calibration (run, splitter, per-language, negatives observe-only) → Tasks 1/5/6/7. §6 deliverables/PR → Task 8. §7 constraints → Global Constraints + read-only checks in Tasks 2/8. §8 risks → Task 4 Step 1 (saturation mitigation), §5.4 (negatives), §4.1 (key wiring → Task 3 Step 1). §9 acceptance → Tasks 6/7/8. No gaps.

**Placeholder scan:** The only `0.XX` placeholders are in Task 6 thresholds, which are *necessarily* computed from the Task-5 run (the methodology forbids guessing them) — each carries the exact formula. `reports/<UTC-ts>/` and the NDJSON filename are runtime-resolved paths, flagged as such. No disallowed "add error handling"/"write tests"-style gaps.

**Type consistency:** `split_metrics`/`aggregate`/`lang_of`/`per_query_rows`/`format_markdown` signatures match between the implementation (Task 1 Step 3) and the test (Step 1) and the CLI usage (Task 5 Step 3). Metric keys are the single `METRIC_KEYS` tuple throughout.

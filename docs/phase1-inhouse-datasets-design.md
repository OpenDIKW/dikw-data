# Phase 1 in-house retrieval datasets — design

> **Status:** approved design (2026-06-26); implementation pending.
> Implements datasets **ii** (`domain-bilingual-v1`) and **iii** (`negatives-ood-v1`)
> from [`dikw-eval-plan.md`](dikw-eval-plan.md) §2.2, following the threshold
> methodology in §2.3 and the bilingual-split rule in §2.4. `dikw-core` stays
> **read-only**.

## 1. Context

Phase 0 (smoke) and the public-anchor calibration (scifact + cmteb-t2-subset,
recorded in [`reports/BASELINES.md`](../reports/BASELINES.md)) are done: the eval
chain is validated end-to-end on real vectors against a read-only `dikw-core`
v0.6.1. The Phase 0→1 advance criterion (public anchors land within ±0.10) is met.

The remaining Phase 1 work is the **in-house retrieval gate that matters**: a
bilingual domain set plus an off-corpus negatives set. The existing synthetic sets
saturate at 1.0 and carry no committed gate; these two datasets are the first
in-house sets calibrated to `observed − margin`.

## 2. Decisions (settled)

1. **Per-language gating = single dataset + recorded split.** One
   `domain-bilingual-v1`; the engine gates a single blended flat-threshold set.
   zh/en metrics are computed offline from the run's NDJSON `per_query` rows and
   recorded in `reports/BASELINES.md`. Rationale: `dataset.yaml thresholds:` is a
   flat map (no per-language nesting — see `scripts/validate_dataset.py`), one
   shared corpus avoids 3× duplication, and ~40 blended queries are statistically
   steadier than 2×~20. §2.4's "gate zh/en separately" is honored as a *review*
   gate (the recorded split + the eval-gate CI that forces a baseline entry on any
   `datasets/**` change), not an engine threshold.
2. **Reuse the existing 24-doc corpus** from `synthetic-diverse-v2` (12 zh / 12 en)
   as-is. Dataset "size" lives in ~40 multi-angle queries, not in new corpus docs.
   §2.3 already says recalibrate when a corpus crosses ~50 docs, so 24 is fine for
   P1 kickoff.
3. **LLM-generate queries + verify.** Use the existing MiniMax factory
   (`scripts/generate_candidates.py` → `RetryingMiniMaxClient`) to draft candidates,
   then verify/curate before materializing `queries.yaml`.

## 3. Dataset specs

Both datasets are self-contained packages conforming to the `dikw-core` dataset
contract (`dataset.yaml` + `corpus/` + `queries.yaml`).

### `domain-bilingual-v1`

```
datasets/domain-bilingual-v1/
  corpus/        # copy of synthetic-diverse-v2's 24 .md (12 zh / 12 en)
  queries.yaml   # ~40 positives; ids prefixed zh-/en-; ~20 each; expect_any: [stem]
  dataset.yaml   # blended flat thresholds, set at observed − margin (§5)
```

- **Query ids carry the language tag** as a leading segment, `zh-…` / `en-…`, so
  the offline splitter can bucket them. (The current `synthetic-diverse-v2` uses a
  `_zh`/`_en` *suffix*; we standardize on a **prefix** here because the splitter
  keys on `id.startswith("zh-"|"en-")`.)
- **A query's language matches its gold doc's language** (the corpus doc's
  frontmatter `language:`), so the zh slice exercises the jieba/CJK path and the en
  slice does not — per §2.4.
- **Coverage:** every corpus doc gets ≥ 1 positive query; zh/en query counts stay
  balanced (~20/~20).

### `negatives-ood-v1`

```
datasets/negatives-ood-v1/
  corpus/        # same 24 .md (copied; the contract requires a corpus dir)
  queries.yaml   # ~25 expect_none: true (zh + en), domain-adjacent but uncovered
  dataset.yaml   # thresholds: {}  (see §5 — expect_none is not a thresholdable key)
```

- Negatives are **plausible-but-unanswerable**: topics adjacent to the domain
  (history/science/finance/…) that no corpus doc actually covers, so a healthy
  engine returns nothing relevant. Mixed zh/en, ids prefixed `zh-`/`en-`.
- The negatives ride the **same** corpus as `domain-bilingual-v1` so "no
  hallucinated relevance on off-corpus queries" is measured against the real
  domain index.

## 4. Generation + verification workflow

1. **Generate.** `scripts/generate_candidates.py --dataset <name> --queries N`
   reads `datasets/<name>/corpus/` and prompts MiniMax for a JSON array of
   candidates (`q`, `type`, `expect_any`, `evidence`, `confidence`, `rationale`;
   `expect_none=true` for negatives), driven through the factory (retries, JSON
   repair, audit, `--resume`). Generate with **coverage control**: ensure each doc
   gets ≥ 1 positive and the zh/en balance holds (run per-language or per-cluster
   prompts as needed).
   - **Key wiring note:** the factory's default transport reads
     `get_required_env("ANTHROPIC_API_KEY")` from `.env` (not `.env.eval`'s
     `MINIMAX_API_KEY`). Generation provides the MiniMax key value as
     `ANTHROPIC_API_KEY` **in-process / in a gitignored `.env`, never echoed**.
     The `llm_base_url` already defaults to MiniMax. This is the one piece of
     wiring the generation step must set up; no change to `llm_client.py` defaults.
2. **Verify (the "human-verify" step).** Export candidates and curate each one:
   confirm the gold stem is correct and the query is genuinely answerable from that
   doc (positives) / genuinely uncovered (negatives); check the language tag; drop
   low-confidence or ambiguous items; dedup; rebalance zh/en. `scripts/llm_review.py`
   may add a second LLM opinion (`pass`/`fail`/`rewrite` + risk flags) — optional,
   extra spend, on by default. **The final human verifier is the maintainer**, via
   the committed `queries.yaml` diff in the PR.
3. **Materialize.** Write curated `queries.yaml` (+ `dataset.yaml`) and copy the
   corpus into each dataset dir. `scripts/validate_dataset.py datasets/<name>` must
   pass ($0, before any spend).

## 5. Threshold calibration (§2.3 methodology)

1. **One real-vector run** over both datasets: `scripts/run_eval.py --datasets
   "$PWD/datasets/domain-bilingual-v1,$PWD/datasets/negatives-ood-v1" --retrieval
   all` (`--cache read_write`). Real Gitee embedding spend on the cold run; warm
   reruns hit the snapshot cache. Confirm `summary.json worst_exit_code == 0` and
   per-mode `bm25/vector/hybrid` views (look for RRF lift).
2. **`domain-bilingual-v1` gate** = blended `observed − margin`, written into
   `dataset.yaml`: **−0.03** absolute for `ndcg_at_10`/`recall_at_100`, **−0.05**
   for `hit_at_3`/`hit_at_10` (hit@k is noisier on small sets). Gate is a
   regression detector, not an aspiration.
3. **Per-language split** via a new tool `tools/split_metrics_by_lang.py`: read the
   run's NDJSON `per_query` rows (`id`, `ranked` top-100, `expect_any`), bucket by
   `id` prefix `zh-`/`en-`, and recompute `hit_at_3`/`hit_at_10`/`mrr`/
   `ndcg_at_10`/`recall_at_100` per language. Output goes into the `BASELINES.md`
   entry. Pure function (bucket+compute) is unit-tested; a thin CLI reads the
   NDJSON. (Feasibility confirmed: `dikw-core/src/dikw_core/eval/runner.py:206-288`
   emits `per_query` with `id`/`ranked`/`expect_any`.)
4. **`negatives-ood-v1` is observe-only.** `expect_none` satisfaction is **not** a
   valid `dataset.yaml` threshold key (only `hit_at_3`/`hit_at_10`/`mrr`/
   `ndcg_at_10`/`recall_at_100` are), and the engine treats `expect_none` queries as
   **diagnostic only** (`runner.py:244`, no exit-1). So `dataset.yaml` carries
   `thresholds: {}`; the value is the recorded `negative_diagnostics` (how many
   negatives leaked a relevant-looking hit) plus pos-vs-neg top-1 score separation,
   logged in `BASELINES.md` for Phase 1. A future gate would need an engine feature,
   out of scope here.

## 6. Deliverables + PR strategy

- **Branch** `eval/phase1-inhouse-datasets`, stacked on `eval/anchor-calibration`
  (#6); new PR (#7) with base `eval/anchor-calibration`. Merge order stays
  #5 → #6 → #7 (GitHub auto-retargets on each merge).
- **New/changed files:**
  - `datasets/domain-bilingual-v1/**` (corpus copy + queries.yaml + dataset.yaml)
  - `datasets/negatives-ood-v1/**` (corpus copy + queries.yaml + dataset.yaml)
  - `tools/split_metrics_by_lang.py` + `tests/test_split_metrics_by_lang.py`
  - `reports/BASELINES.md` — new dated entry (blended + zh/en split + negatives
    diagnostics); satisfies the eval-gate content check
  - possibly a small candidates-export helper if AuditStore→curation needs one
  - docs touch-ups (`dikw-eval-plan.md` phase note; this spec)

## 7. Constraints

- **`dikw-core` read-only.** Materialize/copy only into `dikw-data` paths; never
  modify a tracked `dikw-core` file (verify `git -C ../dikw-core status` clean).
- **Secrets.** `.env`/`.env.eval` keys load in-process only; values are never
  echoed or committed. `.env` (if created for the factory) is already gitignored.
- **Real spend.** The calibration run incurs real Gitee embedding cost; LLM
  generation + optional `llm_review` incur real MiniMax cost. Both are expected and
  bounded: one cold eval run, a few batched generation calls (per language/cluster),
  and — if enabled — one review call per candidate.

## 8. Risks

1. **Saturation.** 24 docs across 10 very distinct topics retrieve easily, so even
   paraphrastic queries may push metrics near 1.0 — weakening "the gate that
   matters." Mitigation (no corpus change): deliberately write a subset of
   **intra-cluster-confusable** queries within the multi-doc clusters
   (`chinese-history`×4, `world-history`×4) so ranking (`ndcg`/`mrr`) has signal.
   Then follow §2.3 — record observed, gate at `observed − margin`, do **not**
   engineer to a target. Residual saturation is logged as a known limitation; a
   denser, deliberately-confusable corpus is a `domain-bilingual-v2` follow-up.
2. **`expect_none` ungateable** — handled in §5.4 (observe-only).
3. **Factory key wiring** — handled in §4.1.

## 9. Acceptance criteria

- `scripts/validate_dataset.py` passes for both datasets; `uv run ruff check .`,
  `uv run mypy src`, `uv run pytest` all green (incl. the new splitter test).
- Calibration run: `summary.json worst_exit_code == 0`; per-mode views recorded.
- `reports/BASELINES.md` has a new entry with blended metrics, the zh/en split, and
  negatives diagnostics; `domain-bilingual-v1` thresholds = `observed − margin`.
- Cloud CI (incl. `eval-gate`) green on PR #7.

## 10. Out of scope (Phase 1 follow-ups / later phases)

- `domain-bilingual-v2` with a denser, deliberately-confusable corpus (if v1
  saturates).
- `mm-asset-v1` (multimodal, Phase 3), `synth-quality-v1` (K-layer, Phase 2) — per
  `dikw-eval-plan.md` §2.2.
- Promoting any threshold to a hard gate beyond the first calibrated floor (needs
  ≥ 2 stable runs per §2.3).

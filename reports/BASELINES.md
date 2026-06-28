# dikw-data eval baselines

Dated log of real-vector eval runs against the `dikw-core` engine — the tracked
source of truth that mirrors `dikw-core/evals/BASELINES.md`. Everything else under
`reports/` (per-run NDJSON + `summary.json`) is disposable and gitignored; this
file is kept under version control via the `!reports/BASELINES.md` exception in
`.gitignore`.

The `eval-gate` workflow (`.github/workflows/eval-gate.yml` +
`tools/check_baselines.py`) requires a **new** entry here whenever a PR changes
`datasets/**`: it must be a new dated header and name at least one retrieval
metric. That keeps a dataset change from shifting the engine's numbers without a
recorded, reviewable outcome.

## Entry template

```
## <YYYY-MM-DD> — <short title>

- dikw-core: <version>   provider: <llm>+<embedder>   retrieval: <hybrid|all>   cache: <mode>
- <dataset>: ndcg_at_10 <v>, hit_at_3 <v>, hit_at_10 <v>, mrr <v>, recall_at_100 <v>
- notes: <anchor delta / saturation / per-language split / std across reruns>
```

## Entries

## 2026-06-25 — scifact + cmteb-t2-subset public-anchor calibration (Phase 0→1)

Run from `dikw-data` against a read-only `dikw-core` v0.6.1 (editable, `[cjk]`).
Provider: **MiniMax-M2.7** (LLM, unused — retrieval-only) + **Gitee
Qwen3-Embedding-0.6B@1024** (embeddings) + sqlite. `--retrieval all`, `--eval
retrieval`, `--cache read_write`, `serve-and-run`, 1 run each. Datasets handed in
by absolute path from `dikw-core/evals/datasets/` (out-of-tree). Canonical view is
`doc/hybrid`.

**scifact** (en, 300 queries / 5183 docs) — `passed: True`, exit 0.

| mode | hit_at_3 | hit_at_10 | mrr | ndcg_at_10 | recall_at_100 |
|---|---|---|---|---|---|
| bm25 | 0.700 | 0.790 | 0.622 | 0.651 | 0.855 |
| vector | 0.700 | 0.813 | 0.639 | 0.673 | 0.903 |
| **hybrid** | **0.723** | **0.843** | **0.655** | **0.689** | **0.947** |

- Clears dikw-core's committed floor (`ndcg_at_10 0.67 / hit_at_3 0.71 / hit_at_10
  0.82 / mrr 0.64 / recall_at_100 0.92`).
- Matches BEIR literature `ndcg_at_10 ≈ 0.67` (observed 0.689, Δ 0.019 — well within
  the ±0.10 advance criterion).
- RRF lift is real: hybrid ndcg_at_10 (0.689) > vector (0.673) > bm25 (0.651).

**cmteb-t2-subset** (zh, 300 queries / 5000 docs) — `passed: True`, exit 0.

| mode | hit_at_3 | hit_at_10 | mrr | ndcg_at_10 | recall_at_100 |
|---|---|---|---|---|---|
| bm25 | 0.933 | 0.967 | 0.924 | 0.840 | 0.908 |
| vector | 0.973 | 0.990 | 0.967 | 0.943 | 0.980 |
| **hybrid** | **0.987** | **0.987** | **0.979** | **0.946** | **0.988** |

- Clears the dataset's calibrated thresholds (`ndcg_at_10 ≥ 0.93`, etc.) and
  **reproduces dikw-core's own committed numbers** to within noise: bm25
  `ndcg_at_10 0.840` (exact), vector `0.943` (vs 0.942), hybrid `0.946` (vs 0.952).
- **Not comparable to the CMTEB leaderboard (~0.50).** This is a 300-query curated
  subset with distractor padding, intentionally easier than the full 118K-passage
  benchmark — its `dataset.yaml` says so. The anchor for the subset is dikw-core's
  committed baseline, which we reproduced, not the leaderboard figure.
- **jieba CJK confirmed**: zh `bm25 ndcg_at_10 0.840`, not the degenerate
  unicode61 per-character `0.031`. RRF hybrid edges vector (0.946 vs 0.943).

**Cross-cutting checks**

- Multi-batch embedding confirmed (5183 / 5000 chunks ≫ the 16/batch Gitee limit) —
  the Phase 0 gap (single batch only) is now covered.
- Read-only held: scifact `corpus/` + `queries.yaml` materialized into gitignored
  paths; its tracked `dataset.yaml` was backed up and restored, so
  `git -C dikw-core status` stays clean.

**Gates: still none.** This is Phase 0→1 calibration, not a gate. Per-language
thresholds get set at `observed − margin` once the in-house sets
(`domain-bilingual-v1`, `negatives-ood-v1`) exist — see `docs/dikw-eval-plan.md`
§2.3 and §3.

## 2026-06-26 — domain-bilingual-v1 + negatives-ood-v1 (Phase 1 in-house sets)

Run from `dikw-data` against a read-only `dikw-core` v0.6.2 (editable, `[cjk]`).
Provider: **MiniMax-M2.7** (LLM — used only for query *generation*, not retrieval)
+ **Gitee Qwen3-Embedding-0.6B@1024** (embeddings) + sqlite. `--retrieval all`,
`--eval retrieval`, `--cache read_write`, `serve-and-run`, 1 run each. Both reuse
the `synthetic-diverse-v2` 24-doc corpus (12 zh / 12 en). Queries are
LLM-generated through the MiniMax factory (`scripts/generate_candidates.py`) then
human-verified gold. Canonical view is `doc/hybrid`. See design:
`docs/phase1-inhouse-datasets-design.md`.

**domain-bilingual-v1** (34 positives: 18 zh + 16 en, every doc covered) —
`passed: True`, exit 0.

| mode | hit_at_3 | hit_at_10 | mrr | ndcg_at_10 | recall_at_100 |
|---|---|---|---|---|---|
| bm25 | 1.000 | 1.000 | 0.985 | 0.989 | 1.000 |
| vector | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| **hybrid** | **1.000** | **1.000** | **1.000** | **1.000** | **1.000** |

Per-language split (canonical `doc/hybrid`, via `tools/split_metrics_by_lang.py`):

| lang | n | hit_at_3 | hit_at_10 | mrr | ndcg_at_10 | recall_at_100 |
|---|---|---|---|---|---|---|
| all | 34 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| zh | 18 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| en | 16 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

- **Saturates at 1.0** on vector/hybrid — 24 distinct-topic docs are trivially
  separable by the embedder. Only **bm25** carries signal (`mrr 0.985`,
  `ndcg_at_10 0.989`), from the deliberately intra-cluster-confusable history
  queries. The splitter's `all` block reconciles with the engine's blended doc
  metrics to within 1e-9 (the tool is validated against the engine's own formulas).
- **Gate set at `observed − margin`** (first committed in-house floor):
  `hit_at_3 0.95 / hit_at_10 0.95 / mrr 0.95 / ndcg_at_10 0.97 / recall_at_100 0.97`
  (−0.05 hit@k/mrr, −0.03 ndcg/recall). This is a **regression-detector floor, not
  a discriminative benchmark** — a denser, deliberately-confusable
  `domain-bilingual-v2` is the discriminative follow-up.

**negatives-ood-v1** (23 `expect_none`: 11 zh + 12 en, riding the same corpus) —
`passed: True`, exit 0.

- `thresholds: {}`, `metrics: {}` — **observe-only**. `expect_none` is *diagnostic
  only* in dikw-core (`runner.py:244`: no threshold key, no exit-1), and doc-level
  retrieval cannot abstain (it always returns a ranked list), so there is no
  "satisfaction" metric to gate at this layer.
- Diagnostic: for every off-topic query the top-ranked doc is an unrelated corpus
  doc (e.g. `麻婆豆腐` → `science-plate-tectonics`) — no spurious strong match into a
  same-topic domain doc. Score-based pos-vs-neg separation needs the served
  `retrieve` contract (scored cutoff) and is out of scope for the doc-level eval.

**Cross-cutting**

- Read-only held: both datasets live under `dikw-data/datasets/` (corpus copied
  from `synthetic-diverse-v2`). `git -C ../dikw-core status` stays clean.
- Factory fix: MiniMax-M2.7 reasoning was exhausting the 4096-token output cap and
  truncating candidate JSON mid-array (`stop_reason: max_tokens`); raised the
  generation output budget to 16000 (`src/dikw_data/llm_client.py`).

**Gates.** First committed in-house floor: `domain-bilingual-v1` (saturated →
regression-detector). `negatives-ood-v1` observe-only. Recalibrate / promote once a
discriminative `domain-bilingual-v2` exists (corpus > ~50 docs, deliberately
confusable) — see `docs/dikw-eval-plan.md` §2.3/§3 and
`docs/phase1-inhouse-datasets-design.md`.

## 2026-06-28 — domain-bilingual-v2 calibration (discriminative confusable set)

**Config.** dikw-core 0.6.4; provider: MiniMax-M3 (LLM, unused — retrieval-only) +
Gitee Qwen3-Embedding-0.6B@1024 (embeddings) + sqlite + jieba. `--retrieval all`,
`--eval retrieval`, `--cache read_write`; cold-embedded the 56-doc corpus once.

**domain-bilingual-v2** (56 docs / 56 queries; 8 intra-cluster-confusable clusters,
28 zh + 28 en; corpus + queries via codex gpt-5.5 xhigh) — `passed: True`, exit 0.

Canonical (doc / hybrid):
`hit_at_3 1.000 / hit_at_10 1.000 / mrr 0.991 / ndcg_at_10 0.993 / recall_at_100 1.000`

Per-mode (`--retrieval all`):

| mode | hit_at_3 | hit_at_10 | mrr | ndcg_at_10 | recall_at_100 |
|---|---|---|---|---|---|
| bm25   | 1.000 | 1.000 | 0.955 | 0.967 | 1.000 |
| vector | 1.000 | 1.000 | 0.991 | 0.993 | 1.000 |
| hybrid | 1.000 | 1.000 | 0.991 | 0.993 | 1.000 |

zh/en split (offline `tools/split_metrics_by_lang.py`, reconciles with the engine's
blended doc metrics):

| lang | n | hit_at_3 | hit_at_10 | mrr | ndcg_at_10 | recall_at_100 |
|---|---|---|---|---|---|---|
| all | 56 | 1.000 | 1.000 | 0.991 | 0.993 | 1.000 |
| zh  | 28 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| en  | 28 | 1.000 | 1.000 | 0.982 | 0.987 | 1.000 |

- **Only partially de-saturated.** hybrid/vector `ndcg_at_10 0.993` (vs v1's 1.000)
  — barely below saturation, and the **zh slice is fully 1.0**. The confusable
  corpus itself works — **bm25 `ndcg 0.967` carries real intra-cluster signal** — but
  the **draft queries over-name their gold** (they embed the answer's distinctive
  term verbatim), making vector retrieval trivial. A **query gold-tightening pass**
  (human verification of `queries.yaml`: describe the answer without naming it) is
  the discriminative follow-up; recalibrate after it (vector/hybrid should fall
  toward bm25).
- **Gate set at `observed − margin`** (−0.05 hit@k/mrr, −0.03 ndcg/recall):
  `hit_at_3 0.95 / hit_at_10 0.95 / mrr 0.94 / ndcg_at_10 0.96 / recall_at_100 0.97`.
  A regression-detector floor over **draft** queries — recalibrate after gold-tightening.
- v2's retrieval calibration is independent of dikw-core#249 (no `expect_none`
  negatives) and #250 (single fixed retrieval config, no ablation sweep).

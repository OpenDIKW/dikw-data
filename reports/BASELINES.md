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

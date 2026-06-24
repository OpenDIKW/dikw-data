# Phase 0 — Smoke / Calibration Results

> Companion to [`dikw-eval-plan.md`](dikw-eval-plan.md) §3 (Phasing). This records the
> first real-vector run of the `dikw-core` eval pipeline from `dikw-data`: what was
> de-risked, the engineering gaps it surfaced (now fixed), and the calibration insight
> that shapes Phase 1. No gates were set — Phase 0 only proves the pipeline and records
> first-run distributions.

**Run context.** `dikw-core` v0.6.1, installed editable with the `[cjk]` extra (jieba).
Engine treated as read-only. Eval driven by `scripts/run_eval.py` in `serve-and-run`
mode (one-shot local server per dataset). Dataset: `synthetic-diverse-v1` (16 docs →
16 chunks → one Gitee embed batch of `chunks 0-15`, within the `embedding_batch_size: 16`
limit). Provider: MiniMax-M2.7 (unused — retrieval-only) + Gitee `Qwen3-Embedding-0.6B`@1024
+ sqlite.

## What was verified (the 5 de-risking checks from the plan)

| # | Check | Result |
|---|---|---|
| 1 | Out-of-tree **absolute** `--dataset "$PWD/datasets/..."` returns a real `EvalReport` (not `dataset_not_found`) | ✅ The linchpin holds. `serve-and-run` boots a local server that reads the dataset by absolute path — datasets stay in `dikw-data`, `dikw-core` is never touched. |
| 2 | Snapshot cache populates; a second run skips re-embedding | ✅ Cold run logged **87** embed lines (Gitee called); warm run logged **0** (cache hit, no spend). Cache lives at `dikw-core/evals/.cache/snapshots/synthetic-diverse-v1`. |
| 3 | Full-corpus ingest stays under the Gitee batch (≤16) / rate limits | ✅ 16 chunks → 1 batch, no rate-limit errors. Wall-clock ≈ 33 s cold, ≈ 28 s warm. *(Only one batch — multi-batch behavior is not yet stress-tested; see Gaps.)* |
| 4 | `retrieval.cjk_tokenizer: jieba` is honored (CJK BM25 not degenerate) | ✅ jieba prefix dict loads in the server before retrieval. *(Discrimination unverifiable on this saturated set — see Gaps.)* |
| 5 | `--against` trips exit 1 on a regression; a within-tolerance run stays 0 | ✅ Honest baseline → exit 0. Tampered baseline (`hit_at_3` forced to 1.5) → exit 1, and `run_eval.py` propagates it via `worst_exit_code`. |

### Read-only constraint held

The eval writes snapshots into `dikw-core/evals/.cache/`, which is gitignored upstream
(`dikw-core/.gitignore:38: evals/.cache/`). After the runs, `git -C dikw-core status`
stays clean. The editable install writes only into our venv, not the engine source tree.

## First-run metric distribution (record, no gate)

`synthetic-diverse-v1`, `--retrieval all`, doc view. Dataset's own thresholds:
`hit_at_3 ≥ 0.9`, `hit_at_10 ≥ 0.9`, `mrr ≥ 0.8` → **passed: true**.

| metric | bm25 | vector | hybrid |
|---|---|---|---|
| hit_at_3 | 1.0 | 1.0 | 1.0 |
| hit_at_10 | 1.0 | 1.0 | 1.0 |
| mrr | 1.0 | 1.0 | 1.0 |
| ndcg_at_10 | 1.0 | 1.0 | 1.0 |
| recall_at_100 | 1.0 | 1.0 | 1.0 |

**Calibration insight: the synthetic sets are saturated.** Every metric is 1.0 across
every mode — the corpus is small and each query trivially resolves to its target, so the
set has **no discriminative power**. It cannot tell bm25 from vector from hybrid, cannot
expose RRF lift, and cannot validate the zh-vs-en split. This is exactly why Phase 1
builds harder material: a literature-anchored calibration floor (`scifact` / `cmteb`),
an in-house bilingual domain set with non-trivial relevance, and an OOD/negatives set.

## Engineering gaps surfaced and fixed (this branch)

The smoke run found four issues a paper design could not. All are fixed here with tests.

1. **`.env.eval` was not gitignored.** `.gitignore` only had `.env`, which does not match
   `.env.eval` — the secrets file could have been committed. Added an explicit `.env.eval`
   line (kept distinct so the tracked `.env.example` stays tracked).
2. **`run_eval.py` validated key *names* but never injected the values.** `dikw-core`
   reads provider keys straight from `os.environ` and `serve-and-run` forwards the parent
   env to the server it spawns; the wrapper loaded `.env.eval` only for the presence check,
   so a real run would have failed auth. Fixed with `merge_env()`, which overlays non-empty
   values onto each subprocess `env=` (never exported globally, never printed).
3. **The rich progress widget polluted stdout.** Default `--wait` output is NDJSON, but the
   progress widget's ANSI bytes interleave on the same stream, so `parse_eval_report()`
   returned `{}` and the captured report was unparseable (gate result unreadable). Fixed by
   always passing `--plain`.
4. **`summarize()` counted pass/fail by `report.passed`, not the exit code.** `--against`
   trips the exit code to 1 on a regression *without* flipping the report's `passed` flag
   (which reflects only the dataset's own thresholds), so a regressed run was miscounted as
   "passed". Counts now follow the authoritative exit code, agreeing with `worst_exit_code`.

## Environment notes (worktree-specific)

- **Path to the engine.** From a nested git worktree, the plan's `../dikw-core` resolves to
  the wrong place. Install with the absolute path:
  `uv pip install -e "/abs/path/to/dikw-core[cjk]"`.
- **uv resync gotcha.** `uv pip install -e` into a uv-managed venv can be clobbered by a
  later `uv run` resync. It survived here, but run eval commands with `UV_NO_SYNC=1` (or
  `uv run --no-sync`) to be safe.

## Gaps — not covered by this smoke (carry into Phase 1)

- **No discrimination signal.** The saturated set cannot validate ranking quality, RRF
  lift, or the zh/en split. Needs harder datasets before any real threshold is meaningful.
- **Single embed batch only.** Multi-batch behavior under the Gitee ≤16 / rate limits is
  untested; a >16-chunk corpus is the real stress case.
- **Synth / K-layer and the LLM judge are untouched.** This run was retrieval-only, so the
  MiniMax path, `synth/*` metrics, and judge sampling are still unverified (Phase 2).
- **No literature anchor yet.** `scifact` / `cmteb-t2-subset` are not materialized, so
  there is no external calibration point (Phase 0's "within ±0.10 of anchor" gate to
  advance is not yet checkable).

## Next

Phase 1 — build the retrieval three: `domain-bilingual-v1` (in-house bilingual domain
retrieval), `negatives-ood-v1` (off-corpus robustness), and materialize `scifact` /
`cmteb-t2-subset` as the anchored calibration floor. Set per-language gates at
`observed − margin` once a clean real-vector run on non-saturated data exists.

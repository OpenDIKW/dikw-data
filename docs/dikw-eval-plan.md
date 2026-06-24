# dikw Evaluation Plan

> **Status:** macro design (Phase 0 not yet run). This document is the blueprint
> and the cornerstone for building `dikw` evaluation datasets; later increments
> execute the phases it lays out.
> **Ownership:** authored and run from this repo (`dikw-data`). `dikw-core` is
> treated as **read-only** — we never modify it.
> **Audience:** anyone setting up or extending evaluation of the `dikw-core`
> knowledge engine.

---

## 0. Scope & constraints

**Goal.** Define a repeatable program to evaluate the `dikw-core` knowledge engine
(`../dikw-core`, v0.6.1) across the dimensions that matter — retrieval quality first,
knowledge-synthesis quality next — anchored to mainstream industry practice (BEIR,
MTEB/CMTEB, MS MARCO, RAGAS, TruLens, ViDoRe).

**Division of repos.**
- `dikw-core` — the engine under test. **Read-only.** Provides the eval runner
  (`dikw client eval`), the dataset contract, the A/B harness, and four packaged
  datasets we reuse.
- `dikw-data` (this repo) — the **data factory + eval owner.** All eval datasets,
  the orchestration wrapper, baselines, reports, and this plan live here. Datasets
  are handed to the engine by **absolute path**, so nothing needs to be added to
  `dikw-core`.

**Secrets.** `.env.eval` (gitignored, listed in `.worktreeinclude` so it is
auto-copied into worktrees) holds the provider keys:

| Var | Role | Provider / endpoint |
|---|---|---|
| `MINIMAX_API_KEY` | LLM / synth | MiniMax via `anthropic_compat`, `https://api.minimaxi.com/anthropic` |
| `DEEPSEEK_API_KEY` | LLM / synth (A/B alternate) | DeepSeek via `anthropic_compat`, `https://api.deepseek.com/anthropic` |
| `GITEE_API_KEY` | **Embeddings** | Gitee AI via `openai_compat`, `https://ai.gitee.com/v1` |

`.env.eval` is never committed and key values are never echoed. The orchestration
wrapper sources it in-process only.

**Locked decisions.**
1. **Default eval base** = MiniMax-M2.7 (LLM/synth) + Gitee `Qwen3-Embedding-0.6B`@1024
   (embeddings) + sqlite. Chosen because it matches `dikw-core`'s own `scifact`
   calibration (same embedder/dim) and needs no synth token override. DeepSeek-V4 +
   Gitee `bge-m3`@1024 is the documented **A/B alternate**.
2. **Dataset priority** = *retrieval three first*: public-benchmark calibration,
   bilingual domain retrieval, negatives/OOD. Multimodal and synth/K-layer quality
   are designed here but deferred to later phases.

**Critical engine fact that shapes everything below.** The server-side eval task
**always builds the real embedder** from the served base's `dikw.yml`
(`dikw-core/src/dikw_core/server/synth_op.py:176`, `build_embedder(cfg.provider)`).
So `dikw client eval` **requires a valid provider + `GITEE_API_KEY`** — there is no
key-free CLI path. The deterministic `FakeEmbeddings` are reachable only from
`dikw-core`'s in-repo pytest gate (`tests/test_retrieval_quality.py`), **not** from
the CLI. Budget for real embedding calls on every CLI eval.

---

## Part I — Eval engineering pipeline + environment deployment

### 1.1 Recommended default configuration (the eval base `dikw.yml`)

Start from `dikw-core/tests/fixtures/live-minimax-gitee.dikw.yml` and add the CJK
tokenizer (so Chinese BM25/hybrid is non-degenerate):

```yaml
provider:
  llm: anthropic_compat
  llm_model: MiniMax-M2.7
  llm_base_url: https://api.minimaxi.com/anthropic
  llm_api_key_env: MINIMAX_API_KEY
  embedding: openai_compat
  embedding_model: Qwen3-Embedding-0.6B
  embedding_base_url: https://ai.gitee.com/v1
  embedding_api_key_env: GITEE_API_KEY
  embedding_dim: 1024            # locked at first ingest; matches scifact calibration
  embedding_batch_size: 16       # Gitee AI rejects batches > 25
retrieval:
  cjk_tokenizer: jieba           # requires dikw-core [cjk] extra; needed for zh corpora
storage:
  backend: sqlite                # .dikw/index.sqlite; disposable, no service
```

The provider block is **required** to carry `llm_api_key_env`, `embedding_api_key_env`,
and `embedding_dim` (no defaults). The A/B alternate swaps `llm_model: deepseek-v4-pro`
+ `llm_base_url: https://api.deepseek.com/anthropic` + `llm_api_key_env: DEEPSEEK_API_KEY`
+ `llm_max_tokens_synth: 8192` (reasoning models need the larger budget) and
`embedding_model: bge-m3`.

### 1.2 Deployment recipe (no `dikw-core` edits)

All commands run from this repo (`dikw-data/`).

1. **Install the engine editable from the sibling checkout** (do **not** pip-install a
   wheel): `uv pip install -e ../dikw-core`. Rationale: the eval snapshot cache root is
   found by walking up from `dikw-core/src/dikw_core/eval/runner.py` for a sibling
   `evals/` dir. An editable install keeps that layout, so
   `../dikw-core/evals/.cache/snapshots/` persists and embeddings are paid **once** per
   `(dataset, model, dim, corpus-hash)`. A wheel install has no sibling `evals/` →
   forces `--cache off` → re-embeds the full corpus through Gitee on every run.
   *(Confirm in the Phase-0 smoke test.)*
2. **Provision a dedicated eval base** under the gitignored `bases/` dir:
   `uv run dikw init bases/eval-base`, then write the `dikw.yml` from §1.1 into it.
   The base is a thin config holder — the runner ingests each dataset's corpus into its
   own hermetic snapshot, **not** into the base, so the base never trips the
   `embedding_dim` lock and embedder swaps are safe.
3. **Load secrets in-process only** (the wrapper does this; never global `export`,
   never echo values).
4. **Two run modes:**
   - Batch (server stays warm): `uv run dikw serve --base bases/eval-base` then
     `uv run dikw client eval --dataset "$PWD/datasets/<name>" --retrieval all --eval retrieval --wait`.
   - One-shot: `uv run dikw client serve-and-run --base bases/eval-base -- eval --dataset "$PWD/datasets/<name>" --wait`.
5. **Datasets stay in this repo.** `--dataset` is resolved **server-side** via
   `load_dataset(Path(name_or_path))`, so an **absolute** path into
   `dikw-data/datasets/<name>` works and we never touch `dikw-core`. Always pass
   `"$PWD/datasets/<name>"` (absolute — the server's CWD may differ).
   *(Confirm out-of-tree absolute-path acceptance in Phase-0.)*

### 1.3 Eval engineering chain (链路)

```
dataset (dikw-data/datasets/<name>, dikw-core dataset contract)
  → scripts/validate_dataset.py              # shape gate, $0, before any spend
  → [server eval task] ingest corpus → hermetic snapshot
        (cache: ../dikw-core/evals/.cache/snapshots, keyed corpus+model+dim — NOT retrieval cfg)
  → dikw client eval --dataset <abs> --retrieval … --eval … --wait   → NDJSON EvalReport
  → capture → dikw-data/reports/<UTC-ts>/<dataset>__<mode>.ndjson  (+ summary.json rollup)
  → gate:  --against <baseline.json>   (built-in, tolerance 0.02, direction-aware)
            OR ../dikw-core/evals/tools/ab_experiment.py   (N-run Welch t-test + bootstrap)
  → baseline log: dikw-data/reports/BASELINES.md  (mirror dikw-core/evals/BASELINES.md)
  → CI: a dikw-data workflow mirroring dikw-core/tools/check_baselines.py
        (require a baseline entry when datasets/** or thresholds: change)
```

**Reused `dikw-core` assets (do not rebuild):** `evals/tools/ab_experiment.py`
(rigorous before/after), the eval `--against`/`--write-baseline`/`--tolerance` gate,
the snapshot cache, `evals/BASELINES.md` discipline, and the
`tools/check_baselines.py` + `.github/workflows/eval-gate.yml` CI pattern.

### 1.4 Orchestration wrapper — specification (built in a later increment)

`dikw-data/scripts/run_eval.py` (uv-run; a `justfile` target may wrap it). CLI:

```
--datasets NAME[,NAME…]            # default: dikw-data/datasets/* + scifact,cmteb-t2-subset
--retrieval hybrid|bm25|vector|all # default hybrid
--eval retrieval|synth|both        # default retrieval
--judge [--judge-sample auto|N]
--mode serve|serve-and-run         # default serve (warm batch)
--cache read_write|rebuild|off     # default read_write; FORCE off on retrieval-config sweeps
--base bases/eval-base
--against <baseline.json> | --write-baseline <path> [--tolerance F]
--out reports/<UTC-ts>/
```

Behavior: source `.env.eval` in-process (abort if any referenced key var is empty;
never print values) → ensure base exists → run `validate_dataset.py` per dataset
(fail fast, $0) → resolve each dataset to an absolute path → invoke
`dikw client eval … --pretty off` (NDJSON) → capture per-`(dataset, mode)` NDJSON +
a `summary.json` rollup → propagate the worst-of exit code (0 pass / 1 fail /
2 bad-spec) so CI can gate.

> **Cache footgun.** The snapshot cache key is `{dataset}/{model}__{dim}__{corpus_hash}__…`
> and does **not** include `RetrievalConfig`. Retrieval-config ablations (rrf_k,
> weights, fusion) under `--cache read_write` silently reuse the first snapshot — they
> **must** pass `--cache off`. Embedder swaps (model/dim change the key) are safe under
> `read_write` and keep separate cache namespaces.

### 1.5 Reproducibility & rigor

- **Retrieval eval is deterministic** given a fixed snapshot (same model+dim+corpus →
  identical vectors). One run suffices; rerun only to detect cache/provider drift.
- **Synth + LLM judges are non-deterministic.** Use `--judge-sample auto` (~25 items,
  targeting a <±0.2 95%-CI half-width) for single runs; for ship decisions use
  `ab_experiment.py` with **N ≥ 5 runs/arm** (Welch t-test + bootstrap CI) and widen
  `--tolerance` to 0.05–0.08 for synth baselines so model jitter doesn't trip the gate.
- **Baselines pin** date, `dikw-core` version (0.6.1), provider combo, retrieval mode,
  `--cache` mode, dataset, run count, and observed metrics ± std. Thresholds are set at
  `observed − margin` (see §2.3).

### 1.6 Worktree & secrets hygiene

- `.env.eval` is gitignored and in `.worktreeinclude` → auto-copied into new worktrees.
- `generated/`, `reports/`, `bases/` are already gitignored in this repo → generated
  bases, sqlite indices, and NDJSON reports never enter git.
- Committed `--against` baselines must stay tracked: keep them **beside their dataset**
  (e.g. `datasets/<name>/baseline.json`) to avoid fighting the `reports/` ignore.
- CI injects keys via secrets, not `.env.eval`.

---

## Part II — Eval dimensions + dataset construction (industry-anchored)

### 2.1 DIKW-layer scorecard

The engine's job is **retrieval + knowledge construction**, not answering. The pyramid
maps onto that: D is the substrate (not directly scored), I is retrieval (the
heavily-instrumented core that carries the hard gates), K is synthesized-knowledge
quality, W is hand-authored and not yet separable. The cross-layer `retrieve` HTTP
contract is what an external agent actually calls, so it gets its own row.

| DIKW layer | dikw-core role | Metrics measurable today | Industry analog | Disposition |
|---|---|---|---|---|
| **D** — Data | raw `sources/` markdown | none direct; `synth/source_chunk_coverage`, `synth/page_density` (informational) | corpus hygiene (no benchmark) | **parked** → ingestion lint, not a scored dimension |
| **I** — retrieval | chunk (~900 tok) + FTS5/BM25 (jieba) + vector → RRF hybrid (k=60, bm25=0.3, vec=1.5) | `hit_at_3`, `hit_at_10`, `mrr`, `ndcg_at_10`, `recall_at_100`; views `doc/ chunk/ asset/`; per-mode `bm25/ vector/ hybrid/` under `--retrieval all` | **BEIR / MTEB-CMTEB / MS MARCO / MIRACL** (≈1:1) | **PRIMARY gate layer** |
| **I** — multimodal | `asset/` + `chunk/` views via `targets.yaml` | `asset/<m>`, `chunk/<m>`; `expect_asset_any`, `expect_chunk_any` | **ViDoRe / M-BEIR / ColPali** (nDCG@5, recall@k) | covered; needs thresholds (**Phase 3**) |
| **K** — Knowledge | LLM-synth pages + `[[wikilinks]]` + closed-set taxonomy | deterministic: `synth/fact_grounding_ratio`, `synth/atomicity_score`, `synth/duplicate_ratio_max` (↓ lower-better), `synth/wikilink_resolved_ratio`, `synth/language_fidelity`, `synth/expected_coverage`; opt-in LLM judges (bootstrap 95% CI): `synth/fact_entailment_ratio`, 4-dim page judge, category-, wikilink-, semantic-atomicity-correctness | KB-synthesis (factuality/grounding, dedup, coverage, linking); RAGAS/TruLens **grounding** legs | mostly covered (**Phase 2**); judges observe-then-gate |
| **W** — Wisdom | hand-written, indexed alongside K | none isolating W | RAG answer-relevance (no clean benchmark) | **parked** → no W-lift metric today |
| **`retrieve` contract** | HTTP ranked chunks + page refs; agent synthesizes | same I-layer metrics on the served ranking | TruLens **context-relevance** / RAGAS **context precision/recall** (retrieval legs only) | covered; generation leg is **agent-side → out of scope** |

**Key narrative.** RAGAS / TruLens / ARES are **end-to-end** frameworks spanning
I + K + agent generation. `dikw-core` owns only I + K. So we map their
**retrieval and grounding legs** onto dikw-core metrics and **cleave off their
answer-generation legs** into a separate Phase-4 harness that does **not** gate the
engine — otherwise a retrieval regression and an agent/prompt change would be
indistinguishable.

### 2.2 Dataset portfolio (build the three retrieval sets first)

Each dataset is a self-contained package conforming to the `dikw-core` dataset
contract (`dataset.yaml` + `corpus/` + `queries.yaml` [+ `targets.yaml` / `expected.yaml`]).
All thresholds below are **placeholders to be calibrated** (see §2.3).

| # | Name | Purpose | Layer | Size | Lang | Modes | Primary metrics (placeholder) | Sourcing | Priority |
|---|---|---|---|---|---|---|---|---|---|
| i | reuse `scifact` + `cmteb-t2-subset` | public-benchmark calibration / floor | I doc | ~300 q en / ~200 q zh | en + zh | retrieval, `--retrieval all` | `ndcg_at_10` en ≥ 0.67 / zh ≥ 0.48; `recall_at_100` ≥ 0.90 | materialize via `dikw-core/evals/tools/convert_beir.py` (corpus gitignored upstream) | **P1** |
| ii | `domain-bilingual-v1` | in-house domain retrieval (the gate that matters) | I doc + contract | ~40 docs / ~40 q | 50/50 zh + en | retrieval, `--retrieval all` | `hit_at_3` ≥ 0.70; `ndcg_at_10` ≥ 0.55; `recall_at_100` ≥ 0.85; report bm25/vector/hybrid lift | reuse `synthetic-diverse-v2` corpus; LLM-gen queries via factory + human-verify gold | **P1** |
| iii | `negatives-ood-v1` | robustness: no hallucinated relevance on off-corpus queries | I doc | ~25 q (rides ii corpus) | zh + en | retrieval | `expect_none` satisfaction ≥ 0.90; pos-vs-neg top-1 score separation (info) | LLM-gen plausible-but-unanswerable queries + human filter | **P1** |
| iv | `mm-asset-v1` | multimodal asset/chunk retrieval (thresholded upgrade of `wiki-mini-mm`) | I chunk + asset | ~15 docs + imgs / ~30 q | zh + en | retrieval + `targets.yaml` | `asset/hit_at_3` ≥ 0.60; `asset/ndcg_at_10` ≥ 0.50; `chunk/hit_at_10` ≥ 0.70 | reuse `synthetic-multimodal-datasets-v1`; author `targets.yaml` (watch anchor collisions) | P3 |
| v | `synth-quality-v1` | K-layer synthesis quality | K | ~20 source docs | zh + en | retrieval + synth | deterministic `synth/*` gates; judges observe-first | curate a 20-doc slice + hand-author `expected.yaml` + `synth.categories` | P2 |

**Contract shapes** (clone from `dikw-core/evals/datasets/{mvp,scifact,cmteb-t2-subset,wiki-mini-mm}`):
- `dataset.yaml`: `name`, `description`, `thresholds:` (retrieval keys bare or
  `doc/|chunk/|asset/`-namespaced; **synth keys must be `synth/`-namespaced; unknown
  keys are rejected**), `modes: [retrieval] | [synth] | [retrieval, synth]`,
  optional `synth:` (`grounding_threshold`, `duplicate_threshold`, `categories`),
  optional `judge:` (`model`, `*_enabled` flags).
- `queries.yaml`: `queries: [{q, id?, query_type?, expect_any|expect_doc_any|
  expect_chunk_any|expect_asset_any | expect_none: true}]` — exactly one of
  positive / negative. Hit@k = any expected identity in top-k.
- `targets.yaml` (multimodal): `chunks: [{id, doc, heading, anchor, asset_id?}]`,
  `assets: [{id, doc, path, heading?, anchor?}]`. `anchor` is a substring resolved to
  a chunk; a collision is a loud error.
- `expected.yaml` (synth coverage): `sources: [{path, expected_titles, expected_keywords}]`.

### 2.3 Threshold-setting methodology (calibrate, don't guess)

1. **First real-vector run records the observed distribution — set no gate before it
   exists.** Guessed thresholds either rubber-stamp regressions or block on noise.
2. **Anchor the public sets first** (dataset i): `scifact` nDCG@10 ≈ 0.67,
   `cmteb-t2-subset` ≈ 0.50. The delta from literature is our chunking/tokenizer offset.
   *(For reference, `dikw-core`'s committed `scifact` floor under our exact embedder is
   `hit_at_3 0.71 / hit_at_10 0.82 / mrr 0.64 / ndcg_at_10 0.67 / recall_at_100 0.92`.)*
3. **Gate at `observed − margin`**: −0.03 absolute for nDCG/recall, −0.05 for hit@k
   (noisier on small sets). The gate is a *regression detector*, not an aspiration.
4. **Re-calibrate** when a dataset crosses ~50 docs / ~30 queries (small-N metrics are
   unstable).
5. **Judges:** never gate on the first run. Collect ≥ 2 runs of bootstrap CIs, confirm
   the CI width is tolerable at sample ≈ 25, then gate at the **lower CI bound** of the
   baseline; pin `judge.model` so judge drift ≠ engine regression.

### 2.4 Metric selection methodology

- **Cutoffs.** `@3` = served-contract gate (the agent consumes a short list — top
  precision drives downstream answer quality). `@10` = ranking quality (`ndcg_at_10`,
  BEIR-comparable). `@100` = pipeline-health floor (`recall_at_100` isolates
  "indexing/embedding broken" from "ranking suboptimal").
- **Bilingual = always split and gate zh/en separately.** zh runs the jieba/CJK path;
  en does not. A blended mean hides a broken-language regression behind a healthy one.
  Tag queries (e.g. `id` prefix `zh-…` / `en-…`) and keep zh/en corpus sizes balanced.
  `synth/language_fidelity` guards against zh→en drift in synthesized pages (gate ≥ 0.95).
- **LLM judges are bias-aware.** Documented verbosity / position / self-enhancement
  biases mean: deterministic-first (gate every property that has a deterministic
  metric); use judges only for properties with no deterministic proxy (completeness,
  clarity, semantic atomicity, entailment nuance); prefer objective entailment/grounding
  judges over preference-style ones; report the CI, not a point estimate.

---

## 3. Phasing (mirrors dikw-core's own `docs/eval-plan.md` triggers)

`dikw-core`'s rule: deterministic metrics first; defer LLM-judge frameworks
(RAGAS/TruLens/ARES) until retrieval saturates **or** corpus > ~50 docs / queries > ~30.

- **Phase 0 — smoke / calibration.** Reuse `mvp` + materialize `scifact` /
  `cmteb-t2-subset`. Goal: pipeline runs end-to-end, numbers land near literature
  anchors, first-run distributions recorded. **No gates yet.** Advance when a clean
  real-vector run exists and public anchors are within ±0.10.
- **Phase 1 — retrieval gates.** Datasets ii + iii (+ i as floor). Gate `hit_at_3` /
  `ndcg_at_10` / `recall_at_100` **per language** at `observed − margin`; show RRF lift
  via per-mode views. Advance when gates are stable across ≥ 2 runs **and**
  (corpus > ~50 docs **or** queries > ~30).
- **Phase 2 — synth / K-layer.** Dataset v. Gate deterministic `synth/*`; turn judges on
  observe-only. Advance when deterministic gates are green and judge CIs are stable
  across ≥ 2 runs (then promote select judges to gates per §2.4).
- **Phase 3 — multimodal.** Dataset iv. Gate `asset/` and `chunk/` metrics. Advance when
  thresholds are calibrated and anchor resolution is clean (no collisions).
- **Phase 4 — agent-side RAG answer eval (separate harness, NOT a dikw-core gate).**
  A distinct harness that calls the `retrieve` contract + a real agent, then applies the
  RAGAS/TruLens/ARES **answer-generation** legs (faithfulness, answer relevancy,
  end-to-end correctness). Lives outside `dikw-core` because the engine does not
  synthesize answers. Advance when I and K layers are gated and stable.

---

## 4. Out of scope (with revisit triggers)

1. **Agent-side final answer generation** — not measurable in-core (the agent, not the
   engine, synthesizes answers). → Phase-4 separate harness.
2. **W-layer retrieval lift** — no metric isolates W's contribution today. → parked until
   W gets a distinct index/route; then add a W-only `expect_any` slice and measure lift.
3. **D-layer intrinsic quality** — no quality metric, only indirect coverage signals. →
   treat as a pre-flight ingestion lint (encoding / language-tag / parseability), not a
   scored dimension.
4. **Graph / wikilink retrieval leg** — experimental and off. → revisit when enabled;
   would extend ii/iv with link-traversal queries and reuse `wikilink_resolved_ratio`.

---

## 5. Appendix — verified interface reference (dikw-core v0.6.1)

**CLI.** `dikw {version,init,serve,auth}`; remote group `dikw client {info,health,status,
check,import,ingest,retrieve,synth,eval,wisdom,lint,pages,graph,assets,tasks,serve-and-run}`.
Common: `--server URL` (env `DIKW_SERVER_URL`, default `http://127.0.0.1:8765`),
`--token`, `--format json|table`, `--wait`.

**`dikw client eval` flags.** `--dataset <name|abs-path>`,
`--retrieval hybrid|bm25|vector|all`, `--eval retrieval|synth` (repeatable),
`--judge`, `--judge-sample N|auto`, `--cache read_write|rebuild|off`,
`--against <json>`, `--write-baseline <json>`, `--tolerance` (default 0.02),
`--wait`, `--pretty`, `--server`, `--token`. **Exit codes:** 0 all pass, 1 threshold/
regression fail, 2 bad spec / not found.

**Metric keys.** Retrieval: `hit_at_3`, `hit_at_10`, `mrr`, `ndcg_at_10`,
`recall_at_100` (views `doc/ chunk/ asset/`; per-mode `bm25/ vector/ hybrid/`).
Synth: `synth/fact_grounding_ratio`, `synth/atomicity_score`,
`synth/duplicate_ratio_max` (lower-better), `synth/wikilink_resolved_ratio`,
`synth/language_fidelity`, `synth/expected_coverage`, `synth/fact_entailment_ratio`
(judge); informational `synth/page_density`, `synth/source_chunk_coverage`,
`synth/fallback_ratio_max`, `synth/slug_merge_ratio_max`.

**Provider config (`dikw.yml` `provider:`).** Requires `llm`, `llm_model`,
`llm_base_url`, `llm_api_key_env`, `embedding` (only `openai_compat` ships),
`embedding_model`, `embedding_base_url`, `embedding_api_key_env`, `embedding_dim`
(locked at first ingest), `embedding_batch_size`. Storage: `sqlite` (default) or
`postgres`.

**Reusable dikw-core assets.** `evals/tools/ab_experiment.py` (A/B: collect baseline/
intervention N runs each → compare → `result.json` with p-value, Cohen's d, ships,
regressed); `evals/BASELINES.md` (dated reproducible baseline log);
`tools/check_baselines.py` + `.github/workflows/eval-gate.yml` (CI gate pattern);
`evals/tools/convert_beir.py` (materialize BEIR datasets); the snapshot cache at
`evals/.cache/snapshots`.

**Packaged datasets to reference / reuse.** `mvp` (3 docs, retrieval + synth, judges on),
`scifact` (BEIR English, nDCG@10 floor 0.67), `cmteb-t2-subset` (CMTEB Chinese),
`wiki-mini-mm` (multimodal chunk/asset, unthresholded).

---

## 6. Sources (industry practice)

- BEIR — Thakur et al. 2021, https://arxiv.org/abs/2104.08663
- MTEB / MMTEB — https://arxiv.org/abs/2502.13595
- MS MARCO (MRR@10 convention) — https://microsoft.github.io/msmarco/
- MIRACL / MIRACL-VISION — https://arxiv.org/abs/2505.11651
- RAGAS — https://arxiv.org/abs/2309.15217 ; https://docs.ragas.io
- TruLens RAG triad — https://www.trulens.org/getting_started/core_concepts/rag_triad/
- ARES — https://arxiv.org/abs/2311.09476
- ViDoRe / ColPali — https://arxiv.org/abs/2407.01449
- LLM-as-judge bias — https://www.trulens.org ; DeepEval judge guides (2026)

# Phase 1 follow-up: `domain-bilingual-v2` — the discriminative retrieval gate (design)

> **Status:** design draft for review (2026-06-28); implementation pending your sign-off.
> Implements the `domain-bilingual-v2` follow-up named in
> [`phase1-inhouse-datasets-design.md`](phase1-inhouse-datasets-design.md) §10 and in
> `datasets/domain-bilingual-v1/dataset.yaml`. Follows the threshold methodology in
> [`dikw-eval-plan.md`](dikw-eval-plan.md) §2.3 and the bilingual-split rule in §2.4.
> `dikw-core` stays **read-only**. Built in parallel with dikw-core#249/#250 — neither
> blocks this construction (only the final threshold calibration waits; see §6).

## 1. Context — why v2

`domain-bilingual-v1` landed (#7) but its own `dataset.yaml` records the problem: its
24 docs span ~10 **mutually-distinct** topics, so the vector/hybrid views **saturate at
1.0** — every query trivially retrieves its lone on-topic doc. The committed thresholds
are therefore a *high regression floor*, not a *discriminative benchmark*: they catch a
pipeline breakage but cannot detect a ranking-quality regression, which is exactly what
"the gate that matters" must measure.

`v2` fixes this at the **corpus** level (not by tuning anything): a denser corpus of
**deliberately intra-cluster-confusable** documents, so a query's gold doc must
*out-rank its near-neighbours*. That gives `ndcg_at_10` / `mrr` real signal while
`recall_at_100` still anchors pipeline health. The confusability is the whole point —
we engineer the corpus to be hard, then (§6) record observed and gate at
`observed − margin` per §2.3; we do **not** engineer queries to a target.

## 2. Decisions (proposed)

1. **New, denser corpus — not a reuse of v1.** v1's 16-line stubs across distinct
   topics cannot be made confusable by query wording alone. v2 is freshly authored as
   **8 topic clusters × ~7 docs = ~56 docs**, each doc ~250–500 words so chunking has
   substance and siblings genuinely overlap in vocabulary.
2. **Single dataset + recorded zh/en split** (same as v1, §2.4): `dataset.yaml
   thresholds:` is a flat map; zh/en metrics are recomputed offline from the run's
   NDJSON via the existing `tools/split_metrics_by_lang.py` and recorded in
   `reports/BASELINES.md`. **4 clusters are zh, 4 are en** (28/28), so the zh slice
   exercises the jieba/CJK path and the en slice does not — query language matches its
   gold doc's language.
3. **Confusability lives *within* a cluster, distinctness *across* clusters.** Sibling
   docs share vocabulary (a query must discriminate among them → ranking signal); the 8
   clusters are mutually distinct (→ `recall_at_100` stays healthy, the set isn't
   pathologically hard). This is the lever that de-saturates `ndcg`/`mrr` without making
   the floor meaningless.
4. **Generate with codex gpt-5.5 xhigh** (your choice): the corpus via
   `scripts/generate_bilingual_corpus.py --provider codex`, the confusable queries via
   `scripts/generate_candidates.py --provider codex` with `--instruction` steering. xhigh
   reasoning matters most for writing queries whose *wrong* answer is a plausible sibling.
5. **Calibration is deferred** to the single post-#249/#250 pass (Workstream D of the
   parallel plan). v2 ships with placeholder thresholds; gated only after a real-vector run.

## 3. Corpus design — 8 confusable clusters (~56 docs, 28 zh / 28 en)

Each cluster's docs are mutually confusable (shared terms, adjacent concepts), so a
well-crafted query about one doc has 6 plausible-but-wrong siblings. Stems are
`<cluster>-<slug>`; frontmatter carries `title`, `language`, `source:
openai-codex-synthetic`.

### zh clusters (jieba/CJK path) — 28 docs

| cluster (stem prefix) | ~7 docs | intra-cluster confusion axis |
|---|---|---|
| `tang` 唐朝制度与历史 | 建立 / 均田制 / 租庸调制 / 科举制 / 唐与西域 / 安史之乱 / 两税法 | 制度 vs 事件 vs 改革,同朝代术语高度重叠 |
| `china-money` 中国货币金融史 | 交子纸币 / 北宋通货膨胀 / 白银货币化 / 票号钱庄 / 盐引制度 / 青苗法 / 一条鞭法 | 货币工具 vs 财政改革,跨朝代但同主题 |
| `tcm` 中医基础理论 | 阴阳 / 五行 / 气血津液 / 经络 / 脏腑 / 四诊 / 辨证论治 | 理论概念互相引用、边界模糊 |
| `china-lit` 中国古典文学 | 红楼梦 / 三国演义 / 水浒传 / 西游记 / 唐诗 / 宋词 / 元曲 | 四大名著彼此混淆;诗词曲三体裁混淆 |

### en clusters (non-CJK path) — 28 docs

| cluster (stem prefix) | ~7 docs | intra-cluster confusion axis |
|---|---|---|
| `crypto` Cryptography | symmetric-key / public-key / hash-functions / digital-signatures / diffie-hellman / tls-handshake / block-vs-stream | key-exchange vs encryption vs integrity, shared jargon |
| `cell-energy` Cellular energy & photosynthesis | light-reactions / calvin-cycle / glycolysis / cellular-respiration / electron-transport-chain / chemiosmosis / photorespiration | overlapping biochemical pathways & molecules |
| `french-rev` French Revolution & Napoleonic era | causes / estates-general-1789 / reign-of-terror / thermidor / napoleon-rise / napoleonic-wars / congress-of-vienna | sequential phases of one era, shared actors |
| `macro-money` Money & inflation (macro) | money-supply / inflation-causes / central-bank-policy / interest-rates-yield-curve / quantitative-easing / phillips-curve / hyperinflation | interlocking macro concepts, shared vocabulary |

(Exact per-cluster doc count may flex 6–8 to keep each cluster internally coherent; total
stays ~56, zh/en stays balanced. Final stems are fixed at materialization.)

## 4. Query design — ~70 queries, deliberately confusable

- **Coverage:** every doc gets ≥ 1 positive; ~35 zh / ~35 en; ids prefixed `zh-` / `en-`
  (the `split_metrics_by_lang` contract), language matching the gold doc.
- **Confusable subset (≥ 40%):** queries phrased so a *sibling* doc is the plausible
  wrong top hit — e.g. `zh-tang-two-tax-vs-zuyongdiao`: "唐朝后期取代租庸调、按土地和资产
  征税的赋税制度是什么?" must rank `tang-两税法` above `tang-租庸调制`. These carry the
  `ndcg`/`mrr` signal.
- **`expect_any: [stem]`** single-gold positives (exactly-one-doc answers), per the
  contract. No `expect_none` here — negatives remain `negatives-ood-v1`'s job.
- Generated via `generate_candidates.py --provider codex --instruction "<cluster + confusability + language constraints>"`, then **human-verified** (you, via the `queries.yaml` PR diff): confirm the gold stem is the *uniquely correct* answer and siblings are genuinely wrong; drop ambiguous; dedup; rebalance zh/en.

## 5. Generation + verification workflow (no `dikw-core` calls)

1. **Scaffold** `datasets/domain-bilingual-v2/` (corpus dir + empty `queries.yaml` +
   `dataset.yaml` with placeholder thresholds).
2. **Generate corpus (codex):** per-cluster prompts to
   `generate_bilingual_corpus.py --provider codex`, one doc per stem, stamping
   `language:` and `source: openai-codex-synthetic`. Cluster prompts instruct codex to
   make siblings *overlap in vocabulary but differ in the answerable fact*.
3. **Generate queries (codex):** per-cluster `generate_candidates.py --provider codex
   --instruction …`, emphasizing the intra-cluster-confusable subset.
4. **Human-verify (maintainer):** curate `queries.yaml` — gold uniqueness, sibling
   wrongness, language tag, balance, dedup. Optional `scripts/llm_review.py` second pass.
5. **Validate ($0):** `scripts/validate_dataset.py datasets/domain-bilingual-v2` must pass.
6. **CI:** `datasets/**` change → the eval-gate workflow requires a new `BASELINES.md`
   entry (lands in §6's calibration commit).

## 6. Threshold calibration — deferred to the post-#249/#250 pass

Per the parallel plan's Workstream D, v2 joins the **single** real-vector calibration run
once dikw-core ships #249/#250:

- One run `scripts/run_eval.py --datasets …/domain-bilingual-v2 --retrieval all`
  (`--cache read_write`; cold-embed once). Confirm `summary.json worst_exit_code == 0`.
- `tools/split_metrics_by_lang.py` → zh/en split into `reports/BASELINES.md`.
- Gate `domain-bilingual-v2` at `observed − margin` (−0.05 `hit@k`/`mrr`, −0.03
  `ndcg`/`recall`), written into `dataset.yaml`.
- **De-saturation acceptance:** hybrid `ndcg_at_10` should land meaningfully **< 1.0**
  (the confusable design worked). If it still saturates, log it and densify further
  (more siblings per cluster) before gating.

Until then `dataset.yaml` carries placeholder thresholds and the dataset is observe-only.

## 7. Deliverables

- `datasets/domain-bilingual-v2/**` (corpus ~56 `.md` + `queries.yaml` + `dataset.yaml`).
- `reports/BASELINES.md` entry (added in the calibration commit, Workstream D).
- This design doc; a phase-note touch in `dikw-eval-plan.md` §2.2 (v2 row).
- Branch `eval/domain-bilingual-v2`; PR base `main`.

## 8. Risks

1. **Codex throughput / cost:** xhigh at concurrency 1 with 600s timeouts → ~56 docs is
   slow and real spend. Mitigation: generate per-cluster in batches with `--resume`; if
   time/cost bites, fall back to M3 for the *plainer* docs and keep codex for the
   confusable queries (your call at generation time).
2. **Over-confusability:** if siblings overlap so much that *no* query has a unique gold,
   `expect_any` becomes ill-defined. Mitigation: each doc must own ≥ 1 distinct
   answerable fact; the human-verify step rejects non-unique golds.
3. **Residual saturation:** distinct-cluster structure may still retrieve easily.
   Mitigation: the §6 de-saturation check gates whether v2 actually earned its purpose;
   densify if not.
4. **codex OAuth refresh_token rotation** (heavy generation): may invalidate the codex
   CLI login. Decouple first with `python -m dikw_data.codex_auth login`.

## 9. Acceptance criteria

- `validate_dataset.py` passes; `ruff` / `mypy src` / `pytest` green.
- ~56 docs, 28 zh / 28 en; every doc has ≥ 1 positive; ~35/~35 zh/en queries; ids
  prefixed `zh-`/`en-`; ≥ 40% intra-cluster-confusable.
- (Workstream D) calibration run `worst_exit_code == 0`; `BASELINES.md` entry with
  blended + zh/en split; hybrid `ndcg_at_10` de-saturated (< 1.0) or the limitation logged.

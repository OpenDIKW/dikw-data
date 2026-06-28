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

_None yet._ The first real entries come from the Phase 0→1 public-anchor
calibration (`scifact` + `cmteb-t2-subset`); see `docs/dikw-eval-plan.md` §2.3 and
`docs/phase0-smoke-results.md`. Phase 0 set **no gates** — the synthetic sets
saturate at 1.0, so thresholds wait for non-saturated, anchored data.

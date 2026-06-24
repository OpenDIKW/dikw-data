# dikw-data

Synthetic evaluation data and tooling for [`dikw-core`](https://github.com/helebest/dikw-core).

This repository is a data factory for retrieval evaluation. It contains curated
synthetic datasets, scripts for generating and cleaning data, a MiniMax-backed
LLM client with task-level retries, and a small web review UI.

## What Is Tracked

Tracked in Git:

- `datasets/`: versioned evaluation datasets consumed by `dikw-core`.
- `src/dikw_data/`: shared Python library code for config, LLM calls, retries,
  task IDs, and audit persistence.
- `scripts/`: generation, repair, cleaning, validation, and dataset maintenance
  commands.
- `web/`: local FastAPI review UI.
- `configs/`: non-secret provider and retry configuration.
- `tests/`: unit tests for retry and JSON-repair behavior.

Not tracked:

- `.env`: local API keys.
- `.venv/`, `.uv-cache/`, `.pytest_cache/`, `__pycache__/`: local runtime state.
- `generated/`: intermediate LLM outputs, audit databases, quarantined data, and
  deprecated generated artifacts.
- `reports/`: local evaluation reports.

## Setup

Install dependencies with `uv`:

```powershell
uv sync
```

Create a local `.env` from the example:

```powershell
Copy-Item .env.example .env
```

Then set:

```text
ANTHROPIC_API_KEY=your_minimax_key
```

MiniMax is called through its Anthropic-compatible endpoint. The endpoint,
model, timeout, retry, and concurrency settings live in
[`configs/minimax.yml`](configs/minimax.yml).

## Datasets

Current versioned datasets:

- `synthetic-diverse-v1`: small mixed-domain text retrieval dataset.
- `synthetic-diverse-v2`: expanded mixed-domain text retrieval dataset covering
  Chinese history, world history, science, medicine, law, finance, geography,
  literature, economics, and technology.
- `synthetic-multimodal-datasets-v1`: multimodal dataset with Markdown text,
  local PNG image assets, asset-level targets, single-image and multi-image
  chunk targets, and compatible doc-level query fields.

Dataset details and file formats are documented in
[`docs/dataset-format.md`](docs/dataset-format.md).

## Common Commands

Validate a dataset:

```powershell
uv run python scripts/validate_dataset.py datasets/synthetic-multimodal-datasets-v1
```

Run unit tests:

```powershell
uv run pytest
```

Generate with the MiniMax-backed pipeline:

```powershell
uv run python scripts/generate_factbook.py --dataset demo --topic "DIKW knowledge engine"
uv run python scripts/generate_corpus.py --dataset demo --resume
uv run python scripts/generate_candidates.py --dataset demo --resume
uv run python scripts/llm_review.py --dataset demo --resume
```

All LLM generation scripts support:

- `--resume`: skip successful tasks and continue unfinished work.
- `--retry-failed`: retry failed tasks.
- `--max-attempts N`: override configured retry attempts.
- `--concurrency N`: override configured concurrency.
- `--dry-run`: list tasks without calling the model.

Start the local review UI:

```powershell
uv run uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

The review UI can preview corpus Markdown, render local Markdown images, inspect
LLM generation audit status, run LLM quality review, review generated query
candidates, persist approve/reject/rewrite decisions in
`generated/<dataset>/review.sqlite`, and export approved items into
`datasets/<dataset>/queries.yaml`.

The web UI has two separate audit views:

- **LLM Generation Audit** reads MiniMax call status from
  `generated/<dataset>/audit.sqlite`.
- **LLM Quality Review** asks MiniMax to review corpus, queries, and target
  metadata, then writes review batches to
  `generated/<dataset>/quality_review.sqlite`.

Generation and maintenance workflows are documented in
[`docs/maintenance.md`](docs/maintenance.md).

## Evaluating dikw-core

`scripts/run_eval.py` orchestrates retrieval/synth evaluation of the read-only
`dikw-core` engine over the datasets in this repo, following
[`docs/dikw-eval-plan.md`](docs/dikw-eval-plan.md). It hands each dataset to the
engine by absolute path, captures the NDJSON `EvalReport` under `reports/`, and
writes a gate-able `summary.json`.

One-time prerequisites:

- Install the engine editable, with the CJK extra for Chinese BM25:
  `uv pip install -e "../dikw-core[cjk]"`.
- Put provider keys in `.env.eval` (gitignored): `MINIMAX_API_KEY`, `GITEE_API_KEY`.

Plan a run without spending anything (validates datasets, checks key names, prints
the exact commands):

```powershell
uv run python scripts/run_eval.py --dry-run
```

Run the default retrieval eval over every dataset (a one-shot server per dataset):

```powershell
uv run python scripts/run_eval.py --retrieval all
```

The eval base provider config lives in
[`configs/eval-base.dikw.yml`](configs/eval-base.dikw.yml) (MiniMax + Gitee
embeddings + sqlite); `run_eval.py` materialises it into the gitignored
`bases/eval-base/` on first run. Reports and bases stay out of Git.

## LLM Reliability

The shared client in [`src/dikw_data/llm_client.py`](src/dikw_data/llm_client.py)
adds a task-level retry layer on top of the Anthropic-compatible SDK:

- Retries 408, 409, 429, 5xx, 529, connection errors, and read timeouts.
- Does not blindly retry authentication errors or schema-level bad requests.
- Uses exponential backoff with optional jitter.
- Repairs malformed JSON once with the same model.
- Persists task status in `generated/<dataset>/audit.sqlite`.
- Uses stable task IDs for resume and retry workflows.

## Evaluation Notes

The macro evaluation plan for the `dikw-core` engine — engineering pipeline,
environment deployment, eval dimensions, and dataset construction — is documented in
[`docs/dikw-eval-plan.md`](docs/dikw-eval-plan.md). It is the cornerstone for
building `dikw` evaluation datasets.

The current `dikw-core` runner is doc-level. For multimodal datasets,
`expect_any` remains for compatibility smoke tests, but real multimodal quality
should be measured with asset/chunk-level metrics such as:

- `asset_hit_at_3`
- `asset_hit_at_10`
- `asset_mrr`
- `chunk_hit_at_3`
- `chunk_hit_at_10`
- `chunk_mrr`

## GitHub Publishing Checklist

Before pushing publicly:

1. Confirm `.env` is ignored and contains no committed history.
2. Keep `generated/` out of Git unless a specific artifact is intentionally
   promoted into `datasets/`.
3. Run `uv run pytest`.
4. Run `scripts/validate_dataset.py` for each dataset touched.
5. Add a repository license before public reuse.

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
  local PNG image assets, asset-level targets, chunk-level targets, and
  compatible doc-level query fields.

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
LLM audit status, review generated query candidates, persist approve/reject/
rewrite decisions in `generated/<dataset>/review.sqlite`, and export approved
items into `datasets/<dataset>/queries.yaml`.

Generation and maintenance workflows are documented in
[`docs/maintenance.md`](docs/maintenance.md).

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

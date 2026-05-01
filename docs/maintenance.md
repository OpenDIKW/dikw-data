# Maintenance Guide

This guide covers local data generation, review, validation, and GitHub
publishing hygiene.

## Environment

Install dependencies:

```powershell
uv sync
```

Create `.env`:

```powershell
Copy-Item .env.example .env
```

Set:

```text
ANTHROPIC_API_KEY=your_minimax_key
```

Do not commit `.env`.

## LLM Generation Workflow

The LLM-backed pipeline writes intermediate results to `generated/<dataset>/`
and promotes reviewed, usable data into `datasets/<dataset>/`.

Typical flow:

```powershell
uv run python scripts/generate_factbook.py --dataset demo --topic "DIKW knowledge engine"
uv run python scripts/generate_corpus.py --dataset demo --resume
uv run python scripts/generate_candidates.py --dataset demo --resume
uv run python scripts/llm_review.py --dataset demo --resume
```

Use `--dry-run` before long jobs:

```powershell
uv run python scripts/generate_corpus.py --dataset demo --dry-run
```

Use `--retry-failed` to retry only failed tasks:

```powershell
uv run python scripts/generate_candidates.py --dataset demo --retry-failed
```

## Retry And Audit Behavior

LLM tasks are identified by stable task IDs derived from dataset, stage, source
hash, and prompt version. Results are persisted in:

```text
generated/<dataset>/audit.sqlite
```

The shared client retries transient MiniMax failures, repairs malformed JSON
once, and records permanent failures for manual inspection. This avoids
restarting long data-generation jobs after one network or rate-limit failure.

## Review UI

Start the local web UI:

```powershell
uv run uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

The UI previews corpus files and shows LLM audit status where an audit database
exists. It is intended for local review and should not be exposed publicly.

## Corpus Quality Workflow

Useful maintenance scripts:

```powershell
uv run python scripts/audit_corpus_quality.py datasets/synthetic-diverse-v2
uv run python scripts/clean_corpus.py datasets/synthetic-diverse-v2
uv run python scripts/validate_dataset.py datasets/synthetic-diverse-v2
```

Promote only cleaned and validated data into `datasets/`. Keep rejected,
quarantined, or deprecated generated data under `generated/`.

## Multimodal Dataset Maintenance

The unified multimodal dataset is:

```text
datasets/synthetic-multimodal-datasets-v1
```

It currently contains category Markdown files, local PNG images, asset targets,
chunk targets, and paired asset/text queries. To update it, regenerate or append
through scripts, then validate:

```powershell
uv run python scripts/validate_dataset.py datasets/synthetic-multimodal-datasets-v1
```

Current doc-level `dikw-core` evaluation is only a compatibility smoke test for
multimodal data. Formal multimodal quality should use asset/chunk-level metrics
once the runner supports them.

## Git Hygiene

Commit these:

- `datasets/`
- `src/`
- `scripts/`
- `tests/`
- `web/`
- `configs/`
- `docs/`
- `README.md`
- `pyproject.toml`
- `uv.lock`

Do not commit these:

- `.env`
- `.venv/`
- `.uv-cache/`
- `.pytest_cache/`
- `__pycache__/`
- `generated/`
- `reports/`

Before pushing:

```powershell
uv run pytest
uv run python scripts/validate_dataset.py datasets/synthetic-diverse-v1
uv run python scripts/validate_dataset.py datasets/synthetic-diverse-v2
uv run python scripts/validate_dataset.py datasets/synthetic-multimodal-datasets-v1
git status --short --ignored
```

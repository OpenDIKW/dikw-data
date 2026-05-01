# dikw-data

LLM-assisted evaluation data factory for `dikw-core`.

This project generates synthetic corpora and retrieval-evaluation queries, then
exports datasets in the three-file shape consumed by `dikw-core`:

```text
dataset.yaml
corpus/
queries.yaml
```

MiniMax is accessed through its Anthropic-compatible endpoint. Secrets live in
`.env`; non-secret provider and retry settings live in `configs/minimax.yml`.

## Common Commands

```powershell
uv run python scripts/generate_factbook.py --dataset demo --topic "DIKW knowledge engine"
uv run python scripts/generate_corpus.py --dataset demo
uv run python scripts/generate_candidates.py --dataset demo
uv run python scripts/llm_review.py --dataset demo
```

All LLM scripts support `--resume`, `--retry-failed`, `--max-attempts`,
`--concurrency`, and `--dry-run`.


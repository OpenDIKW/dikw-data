from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dikw_data.pipeline import add_common_args, dataset_dir, prompt_task, run_tasks_from_cli


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate retrieval query candidates.")
    add_common_args(parser)
    parser.add_argument("--queries", type=int, default=30)
    parser.add_argument(
        "--instruction",
        default="",
        help="Extra steering appended to the prompt (e.g. positives-only, "
        "coverage/balance, or expect_none-only constraints).",
    )
    args = parser.parse_args()

    corpus_dir = dataset_dir(args.dataset) / "corpus"
    corpus = _read_corpus(corpus_dir)
    extra = f"{args.instruction.strip()}\n\n" if args.instruction.strip() else ""
    system = "You generate retrieval-evaluation query candidates with exact document stems."
    user = (
        f"Generate {args.queries} retrieval query candidates from this corpus. "
        "Return a JSON array. Each object must include q, type, expect_any, evidence, "
        "confidence, and rationale. Use expect_none=true for out-of-domain negatives. "
        "expect_any values must be file stems from the corpus.\n\n"
        f"{extra}"
        f"{corpus}"
    )
    task = prompt_task(
        dataset=args.dataset,
        stage="generate_candidates",
        prompt_version="v1",
        system=system,
        user=user,
        source=corpus or f"{args.dataset}:{args.queries}",
    )
    return run_tasks_from_cli(args, [task])


def _read_corpus(corpus_dir: Path) -> str:
    parts: list[str] = []
    if not corpus_dir.is_dir():
        return ""
    for path in sorted(corpus_dir.rglob("*")):
        if path.suffix.lower() not in {".md", ".html", ".htm"}:
            continue
        parts.append(f"\n\n# STEM: {path.stem}\n{path.read_text(encoding='utf-8')}")
    return "".join(parts)


if __name__ == "__main__":
    sys.exit(main())


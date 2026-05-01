from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dikw_data.pipeline import add_common_args, prompt_task, run_tasks_from_cli


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate corpus documents from a factbook.")
    add_common_args(parser)
    parser.add_argument("--factbook", default=None)
    parser.add_argument("--docs", type=int, default=12)
    args = parser.parse_args()

    factbook_path = Path(args.factbook) if args.factbook else Path("generated") / args.dataset / f"{args.dataset}.jsonl"
    source = factbook_path.read_text(encoding="utf-8") if factbook_path.is_file() else ""
    system = "You write Markdown documents for synthetic retrieval evaluation corpora."
    user = (
        f"Using the factbook records below, write {args.docs} Markdown documents. "
        "Return a JSON array of objects with stem, title, markdown, and covered_fact_ids. "
        "Include a few related distractor documents that are similar but not equivalent.\n\n"
        f"{source}"
    )
    task = prompt_task(
        dataset=args.dataset,
        stage="generate_corpus",
        prompt_version="v1",
        system=system,
        user=user,
        source=source or f"{args.dataset}:{args.docs}",
    )
    return run_tasks_from_cli(args, [task])


if __name__ == "__main__":
    sys.exit(main())


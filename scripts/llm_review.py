from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dikw_data.pipeline import add_common_args, prompt_task, run_tasks_from_cli


def main() -> int:
    parser = argparse.ArgumentParser(description="Review query candidates with a second LLM pass.")
    add_common_args(parser)
    parser.add_argument("--candidates", default=None)
    args = parser.parse_args()

    candidates_path = Path(args.candidates) if args.candidates else Path("generated") / args.dataset / f"{args.dataset}.jsonl"
    candidates = candidates_path.read_text(encoding="utf-8") if candidates_path.is_file() else ""
    system = "You are a strict reviewer for retrieval-evaluation datasets."
    user = (
        "Review these candidate query records. Return a JSON array with task-local "
        "review decisions. Each object must include q, decision, reason, corrected_q, "
        "corrected_expect_any, and risk_flags. decision must be pass, fail, or rewrite.\n\n"
        f"{candidates}"
    )
    task = prompt_task(
        dataset=args.dataset,
        stage="llm_review",
        prompt_version="v1",
        system=system,
        user=user,
        source=candidates or args.dataset,
    )
    return run_tasks_from_cli(args, [task])


if __name__ == "__main__":
    sys.exit(main())


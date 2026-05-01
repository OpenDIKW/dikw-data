from __future__ import annotations

import argparse
import sys

from dikw_data.pipeline import add_common_args, prompt_task, run_tasks_from_cli


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a synthetic factbook.")
    add_common_args(parser)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--items", type=int, default=30)
    args = parser.parse_args()

    system = "You create grounded synthetic facts for retrieval evaluation datasets."
    user = (
        f"Create {args.items} synthetic factbook entries for topic: {args.topic}. "
        "Return a JSON array. Each object must include id, theme, fact, entities, "
        "intended_doc_stems, and query_angles."
    )
    task = prompt_task(
        dataset=args.dataset,
        stage="generate_factbook",
        prompt_version="v1",
        system=system,
        user=user,
        source=f"{args.topic}:{args.items}",
    )
    return run_tasks_from_cli(args, [task])


if __name__ == "__main__":
    sys.exit(main())


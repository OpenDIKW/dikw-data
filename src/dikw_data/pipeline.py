"""Shared CLI helpers for the generation scripts."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from .audit import AuditStore
from .config import load_minimax_config
from .llm_client import RetryingMiniMaxClient
from .tasks import LLMTask, hash_text


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--max-attempts", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")


def run_tasks_from_cli(args: argparse.Namespace, tasks: list[LLMTask]) -> int:
    config = load_minimax_config()
    audit = AuditStore(args.dataset)
    client = RetryingMiniMaxClient(config=config, audit=audit)
    results = asyncio.run(
        client.run_many(
            tasks,
            concurrency=args.concurrency,
            resume=args.resume,
            retry_failed=args.retry_failed,
            max_attempts=args.max_attempts,
            dry_run=args.dry_run,
        )
    )
    for result in results:
        print(
            json.dumps(
                {
                    "task_id": result.task_id,
                    "status": result.status,
                    "attempts": result.attempts,
                    "skipped": result.skipped,
                    "error": result.error,
                },
                ensure_ascii=False,
            )
        )
    return 1 if any(r.status in {"failed", "needs_manual_review"} for r in results) else 0


def dataset_dir(dataset: str) -> Path:
    return Path("datasets") / dataset


def prompt_task(
    *,
    dataset: str,
    stage: str,
    prompt_version: str,
    system: str,
    user: str,
    source: str,
) -> LLMTask:
    return LLMTask(
        dataset=dataset,
        stage=stage,
        source_hash=hash_text(source),
        prompt_version=prompt_version,
        system=system,
        user=user,
        expected_json=True,
    )


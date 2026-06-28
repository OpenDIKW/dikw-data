from __future__ import annotations

import asyncio
from pathlib import Path

from dikw_data.audit import AuditStore
from dikw_data.config import MiniMaxConfig, RetryPolicy
from dikw_data.llm_client import MiniMaxCallError, RetryingMiniMaxClient
from dikw_data.tasks import LLMTask


class FakeTransport:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    async def complete(self, *, system: str, user: str, model: str) -> str:
        _ = (system, user, model)
        outcome = self.outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, BaseException):
            raise outcome
        return str(outcome)


async def no_sleep(seconds: float) -> None:
    _ = seconds


def make_config() -> MiniMaxConfig:
    return MiniMaxConfig(
        model="MiniMax-M3",
        base_url="https://api.minimaxi.com/anthropic",
        timeout_seconds=120,
        sdk_max_retries=0,
        retry_policy=RetryPolicy(
            max_attempts=4,
            initial_backoff_seconds=0,
            max_backoff_seconds=0,
            jitter=False,
            timeout_seconds=120,
        ),
        concurrency=2,
    )


def make_task(stage: str = "test") -> LLMTask:
    return LLMTask(
        dataset="demo",
        stage=stage,
        source_hash="abc",
        prompt_version="v1",
        system="system",
        user="user",
    )


def test_retries_retryable_status_then_succeeds(tmp_path: Path) -> None:
    audit = AuditStore("demo", tmp_path)
    transport = FakeTransport(
        [
            MiniMaxCallError("rate limited", status_code=429),
            MiniMaxCallError("overloaded", status_code=529),
            '{"ok": true}',
        ]
    )
    client = RetryingMiniMaxClient(
        config=make_config(), audit=audit, transport=transport, sleep=no_sleep
    )

    result = asyncio.run(client.run_task(make_task()))

    assert result.status == "succeeded"
    assert result.attempts == 3
    assert result.result == {"ok": True}
    assert transport.calls == 3


def test_does_not_retry_non_retryable_status(tmp_path: Path) -> None:
    audit = AuditStore("demo", tmp_path)
    transport = FakeTransport([MiniMaxCallError("bad auth", status_code=401)])
    client = RetryingMiniMaxClient(
        config=make_config(), audit=audit, transport=transport, sleep=no_sleep
    )

    result = asyncio.run(client.run_task(make_task()))

    assert result.status == "failed"
    assert result.attempts == 1
    assert transport.calls == 1


def test_empty_response_is_retried(tmp_path: Path) -> None:
    audit = AuditStore("demo", tmp_path)
    transport = FakeTransport(["", '{"ok": true}'])
    client = RetryingMiniMaxClient(
        config=make_config(), audit=audit, transport=transport, sleep=no_sleep
    )

    result = asyncio.run(client.run_task(make_task()))

    assert result.status == "succeeded"
    assert result.attempts == 2
    assert result.result == {"ok": True}


def test_json_parse_failure_triggers_one_repair(tmp_path: Path) -> None:
    audit = AuditStore("demo", tmp_path)
    transport = FakeTransport(["not json", '{"fixed": true}'])
    client = RetryingMiniMaxClient(
        config=make_config(), audit=audit, transport=transport, sleep=no_sleep
    )

    result = asyncio.run(client.run_task(make_task()))

    assert result.status == "succeeded"
    assert result.result == {"fixed": True}
    assert transport.calls == 2


def test_fenced_json_does_not_trigger_repair(tmp_path: Path) -> None:
    audit = AuditStore("demo", tmp_path)
    transport = FakeTransport(['```json\n{"ok": true}\n```'])
    client = RetryingMiniMaxClient(
        config=make_config(), audit=audit, transport=transport, sleep=no_sleep
    )

    result = asyncio.run(client.run_task(make_task()))

    assert result.status == "succeeded"
    assert result.result == {"ok": True}
    assert transport.calls == 1


def test_failed_after_max_attempts_is_recorded(tmp_path: Path) -> None:
    audit = AuditStore("demo", tmp_path)
    transport = FakeTransport(
        [
            MiniMaxCallError("server", status_code=500),
            MiniMaxCallError("server", status_code=500),
        ]
    )
    client = RetryingMiniMaxClient(
        config=make_config(), audit=audit, transport=transport, sleep=no_sleep
    )

    task = make_task()
    result = asyncio.run(client.run_task(task, max_attempts=2))
    record = audit.get(task.task_id)

    assert result.status == "failed"
    assert result.attempts == 2
    assert record is not None
    assert record.status == "failed"


def test_resume_skips_successful_task(tmp_path: Path) -> None:
    audit = AuditStore("demo", tmp_path)
    task = make_task()
    audit.record_finished(
        task_id=task.task_id,
        dataset=task.dataset,
        stage=task.stage,
        status="succeeded",
        attempts=1,
        raw_response='{"ok": true}',
        result_json={"ok": True},
        last_error=None,
    )
    transport = FakeTransport(['{"should_not": "run"}'])
    client = RetryingMiniMaxClient(
        config=make_config(), audit=audit, transport=transport, sleep=no_sleep
    )

    result = asyncio.run(client.run_task(task, resume=True))

    assert result.skipped is True
    assert result.status == "succeeded"
    assert transport.calls == 0

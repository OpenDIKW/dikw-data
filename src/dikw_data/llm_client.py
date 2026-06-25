"""Task-level MiniMax client with retries, JSON repair, and audit logging."""

from __future__ import annotations

import asyncio
import json
import random
import re
from dataclasses import dataclass
from typing import Any, Protocol

from .audit import FAILED, NEEDS_MANUAL_REVIEW, TERMINAL_SUCCESS, AuditStore
from .config import LLMConfig, get_required_env
from .tasks import LLMTask

RETRYABLE_STATUSES = {408, 409, 429, 529}
NON_RETRYABLE_STATUSES = {400, 401, 403}


class MiniMaxCallError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class LLMTransport(Protocol):
    async def complete(self, *, system: str, user: str, model: str) -> str:
        """Return the raw text response from the provider."""


# Backward-compat alias — the seam predates multi-provider support.
MiniMaxTransport = LLMTransport


class AnthropicTransport:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout_seconds: float,
        max_retries: int,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            import httpx
            from anthropic import AsyncAnthropic

            timeout = httpx.Timeout(
                connect=10.0,
                read=self.timeout_seconds,
                write=self.timeout_seconds,
                pool=5.0,
            )
            self._client = AsyncAnthropic(
                api_key=self.api_key,
                base_url=self.base_url,
                max_retries=self.max_retries,
                timeout=timeout,
                http_client=httpx.AsyncClient(
                    timeout=timeout,
                    limits=httpx.Limits(max_keepalive_connections=0),
                ),
            )
        return self._client

    async def complete(self, *, system: str, user: str, model: str) -> str:
        client = self._get_client()
        try:
            response = await client.messages.create(
                model=model,
                system=system,
                messages=[{"role": "user", "content": user}],
                max_tokens=4096,
                temperature=0.2,
            )
        except Exception as e:  # SDK exception types differ across versions.
            status = getattr(e, "status_code", None)
            raise MiniMaxCallError(str(e), status_code=status) from e

        parts: list[str] = []
        for block in response.content:
            text = getattr(block, "text", None)
            if isinstance(text, str):
                parts.append(text)
        return "".join(parts)


# Backward-compat alias.
AnthropicMiniMaxTransport = AnthropicTransport


def build_transport(config: LLMConfig) -> LLMTransport:
    """Construct the transport for ``config.llm``.

    ``anthropic_compat`` covers MiniMax / DeepSeek (Anthropic-compatible HTTP);
    ``openai_codex`` is the ChatGPT codex Responses API over OAuth.
    """
    if config.llm == "openai_codex":
        # Lazy import: codex_transport imports MiniMaxCallError from this
        # module, so a top-level import would be circular.
        from .codex_transport import CodexResponsesTransport

        return CodexResponsesTransport(
            base_url=config.base_url,
            reasoning_effort=config.reasoning_effort,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.sdk_max_retries,
        )
    # Accept the legacy "anthropic" spelling alongside "anthropic_compat".
    if config.llm in ("anthropic_compat", "anthropic"):
        return AnthropicTransport(
            api_key=get_required_env(config.llm_api_key_env),
            base_url=config.base_url,
            timeout_seconds=config.timeout_seconds,
            max_retries=config.sdk_max_retries,
        )
    raise ValueError(f"unknown provider llm: {config.llm!r}")


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    status: str
    attempts: int
    result: dict[str, Any] | list[Any] | None
    raw_response: str | None
    error: str | None = None
    skipped: bool = False


class RetryingMiniMaxClient:
    def __init__(
        self,
        *,
        config: LLMConfig,
        audit: AuditStore,
        transport: LLMTransport | None = None,
        sleep: Any = asyncio.sleep,
    ) -> None:
        self.config = config
        self.audit = audit
        self.transport = transport or build_transport(config)
        self._sleep = sleep
        self._consecutive_rate_limits = 0

    async def run_task(
        self,
        task: LLMTask,
        *,
        resume: bool = False,
        retry_failed: bool = False,
        max_attempts: int | None = None,
        dry_run: bool = False,
    ) -> TaskResult:
        if dry_run:
            return TaskResult(
                task_id=task.task_id,
                status="dry_run",
                attempts=0,
                result=None,
                raw_response=None,
                skipped=True,
            )
        if self.audit.should_skip(task.task_id, resume=resume, retry_failed=retry_failed):
            record = self.audit.get(task.task_id)
            return TaskResult(
                task_id=task.task_id,
                status=record.status if record else TERMINAL_SUCCESS,
                attempts=record.attempts if record else 0,
                result=record.result_json if record else None,
                raw_response=record.raw_response if record else None,
                skipped=True,
            )

        self.audit.record_started(task_id=task.task_id, dataset=task.dataset, stage=task.stage)
        attempts_budget = max_attempts or self.config.retry_policy.max_attempts
        raw: str | None = None
        try:
            raw, attempts = await self._complete_with_retry(task, attempts_budget=attempts_budget)
        except Exception as e:
            error = str(e)
            attempts = attempts_budget if _is_retryable_exception(e) else 1
            self.audit.record_finished(
                task_id=task.task_id,
                dataset=task.dataset,
                stage=task.stage,
                status=FAILED,
                attempts=attempts,
                raw_response=raw,
                result_json=None,
                last_error=error,
            )
            return TaskResult(task.task_id, FAILED, attempts, None, raw, error)

        if not task.expected_json:
            result = {"text": raw}
            self.audit.record_finished(
                task_id=task.task_id,
                dataset=task.dataset,
                stage=task.stage,
                status=TERMINAL_SUCCESS,
                attempts=attempts,
                raw_response=raw,
                result_json=result,
                last_error=None,
            )
            return TaskResult(task.task_id, TERMINAL_SUCCESS, attempts, result, raw)

        parsed, parse_error = _parse_json(raw)
        if parsed is None:
            repaired_raw = await self._repair_json(task=task, broken_json=raw)
            parsed, parse_error = _parse_json(repaired_raw)
            raw = repaired_raw

        if parsed is None:
            self.audit.record_finished(
                task_id=task.task_id,
                dataset=task.dataset,
                stage=task.stage,
                status=NEEDS_MANUAL_REVIEW,
                attempts=attempts,
                raw_response=raw,
                result_json=None,
                last_error=parse_error,
            )
            return TaskResult(
                task.task_id,
                NEEDS_MANUAL_REVIEW,
                attempts,
                None,
                raw,
                parse_error,
            )

        self.audit.record_finished(
            task_id=task.task_id,
            dataset=task.dataset,
            stage=task.stage,
            status=TERMINAL_SUCCESS,
            attempts=attempts,
            raw_response=raw,
            result_json=parsed,
            last_error=None,
        )
        return TaskResult(task.task_id, TERMINAL_SUCCESS, attempts, parsed, raw)

    async def run_many(
        self,
        tasks: list[LLMTask],
        *,
        concurrency: int | None = None,
        resume: bool = False,
        retry_failed: bool = False,
        max_attempts: int | None = None,
        dry_run: bool = False,
    ) -> list[TaskResult]:
        limit = concurrency or self.config.concurrency
        semaphore = asyncio.Semaphore(limit)

        async def run_one(task: LLMTask) -> TaskResult:
            async with semaphore:
                return await self.run_task(
                    task,
                    resume=resume,
                    retry_failed=retry_failed,
                    max_attempts=max_attempts,
                    dry_run=dry_run,
                )

        return await asyncio.gather(*(run_one(task) for task in tasks))

    async def _complete_with_retry(
        self, task: LLMTask, *, attempts_budget: int
    ) -> tuple[str, int]:
        last_error: Exception | None = None
        for attempt in range(1, attempts_budget + 1):
            try:
                text = await self.transport.complete(
                    system=task.system,
                    user=_strict_json_user_prompt(task.user) if task.expected_json else task.user,
                    model=self.config.model,
                )
                if not text.strip():
                    raise MiniMaxCallError("empty response from MiniMax")
                self._consecutive_rate_limits = 0
                return text, attempt
            except Exception as e:
                last_error = e
                if _status_code(e) == 429:
                    self._consecutive_rate_limits += 1
                if not _is_retryable_exception(e) or attempt >= attempts_budget:
                    raise
                await self._sleep(self._backoff_seconds(attempt))
                if self._consecutive_rate_limits >= self.config.rate_limit_slowdown_after:
                    await self._sleep(
                        min(
                            self.config.retry_policy.max_backoff_seconds,
                            self.config.retry_policy.initial_backoff_seconds
                            * self._consecutive_rate_limits,
                        )
                    )
        raise last_error or MiniMaxCallError("MiniMax call failed")

    async def _repair_json(self, *, task: LLMTask, broken_json: str) -> str:
        repair_user = (
            "Repair the following text into valid JSON only. Do not add markdown, "
            "comments, or explanation. Preserve all fields and values when possible.\n\n"
            f"{broken_json}"
        )
        try:
            text, _ = await self._complete_with_retry(
                LLMTask(
                    dataset=task.dataset,
                    stage=f"{task.stage}:repair_json",
                    source_hash=task.source_hash,
                    prompt_version=task.prompt_version,
                    system="You repair malformed JSON and output strict JSON only.",
                    user=repair_user,
                    expected_json=False,
                ),
                attempts_budget=1,
            )
            return text
        except Exception:
            return broken_json

    def _backoff_seconds(self, attempt: int) -> float:
        policy = self.config.retry_policy
        # Annotated float because ``2 ** (attempt - 1)`` (int ** int) is typed Any
        # in typeshed — negative exponents yield a float — which otherwise widens
        # ``base`` and both returns to Any under strict mypy.
        base: float = min(
            policy.max_backoff_seconds,
            policy.initial_backoff_seconds * (2 ** (attempt - 1)),
        )
        if not policy.jitter:
            return base
        return random.uniform(base * 0.5, base * 1.5)


def _strict_json_user_prompt(user: str) -> str:
    return (
        f"{user}\n\n"
        "Return strict JSON only. Do not wrap the result in markdown fences. "
        "Do not include commentary outside the JSON value."
    )


def _parse_json(text: str) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    text = _extract_json_text(text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        return None, f"JSON parse failed: {e}"
    if not isinstance(parsed, (dict, list)):
        return None, "JSON root must be an object or array"
    return parsed, None


def _extract_json_text(text: str) -> str:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    if stripped.startswith("{") or stripped.startswith("["):
        return stripped
    candidates: list[tuple[int, int]] = []
    for open_char, close_char in (("{", "}"), ("[", "]")):
        start = stripped.find(open_char)
        end = stripped.rfind(close_char)
        if start != -1 and end > start:
            candidates.append((start, end + 1))
    if not candidates:
        return stripped
    start, end = min(candidates, key=lambda span: span[0])
    return stripped[start:end]


def _status_code(error: BaseException) -> int | None:
    status = getattr(error, "status_code", None)
    return int(status) if isinstance(status, int) else None


def _is_retryable_exception(error: BaseException) -> bool:
    status = _status_code(error)
    if status in NON_RETRYABLE_STATUSES:
        return False
    if status in RETRYABLE_STATUSES:
        return True
    if status is not None and status >= 500:
        return True
    # Network and timeout errors often have no stable SDK status code.
    return status is None

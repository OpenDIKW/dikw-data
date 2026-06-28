"""OpenAI Codex transport — ChatGPT-backend Responses API over OAuth.

Ported (trimmed) from dikw-core's ``providers/openai_codex.py`` and adapted to
dikw-data's ``LLMTransport`` seam: ``complete(system, user, model) -> str``.
Slotting in here lets ``RetryingMiniMaxClient`` reuse its retry / backoff /
audit / JSON-repair machinery unchanged.

Codex differs from a plain OpenAI-compatible endpoint:
  * speaks the **Responses API**, streaming-only — a non-streaming call comes
    back ``Stream must be set to true``, so ``complete`` collapses a stream;
  * authenticates with a ChatGPT-issued OAuth access_token (resolved +
    refreshed via :mod:`dikw_data.codex_auth`, not ``OPENAI_API_KEY``);
  * requires Cloudflare-mitigation headers (``originator``,
    ``ChatGPT-Account-ID`` from the JWT);
  * rejects ``temperature`` / ``max_output_tokens`` (400 Unsupported parameter)
    — length and sampling are managed server-side by the plan/model.

Unlike dikw-core, this transport DOES send ``reasoning.effort`` on the wire so
``xhigh`` is honoured (the codex CLI sets it the same way against the same
backend); dikw-core left effort at the backend default.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .codex_auth import (
    DEFAULT_CODEX_BASE_URL,
    account_id_from_jwt,
    default_base,
    resolve_access_token,
)
from .llm_client import MiniMaxCallError

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import AsyncIterator

    from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Cloudflare requires these on every chatgpt.com/backend-api/codex request —
# without them the gateway 403s before reaching the model. ``originator`` must
# match the literal string the codex CLI reports.
_CODEX_BASE_HEADERS: dict[str, str] = {
    "originator": "codex_cli_rs",
    "User-Agent": "codex_cli_rs/0.1 (dikw-data)",
}

# Signature of the openai SDK reducer failure when the codex backend ships
# ``response.output = None`` in its terminal ``response.completed`` event. We
# refuse to swallow any other TypeError/AttributeError so a real None-attribute
# bug in our own code surfaces instead of being absorbed as a fake success.
_REDUCER_BUG_TYPE_ERROR_SIGNATURE = "'NoneType' object is not iterable"
_REDUCER_BUG_ATTR_ERROR_SIGNATURES: tuple[str, ...] = (
    "attribute 'output'",
    'attribute "output"',
)


def _is_codex_final_response_reducer_bug(exc: BaseException) -> bool:
    """True iff ``exc`` is the openai SDK reducer's failure on
    ``response.output = None`` from the codex backend (pinned to the ``output``
    field boundary so unrelated schema errors propagate)."""
    msg = str(exc)
    if isinstance(exc, TypeError):
        return _REDUCER_BUG_TYPE_ERROR_SIGNATURE in msg
    if isinstance(exc, AttributeError):
        return any(sig in msg for sig in _REDUCER_BUG_ATTR_ERROR_SIGNATURES)
    return False


def build_no_keepalive_async_client(timeout_seconds: float | None) -> tuple[Any, Any]:
    """httpx client with TCP keepalive disabled (fresh connection per request).

    Idle keepalive connections to the codex gateway get silently dropped
    mid-batch; forcing a fresh connection avoids retry storms on stale sockets.
    """
    import httpx

    timeout = httpx.Timeout(
        connect=10.0,
        read=timeout_seconds,
        write=timeout_seconds,
        pool=5.0,
    )
    client = httpx.AsyncClient(
        timeout=timeout,
        limits=httpx.Limits(max_keepalive_connections=0),
    )
    return timeout, client


def _build_async_client(
    *,
    base_url: str,
    access_token: str,
    max_retries: int | None,
    timeout_seconds: float | None,
) -> AsyncOpenAI:
    """Build a per-request ``AsyncOpenAI``.

    Rebuilt per call rather than cached: the OAuth access_token is short-lived,
    and a client cached across a refresh would silently 401.
    """
    from openai import AsyncOpenAI

    headers: dict[str, str] = dict(_CODEX_BASE_HEADERS)
    account_id = account_id_from_jwt(access_token)
    if account_id is not None:
        headers["ChatGPT-Account-ID"] = account_id

    timeout, http_client = build_no_keepalive_async_client(timeout_seconds)
    kwargs: dict[str, Any] = {
        "api_key": access_token,
        "base_url": base_url,
        "default_headers": headers,
        "timeout": timeout,
        "http_client": http_client,
    }
    if max_retries is not None:
        kwargs["max_retries"] = max_retries
    return AsyncOpenAI(**kwargs)


def _extract_text_from_response(response: Any) -> str:
    """Gather ``output_text`` from ``message`` items in ``response.output``.

    Reasoning / tool_call / other type-tagged items are skipped — only message
    items carry user-facing text.
    """
    parts: list[str] = []
    output = getattr(response, "output", None) or []
    for item in output:
        if getattr(item, "type", None) != "message":
            continue
        content = getattr(item, "content", None) or []
        for part in content:
            if getattr(part, "type", None) == "output_text":
                text = getattr(part, "text", None)
                if isinstance(text, str):
                    parts.append(text)
    return "".join(parts)


def _request_kwargs(
    *, system: str, user: str, model: str, reasoning_effort: str | None
) -> dict[str, Any]:
    """Wire payload for ``client.responses.stream(...)``.

    ``temperature`` / ``max_output_tokens`` are deliberately omitted — the codex
    backend rejects them. ``reasoning.effort`` is sent when configured so xhigh
    is honoured.
    """
    kwargs: dict[str, Any] = {
        "model": model,
        "instructions": system,
        "input": [
            {"role": "user", "content": [{"type": "input_text", "text": user}]}
        ],
        "store": False,
    }
    if reasoning_effort:
        kwargs["reasoning"] = {"effort": reasoning_effort}
    return kwargs


class CodexResponsesTransport:
    """``LLMTransport`` implementation backed by the ChatGPT codex Responses API."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_CODEX_BASE_URL,
        base_root: Path | None = None,
        reasoning_effort: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        self._base_url = base_url
        self._base_root = base_root or default_base()
        self._reasoning_effort = reasoning_effort
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[AsyncOpenAI]:
        """Resolve a fresh access_token, build a per-request client, close it."""
        token = await resolve_access_token(self._base_root)
        client = _build_async_client(
            base_url=self._base_url,
            access_token=token,
            max_retries=self._max_retries,
            timeout_seconds=self._timeout_seconds,
        )
        try:
            yield client
        finally:
            close = getattr(client, "close", None)
            if close is not None:
                await close()

    async def complete(self, *, system: str, user: str, model: str) -> str:
        """Collapse a Responses stream to the final assistant text.

        Network/API failures map to :class:`MiniMaxCallError` (carrying any HTTP
        status) so ``RetryingMiniMaxClient`` classifies and retries them. A
        genuine ``TypeError``/``AttributeError`` from our own code propagates
        unmapped rather than masquerading as an API error.
        """
        kwargs = _request_kwargs(
            system=system,
            user=user,
            model=model,
            reasoning_effort=self._reasoning_effort,
        )
        try:
            return await self._stream_to_text(kwargs)
        except MiniMaxCallError:
            raise
        except (TypeError, AttributeError):
            raise
        except Exception as e:  # noqa: BLE001 — SDK exception types vary by version
            status = getattr(e, "status_code", None)
            raise MiniMaxCallError(str(e), status_code=status) from e

    async def _stream_to_text(self, kwargs: dict[str, Any]) -> str:
        parts: list[str] = []
        final: Any = None
        reducer_bug_seen = False
        async with self._client() as client, client.responses.stream(**kwargs) as stream:
            # The codex backend ships ``response.output = None`` in its terminal
            # ``response.completed`` payload; the SDK reducer iterates it and
            # dies with TypeError. It can surface inside ``async for`` or from
            # ``get_final_response()`` — tolerate both and fall back to the
            # locally accumulated delta text. The catch is narrow: only the
            # reducer's own signature is treated as a known quirk.
            try:
                async for event in stream:
                    ev_type = getattr(event, "type", None)
                    if ev_type == "response.output_text.delta":
                        delta = getattr(event, "delta", None) or ""
                        if delta:
                            parts.append(delta)
                    # response.reasoning_summary_text.delta and all other event
                    # types are intentionally dropped — complete() only needs
                    # the final assembled message text.
            except (TypeError, AttributeError) as exc:
                if not _is_codex_final_response_reducer_bug(exc):
                    raise
                logger.warning(
                    "Codex stream reducer failed during iteration; falling back "
                    "to accumulated deltas (%d chars). SDK bug: %s",
                    sum(len(p) for p in parts),
                    exc,
                )
                reducer_bug_seen = True
                final = None
            else:
                try:
                    final = await stream.get_final_response()
                except (TypeError, AttributeError) as exc:
                    if not _is_codex_final_response_reducer_bug(exc):
                        raise
                    logger.warning(
                        "Codex stream reducer failed in get_final_response; "
                        "falling back to accumulated deltas (%d chars). SDK "
                        "bug: %s",
                        sum(len(p) for p in parts),
                        exc,
                    )
                    reducer_bug_seen = True
                    final = None

        # Trust the SDK's authoritative final text when present. But the codex
        # backend sometimes ships a terminal response whose ``output`` is an
        # EMPTY LIST even though real output_text deltas streamed — in that one
        # case the streamed ``parts`` are authoritative.
        extracted = "" if final is None else _extract_text_from_response(final)
        if final is None:
            final_text = "".join(parts)
        elif extracted:
            final_text = extracted
        elif parts and not (getattr(final, "output", None) or []):
            final_text = "".join(parts)
        else:
            final_text = extracted

        # Total-loss safeguard: reducer bug fired before any text arrived. Map
        # to a retryable error (status 503) — empirically transient (auth flap,
        # quota throttle, content-refusal that resolves on retry).
        if reducer_bug_seen and not parts:
            raise MiniMaxCallError(
                "codex backend returned response.output=None and shipped zero "
                "text deltas (likely auth, quota, or content-refusal on "
                "chatgpt.com/backend-api/codex)",
                status_code=503,
            )
        return final_text

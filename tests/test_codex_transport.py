"""Unit tests for CodexResponsesTransport — fully offline (fake Responses stream)."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

import dikw_data.codex_transport as ct
from dikw_data.codex_transport import CodexResponsesTransport, _request_kwargs
from dikw_data.llm_client import MiniMaxCallError

REDUCER_BUG = TypeError("'NoneType' object is not iterable")


class _Event:
    def __init__(self, type: str, delta: str | None = None) -> None:
        self.type = type
        self.delta = delta


class _Part:
    def __init__(self, type: str, text: str) -> None:
        self.type = type
        self.text = text


class _Item:
    def __init__(self, type: str, content: list[_Part] | None = None) -> None:
        self.type = type
        self.content = content or []


class _Final:
    def __init__(self, output: Any, status: str = "completed") -> None:
        self.output = output
        self.status = status
        self.usage = None


class _FakeStream:
    """Async context manager mimicking ``client.responses.stream(...)``."""

    def __init__(self, events: list[_Event], final: Any) -> None:
        self._events = events
        self._final = final
        self.kwargs: dict[str, Any] = {}

    async def __aenter__(self) -> _FakeStream:
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    def __aiter__(self) -> Any:
        async def _gen() -> Any:
            for e in self._events:
                yield e

        return _gen()

    async def get_final_response(self) -> Any:
        if isinstance(self._final, BaseException):
            raise self._final
        return self._final


class _FakeResponses:
    def __init__(self, stream: _FakeStream) -> None:
        self._stream = stream

    def stream(self, **kwargs: Any) -> _FakeStream:
        self._stream.kwargs = kwargs
        return self._stream


class _FakeClient:
    def __init__(self, stream: _FakeStream) -> None:
        self.responses = _FakeResponses(stream)

    async def close(self) -> None:
        return None


def _patch(monkeypatch: pytest.MonkeyPatch, stream: _FakeStream) -> _FakeClient:
    client = _FakeClient(stream)

    async def _fake_token(*a: Any, **k: Any) -> str:
        return "fake-token"

    monkeypatch.setattr(ct, "resolve_access_token", _fake_token)
    monkeypatch.setattr(ct, "_build_async_client", lambda **k: client)
    return client


def _run(transport: CodexResponsesTransport) -> str:
    return asyncio.run(transport.complete(system="S", user="U", model="gpt-5.5"))


def test_reasoning_effort_on_the_wire(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = _FakeStream(
        [_Event("response.output_text.delta", "hi")],
        _Final(output=[_Item("message", [_Part("output_text", "hi")])]),
    )
    _patch(monkeypatch, stream)
    transport = CodexResponsesTransport(reasoning_effort="xhigh")
    assert _run(transport) == "hi"
    assert stream.kwargs["reasoning"] == {"effort": "xhigh"}
    assert "temperature" not in stream.kwargs
    assert "max_output_tokens" not in stream.kwargs


def test_no_reasoning_field_when_effort_unset() -> None:
    kwargs = _request_kwargs(system="S", user="U", model="m", reasoning_effort=None)
    assert "reasoning" not in kwargs


def test_final_message_text_is_authoritative(monkeypatch: pytest.MonkeyPatch) -> None:
    stream = _FakeStream(
        [
            _Event("response.output_text.delta", "Hello"),
            _Event("response.reasoning_summary_text.delta", "(thinking)"),
            _Event("response.output_text.delta", " world"),
        ],
        _Final(output=[_Item("message", [_Part("output_text", "Hello world")])]),
    )
    _patch(monkeypatch, stream)
    assert _run(CodexResponsesTransport()) == "Hello world"


def test_empty_output_list_falls_back_to_deltas(monkeypatch: pytest.MonkeyPatch) -> None:
    # Backend ships output=[] though real deltas streamed — deltas win.
    stream = _FakeStream(
        [_Event("response.output_text.delta", "streamed")],
        _Final(output=[]),
    )
    _patch(monkeypatch, stream)
    assert _run(CodexResponsesTransport()) == "streamed"


def test_reducer_bug_falls_back_to_accumulated_deltas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = _FakeStream(
        [_Event("response.output_text.delta", "partial answer")],
        REDUCER_BUG,
    )
    _patch(monkeypatch, stream)
    assert _run(CodexResponsesTransport()) == "partial answer"


def test_reducer_bug_with_zero_deltas_raises_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stream = _FakeStream([], REDUCER_BUG)
    _patch(monkeypatch, stream)
    with pytest.raises(MiniMaxCallError) as excinfo:
        _run(CodexResponsesTransport())
    # status 503 → treated as retryable by the client's retry layer.
    assert excinfo.value.status_code == 503


def test_unrelated_type_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    # A genuine bug must not be masked as an API error.
    stream = _FakeStream(
        [_Event("response.output_text.delta", "x")],
        TypeError("totally unrelated"),
    )
    _patch(monkeypatch, stream)
    with pytest.raises(TypeError, match="totally unrelated"):
        _run(CodexResponsesTransport())

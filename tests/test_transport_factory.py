"""Unit tests for the provider -> transport factory and config loading."""

from __future__ import annotations

import dataclasses

import pytest

import dikw_data.llm_client as llm_client
from dikw_data.config import config_path_for, load_llm_config
from dikw_data.codex_transport import CodexResponsesTransport
from dikw_data.llm_client import AnthropicTransport, build_transport


def test_config_path_for() -> None:
    assert config_path_for("codex").name == "codex.yml"
    assert config_path_for("deepseek").parent.name == "configs"


def test_codex_config_loads_with_effort() -> None:
    cfg = load_llm_config(config_path_for("codex"))
    assert cfg.llm == "openai_codex"
    assert cfg.model == "gpt-5.5"
    assert cfg.reasoning_effort == "xhigh"
    assert cfg.base_url == "https://chatgpt.com/backend-api/codex"


def test_build_transport_codex_needs_no_env() -> None:
    cfg = load_llm_config(config_path_for("codex"))
    transport = build_transport(cfg)
    assert isinstance(transport, CodexResponsesTransport)
    assert transport._reasoning_effort == "xhigh"


def test_build_transport_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_client, "get_required_env", lambda key: f"key-for-{key}")
    for provider in ("minimax", "deepseek"):
        cfg = load_llm_config(config_path_for(provider))
        transport = build_transport(cfg)
        assert isinstance(transport, AnthropicTransport)


def test_build_transport_legacy_anthropic_spelling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(llm_client, "get_required_env", lambda key: "k")
    cfg = load_llm_config(config_path_for("minimax"))
    legacy = dataclasses.replace(cfg, llm="anthropic")
    assert isinstance(build_transport(legacy), AnthropicTransport)


def test_build_transport_unknown_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_client, "get_required_env", lambda key: "k")
    cfg = load_llm_config(config_path_for("minimax"))
    bogus = dataclasses.replace(cfg, llm="mystery")
    with pytest.raises(ValueError, match="unknown provider"):
        build_transport(bogus)

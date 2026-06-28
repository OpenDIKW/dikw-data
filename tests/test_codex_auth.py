"""Unit tests for codex_auth — offline (no OAuth network calls)."""

from __future__ import annotations

import asyncio
import base64
import json
import time
from pathlib import Path

import pytest

import dikw_data.codex_auth as auth


def _b64url(obj: dict) -> str:
    raw = json.dumps(obj).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _make_jwt(*, exp_in: int = 3600, account_id: str | None = "acct-123") -> str:
    """Mint a fake (unsigned) JWT with codex-style nested account_id claim."""
    header = _b64url({"alg": "none", "typ": "JWT"})
    payload: dict = {"exp": int(time.time()) + exp_in}
    if account_id is not None:
        payload["https://api.openai.com/auth"] = {"chatgpt_account_id": account_id}
    return f"{header}.{_b64url(payload)}.sig"


def test_account_id_from_nested_claim() -> None:
    token = _make_jwt(account_id="744ae65d")
    assert auth.account_id_from_jwt(token) == "744ae65d"


def test_account_id_absent_returns_none() -> None:
    assert auth.account_id_from_jwt(_make_jwt(account_id=None)) is None
    assert auth.account_id_from_jwt("not-a-jwt") is None


def test_is_expiring() -> None:
    assert auth._is_expiring(_make_jwt(exp_in=-10), skew_seconds=0) is True
    assert auth._is_expiring(_make_jwt(exp_in=3600), skew_seconds=120) is False
    assert auth._is_expiring("not-a-jwt", skew_seconds=0) is True


def test_store_round_trip(tmp_path: Path) -> None:
    tokens = {"access_token": _make_jwt(), "refresh_token": "refresh-xyz"}
    auth.save_codex_tokens(tmp_path, tokens)
    loaded = auth.read_codex_tokens(tmp_path)
    assert loaded["access_token"] == tokens["access_token"]
    assert loaded["refresh_token"] == "refresh-xyz"
    # Tokens are written 0o600.
    assert (auth.dikw_auth_path(tmp_path).stat().st_mode & 0o777) == 0o600


def test_read_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(auth.CodexAuthError) as excinfo:
        auth.read_codex_tokens(tmp_path)
    assert excinfo.value.relogin_required is True


def test_lazy_import_from_codex_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Fake ~/.codex/auth.json (flat schema) with a non-expired token.
    codex_home = tmp_path / "codex"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text(
        json.dumps(
            {
                "tokens": {
                    "access_token": _make_jwt(exp_in=3600, account_id="acct-cli"),
                    "refresh_token": "cli-refresh",
                },
                "last_refresh": "2026-06-28T00:00:00Z",
            }
        )
    )
    monkeypatch.setenv("CODEX_HOME", str(codex_home))

    base = tmp_path / "project"
    assert not auth.dikw_auth_path(base).exists()
    auth._maybe_migrate_from_codex_cli(base)

    loaded = auth.read_codex_tokens(base)
    assert loaded["refresh_token"] == "cli-refresh"
    assert auth.account_id_from_jwt(loaded["access_token"]) == "acct-cli"


def test_resolve_skips_refresh_when_fresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth.save_codex_tokens(
        tmp_path,
        {"access_token": _make_jwt(exp_in=3600), "refresh_token": "r"},
    )

    async def _boom(*a: object, **k: object) -> dict[str, str]:
        raise AssertionError("refresh must not be called for a fresh token")

    monkeypatch.setattr(auth, "refresh_codex_tokens", _boom)
    # Disable lazy import so the test's store is the only source.
    monkeypatch.setattr(auth, "_maybe_migrate_from_codex_cli", lambda base: None)

    token = asyncio.run(auth.resolve_access_token(tmp_path))
    assert auth._is_expiring(token, skew_seconds=120) is False


def test_resolve_refreshes_when_expiring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth.save_codex_tokens(
        tmp_path,
        {"access_token": _make_jwt(exp_in=-10), "refresh_token": "old-refresh"},
    )
    fresh = _make_jwt(exp_in=3600)

    async def _fake_refresh(*, refresh_token: str, timeout_seconds: float = 20.0):
        assert refresh_token == "old-refresh"
        return {"access_token": fresh, "refresh_token": "new-refresh"}

    monkeypatch.setattr(auth, "refresh_codex_tokens", _fake_refresh)
    monkeypatch.setattr(auth, "_maybe_migrate_from_codex_cli", lambda base: None)

    token = asyncio.run(auth.resolve_access_token(tmp_path))
    assert token == fresh
    # Rotated refresh_token persisted.
    assert auth.read_codex_tokens(tmp_path)["refresh_token"] == "new-refresh"

"""Codex OAuth credential resolution — dikw-data self-managed token store.

Ported (trimmed) from dikw-core's ``providers/codex_auth.py``. Tokens live at
``<base>/.dikw/auth.json`` (default base = the dikw-data project root),
deliberately separate from codex CLI's ``~/.codex/auth.json``.

Why a separate store: OpenAI's ChatGPT OAuth issuer rotates the refresh_token
on every refresh. If two clients (codex CLI, dikw-data) write the same file,
whichever refreshes second is silently logged out because its refresh_token has
just been invalidated by the first. Each client therefore keeps its own copy.

Bootstrap paths into the dikw-data store:
  * ``device_code_login(base)`` runs the OpenAI device-code flow itself.
  * ``import_from_codex_cli(base)`` copies tokens from ``~/.codex/auth.json`` once.
  * ``_maybe_migrate_from_codex_cli(base)`` is the lazy in-process variant — it
    fires automatically the first time a token is needed and the dikw-data store
    is missing while codex CLI's file is valid, so an already-logged-in codex
    CLI user is unblocked with zero extra steps.

OAuth client_id is the public identifier of the codex CLI application itself
(not a per-user secret); ChatGPT's issuer pins refresh_tokens to the client_id
that minted them, so refreshing a codex-CLI-issued token requires sending it back.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import os
import sys
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import PROJECT_ROOT

_fcntl: Any | None = None
_msvcrt: Any | None = None
try:
    import fcntl

    _fcntl = fcntl
except ImportError:  # pragma: no cover — Windows
    pass
try:
    import msvcrt

    _msvcrt = msvcrt
except ImportError:  # pragma: no cover — POSIX
    pass

DEFAULT_CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"
CODEX_OAUTH_ISSUER = "https://auth.openai.com"
CODEX_OAUTH_TOKEN_URL = f"{CODEX_OAUTH_ISSUER}/oauth/token"
CODEX_OAUTH_DEVICE_USERCODE_URL = f"{CODEX_OAUTH_ISSUER}/api/accounts/deviceauth/usercode"
CODEX_OAUTH_DEVICE_TOKEN_URL = f"{CODEX_OAUTH_ISSUER}/api/accounts/deviceauth/token"
CODEX_OAUTH_DEVICE_VERIFICATION_URL = f"{CODEX_OAUTH_ISSUER}/codex/device"
CODEX_OAUTH_DEVICE_REDIRECT_URI = f"{CODEX_OAUTH_ISSUER}/deviceauth/callback"
CODEX_OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
CODEX_ACCESS_TOKEN_REFRESH_SKEW_SECONDS = 120
CODEX_AUTH_LOCK_TIMEOUT_SECONDS = 30.0
CODEX_DEVICE_LOGIN_TIMEOUT_SECONDS = 15 * 60
CODEX_DEVICE_POLL_MIN_INTERVAL_SECONDS = 3

_AUTH_STORE_VERSION = 1
_PROVIDER_KEY = "openai-codex"


class CodexAuthError(RuntimeError):
    """OAuth-specific failure with a structured ``code`` for diagnostics.

    ``relogin_required=True`` signals the user must run the device-code login
    again (or import fresh tokens) to mint a new refresh_token.
    """

    def __init__(
        self, message: str, *, code: str, relogin_required: bool = False
    ) -> None:
        super().__init__(message)
        self.code = code
        self.relogin_required = relogin_required


# --------------------------------------------------------------------------- #
# Path resolution
# --------------------------------------------------------------------------- #


def default_base() -> Path:
    """The dikw-data project root — owner of the default auth store."""
    return PROJECT_ROOT


def codex_home() -> Path:
    """Resolve ``$CODEX_HOME`` or fall back to ``~/.codex`` (codex CLI default).

    Used only as the read-only source path for importing codex CLI tokens —
    dikw-data never writes here.
    """
    raw = os.environ.get("CODEX_HOME", "").strip()
    if not raw:
        return Path.home() / ".codex"
    return Path(raw).expanduser()


def dikw_auth_dir(base: Path) -> Path:
    return base / ".dikw"


def dikw_auth_path(base: Path) -> Path:
    return dikw_auth_dir(base) / "auth.json"


def dikw_auth_lock_path(base: Path) -> Path:
    return dikw_auth_dir(base) / "auth.json.lock"


# --------------------------------------------------------------------------- #
# JWT inspection (pure functions)
# --------------------------------------------------------------------------- #


def _decode_jwt_claims(token: str) -> dict[str, Any]:
    """base64url-decode the JWT payload segment, ``{}`` for any non-JWT input."""
    if not isinstance(token, str) or token.count(".") != 2:
        return {}
    payload_segment = token.split(".", 2)[1]
    if not payload_segment:
        return {}
    padded = payload_segment + "=" * (-len(payload_segment) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
        claims = json.loads(raw)
    except Exception:
        return {}
    return claims if isinstance(claims, dict) else {}


def _is_expiring(token: str, *, skew_seconds: int) -> bool:
    """True if the token has < ``skew_seconds`` left, or isn't a JWT.

    Conservative on the unknown side: a non-JWT or a JWT without ``exp`` is
    treated as expiring so the caller refreshes.
    """
    claims = _decode_jwt_claims(token)
    exp = claims.get("exp")
    if not isinstance(exp, int | float):
        return True
    return float(exp) <= (time.time() + max(0, int(skew_seconds)))


def account_id_from_jwt(token: str) -> str | None:
    """Extract ``chatgpt_account_id`` for the ``ChatGPT-Account-ID`` header.

    The codex CLI access_token nests the claim under
    ``["https://api.openai.com/auth"]["chatgpt_account_id"]`` rather than at
    the JWT top level, so we check both: top-level first (other token shapes),
    then the OpenAI auth namespace. Returns ``None`` when absent so callers
    omit the header rather than sending a malformed value.
    """
    claims = _decode_jwt_claims(token)
    value = claims.get("chatgpt_account_id")
    if isinstance(value, str) and value:
        return value
    nested = claims.get("https://api.openai.com/auth")
    if isinstance(nested, dict):
        value = nested.get("chatgpt_account_id")
        if isinstance(value, str) and value:
            return value
    return None


# --------------------------------------------------------------------------- #
# Cross-process advisory file lock — fcntl on POSIX, msvcrt on Windows.
# OS-level only (no in-process reentrancy): two coroutines on one event loop
# share a thread, so an in-process depth counter would let the second skip the
# OS lock and fire a concurrent OAuth refresh that invalidates the first's
# refresh_token. Callers must not nest lock acquisitions.
# --------------------------------------------------------------------------- #


def _seed_lock_file_if_needed(path: Path) -> None:
    if _msvcrt is None:
        return
    try:
        if not path.exists() or path.stat().st_size == 0:
            with path.open("a", encoding="utf-8") as seed:
                seed.write(" ")
    except (PermissionError, OSError):
        pass


def _try_os_lock_acquire(lock_file: Any) -> None:
    if _fcntl is not None:
        _fcntl.flock(lock_file.fileno(), _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        return
    assert _msvcrt is not None
    lock_file.seek(0)
    _msvcrt.locking(lock_file.fileno(), _msvcrt.LK_NBLCK, 1)


def _release_os_lock(lock_file: Any) -> None:
    if _fcntl is not None:
        _fcntl.flock(lock_file.fileno(), _fcntl.LOCK_UN)
        return
    if _msvcrt is not None:
        try:
            lock_file.seek(0)
            _msvcrt.locking(lock_file.fileno(), _msvcrt.LK_UNLCK, 1)
        except OSError:  # pragma: no cover
            pass


@contextmanager
def _auth_file_lock(path: Path, *, timeout: float) -> Iterator[None]:
    """Sync flavour — used by the public ``save_codex_tokens``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if _fcntl is None and _msvcrt is None:  # pragma: no cover — defensive
        yield
        return
    _seed_lock_file_if_needed(path)
    open_mode = "r+" if _msvcrt else "a+"
    with path.open(open_mode) as lock_file:
        deadline = time.time() + max(1.0, timeout)
        while True:
            try:
                _try_os_lock_acquire(lock_file)
                break
            except (BlockingIOError, OSError, PermissionError):
                if time.time() >= deadline:
                    raise TimeoutError(
                        f"Timed out waiting for codex auth lock at {path}"
                    ) from None
                time.sleep(0.05)
        try:
            yield
        finally:
            _release_os_lock(lock_file)


@asynccontextmanager
async def _async_auth_file_lock(path: Path, *, timeout: float) -> AsyncIterator[None]:
    """Async flavour — yields via ``asyncio.sleep`` instead of blocking the loop."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if _fcntl is None and _msvcrt is None:  # pragma: no cover — defensive
        yield
        return
    _seed_lock_file_if_needed(path)
    open_mode = "r+" if _msvcrt else "a+"
    with path.open(open_mode) as lock_file:
        deadline = time.time() + max(1.0, timeout)
        while True:
            try:
                _try_os_lock_acquire(lock_file)
                break
            except (BlockingIOError, OSError, PermissionError):
                if time.time() >= deadline:
                    raise TimeoutError(
                        f"Timed out waiting for codex auth lock at {path}"
                    ) from None
                await asyncio.sleep(0.05)
        try:
            yield
        finally:
            _release_os_lock(lock_file)


# --------------------------------------------------------------------------- #
# Auth store read / write — nested multi-provider schema:
#   {"version": 1, "providers": {"openai-codex": {"tokens": {...},
#    "last_refresh": "...", "auth_mode": "chatgpt"}}}
# --------------------------------------------------------------------------- #


def _load_store(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"version": _AUTH_STORE_VERSION, "providers": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CodexAuthError(
            f"dikw-data auth store at {path} is not valid JSON. "
            "Re-run `python -m dikw_data.codex_auth login` to repair.",
            code="codex_auth_invalid_json",
            relogin_required=True,
        ) from exc
    if not isinstance(raw, dict):
        raise CodexAuthError(
            f"dikw-data auth store at {path} has an unexpected top-level shape.",
            code="codex_auth_invalid_shape",
            relogin_required=True,
        )
    if raw.get("version") != _AUTH_STORE_VERSION:
        raise CodexAuthError(
            f"dikw-data auth store at {path} has unsupported version "
            f"{raw.get('version')!r}; this build expects {_AUTH_STORE_VERSION}.",
            code="codex_auth_unsupported_version",
            relogin_required=True,
        )
    if not isinstance(raw.get("providers"), dict):
        raw["providers"] = {}
    return raw


def read_codex_tokens(base: Path) -> dict[str, str]:
    """Load access_token + refresh_token from ``<base>/.dikw/auth.json``."""
    path = dikw_auth_path(base)
    store = _load_store(path)
    provider_node = store.get("providers", {}).get(_PROVIDER_KEY)
    if not isinstance(provider_node, dict):
        raise CodexAuthError(
            f"No dikw-data codex credentials at {path}. "
            "Run `python -m dikw_data.codex_auth login` to authenticate, "
            "or `python -m dikw_data.codex_auth import` to import from codex CLI.",
            code="codex_auth_missing",
            relogin_required=True,
        )
    tokens = provider_node.get("tokens")
    if not isinstance(tokens, dict):
        raise CodexAuthError(
            f"dikw-data auth store at {path} is missing the `tokens` block.",
            code="codex_auth_invalid_shape",
            relogin_required=True,
        )
    access = tokens.get("access_token")
    if not isinstance(access, str) or not access.strip():
        raise CodexAuthError(
            f"dikw-data auth store at {path} is missing access_token.",
            code="codex_auth_missing_access_token",
            relogin_required=True,
        )
    refresh = tokens.get("refresh_token")
    if not isinstance(refresh, str) or not refresh.strip():
        raise CodexAuthError(
            f"dikw-data auth store at {path} is missing refresh_token.",
            code="codex_auth_missing_refresh_token",
            relogin_required=True,
        )
    return {"access_token": access.strip(), "refresh_token": refresh.strip()}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _atomic_write_store(auth_path: Path, store: dict[str, Any]) -> None:
    """Atomic 0o600 JSON write — caller must hold the advisory lock.

    Writes ``auth.json.tmp`` then ``os.replace`` so cross-process readers never
    observe a partial file. Mode 0o600 keeps OAuth tokens off other local
    users' eyes; the unlink + O_EXCL dance enforces it (POSIX honours the mode
    only on creation, so reusing a stale .tmp would carry old permissions).
    """
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = auth_path.with_name(auth_path.name + ".tmp")
    tmp_path.unlink(missing_ok=True)
    payload = json.dumps(store, indent=2).encode("utf-8")
    flags = os.O_CREAT | os.O_WRONLY | os.O_EXCL
    fd = os.open(tmp_path, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
    except BaseException:
        with contextlib.suppress(OSError):
            os.close(fd)
        raise
    os.replace(tmp_path, auth_path)


def _write_tokens_unlocked(
    auth_path: Path,
    tokens: dict[str, str],
    *,
    last_refresh: str | None = None,
    auth_mode: str = "chatgpt",
) -> None:
    """Atomic in-place token write. Caller must hold ``_auth_file_lock``."""
    try:
        store = _load_store(auth_path)
    except CodexAuthError:
        store = {"version": _AUTH_STORE_VERSION, "providers": {}}
    providers = store.get("providers")
    if not isinstance(providers, dict):
        providers = {}
        store["providers"] = providers
    providers[_PROVIDER_KEY] = {
        "tokens": {
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
        },
        "last_refresh": last_refresh or _now_iso(),
        "auth_mode": auth_mode,
    }
    _atomic_write_store(auth_path, store)


def save_codex_tokens(
    base: Path, tokens: dict[str, str], *, auth_mode: str = "chatgpt"
) -> None:
    """Public sync save — acquires the advisory lock, then atomic-writes."""
    dikw_auth_dir(base).mkdir(parents=True, exist_ok=True)
    with _auth_file_lock(
        dikw_auth_lock_path(base), timeout=CODEX_AUTH_LOCK_TIMEOUT_SECONDS
    ):
        _write_tokens_unlocked(dikw_auth_path(base), tokens, auth_mode=auth_mode)


# --------------------------------------------------------------------------- #
# OAuth refresh + resolve_access_token orchestration
# --------------------------------------------------------------------------- #


_RELOGIN_ERROR_CODES = frozenset({"invalid_grant", "invalid_token", "invalid_request"})


def _extract_oauth_error(payload: Any) -> tuple[str, str | None]:
    if not isinstance(payload, dict):
        return "codex_refresh_failed", None
    err = payload.get("error")
    if isinstance(err, dict):
        code = err.get("code") or err.get("type") or "codex_refresh_failed"
        desc = err.get("message")
        return (
            str(code) if isinstance(code, str) else "codex_refresh_failed",
            desc if isinstance(desc, str) and desc.strip() else None,
        )
    if isinstance(err, str) and err.strip():
        desc = payload.get("error_description") or payload.get("message")
        return (
            err.strip(),
            desc if isinstance(desc, str) and desc.strip() else None,
        )
    return "codex_refresh_failed", None


async def refresh_codex_tokens(
    *, refresh_token: str, timeout_seconds: float = 20.0
) -> dict[str, str]:
    """Exchange a refresh_token for a fresh access_token at the OAuth endpoint.

    Returns ``{access_token, refresh_token}`` — uses the rotated refresh_token
    when present, otherwise preserves the input (some endpoints omit it on
    no-rotation refreshes).
    """
    import httpx

    timeout = httpx.Timeout(max(5.0, float(timeout_seconds)))
    async with httpx.AsyncClient(
        timeout=timeout, headers={"Accept": "application/json"}
    ) as client:
        response = await client.post(
            CODEX_OAUTH_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": CODEX_OAUTH_CLIENT_ID,
            },
        )

    if response.status_code != 200:
        try:
            payload = response.json()
        except Exception:
            payload = None
        code, description = _extract_oauth_error(payload)
        relogin = code in _RELOGIN_ERROR_CODES
        if code == "refresh_token_reused":
            relogin = True
            message = (
                "Codex refresh token was already consumed by another client "
                "(e.g. codex CLI or another dikw-data process). Re-authenticate "
                "with `python -m dikw_data.codex_auth login`."
            )
        elif description:
            message = f"Codex token refresh failed: {description}"
        else:
            message = f"Codex token refresh failed with status {response.status_code}."
        if response.status_code in (401, 403):
            relogin = True
        raise CodexAuthError(message, code=code, relogin_required=relogin)

    try:
        body = response.json()
    except Exception as exc:  # pragma: no cover
        raise CodexAuthError(
            "Codex token refresh returned invalid JSON.",
            code="codex_refresh_invalid_json",
            relogin_required=True,
        ) from exc
    new_access = body.get("access_token") if isinstance(body, dict) else None
    if not isinstance(new_access, str) or not new_access.strip():
        raise CodexAuthError(
            "Codex token refresh response was missing access_token.",
            code="codex_refresh_missing_access_token",
            relogin_required=True,
        )
    new_refresh = body.get("refresh_token") if isinstance(body, dict) else None
    rotated = (
        new_refresh.strip()
        if isinstance(new_refresh, str) and new_refresh.strip()
        else refresh_token
    )
    return {"access_token": new_access.strip(), "refresh_token": rotated}


async def resolve_access_token(
    base: Path | None = None,
    *,
    refresh_skew_seconds: int = CODEX_ACCESS_TOKEN_REFRESH_SKEW_SECONDS,
    refresh_timeout_seconds: float = 20.0,
) -> str:
    """Load tokens, refresh if expiring, write back the fresh pair, return the
    active access_token.

    Re-reads under lock before refreshing so two parallel workers seeing a
    near-expiring token fire only one network refresh. On the first call when
    the store is missing, lazily imports from codex CLI's ``~/.codex/auth.json``.
    """
    if base is None:
        base = default_base()
    _maybe_migrate_from_codex_cli(base)

    tokens = read_codex_tokens(base)
    if not _is_expiring(tokens["access_token"], skew_seconds=refresh_skew_seconds):
        return tokens["access_token"]

    dikw_auth_dir(base).mkdir(parents=True, exist_ok=True)
    async with _async_auth_file_lock(
        dikw_auth_lock_path(base), timeout=CODEX_AUTH_LOCK_TIMEOUT_SECONDS
    ):
        tokens = read_codex_tokens(base)
        if not _is_expiring(tokens["access_token"], skew_seconds=refresh_skew_seconds):
            return tokens["access_token"]
        refreshed = await refresh_codex_tokens(
            refresh_token=tokens["refresh_token"],
            timeout_seconds=refresh_timeout_seconds,
        )
        _write_tokens_unlocked(dikw_auth_path(base), refreshed)
        return refreshed["access_token"]


# --------------------------------------------------------------------------- #
# Import from codex CLI's auth.json (explicit + lazy)
# --------------------------------------------------------------------------- #


def _read_codex_cli_tokens_if_valid() -> dict[str, str] | None:
    """Read codex CLI's flat ``auth.json`` and return tokens iff non-expired."""
    src = codex_home() / "auth.json"
    if not src.is_file():
        return None
    try:
        raw = json.loads(src.read_text(encoding="utf-8"))
    except Exception:
        return None
    tokens = raw.get("tokens") if isinstance(raw, dict) else None
    if not isinstance(tokens, dict):
        return None
    access = tokens.get("access_token")
    refresh = tokens.get("refresh_token")
    if not isinstance(access, str) or not access.strip():
        return None
    if not isinstance(refresh, str) or not refresh.strip():
        return None
    if _is_expiring(access, skew_seconds=0):
        return None
    return {"access_token": access.strip(), "refresh_token": refresh.strip()}


def _maybe_migrate_from_codex_cli(base: Path) -> None:
    """Populate the dikw-data store from codex CLI's file on first use.

    Runs only when the dikw-data store file is missing entirely, so it won't
    auto-undo a deliberate logout (the file persists after logout).
    """
    dest = dikw_auth_path(base)
    if dest.exists():
        return
    src_tokens = _read_codex_cli_tokens_if_valid()
    if src_tokens is None:
        return
    src_path = codex_home() / "auth.json"
    save_codex_tokens(base, src_tokens)
    sys.stderr.write(
        f"[dikw-data] Imported codex tokens from {src_path} to {dest}.\n"
        f"[dikw-data] dikw-data will no longer write to {src_path}, but the "
        "imported refresh_token stays shared with codex CLI until the next "
        "refresh on either side rotates it (the other side's copy is then "
        "invalidated). For fully independent credentials run "
        "`python -m dikw_data.codex_auth login`.\n"
    )
    sys.stderr.flush()


@dataclass(frozen=True)
class ImportResult:
    source_path: Path
    dest_path: Path
    account_id: str | None
    expires_at: int | None


def _import_result_for(base: Path, src: Path, tokens: dict[str, str]) -> ImportResult:
    access = tokens["access_token"]
    claims = _decode_jwt_claims(access)
    exp = claims.get("exp")
    return ImportResult(
        source_path=src,
        dest_path=dikw_auth_path(base),
        account_id=account_id_from_jwt(access),
        expires_at=int(exp) if isinstance(exp, int | float) else None,
    )


def import_from_codex_cli(base: Path, *, force: bool = False) -> ImportResult:
    """Copy tokens from ``codex_home()/auth.json`` into the dikw-data store."""
    src = codex_home() / "auth.json"
    if not src.is_file():
        raise CodexAuthError(
            f"No codex CLI credentials at {src}. Run `codex` once to "
            "authenticate, or `python -m dikw_data.codex_auth login`.",
            code="codex_cli_auth_missing",
            relogin_required=True,
        )
    try:
        raw = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CodexAuthError(
            f"Codex CLI auth file at {src} is not valid JSON.",
            code="codex_cli_auth_invalid_json",
            relogin_required=True,
        ) from exc
    tokens_block = raw.get("tokens") if isinstance(raw, dict) else None
    if not isinstance(tokens_block, dict):
        raise CodexAuthError(
            f"Codex CLI auth file at {src} is missing the `tokens` block.",
            code="codex_cli_auth_invalid_shape",
            relogin_required=True,
        )
    access = tokens_block.get("access_token")
    refresh = tokens_block.get("refresh_token")
    if not isinstance(access, str) or not access.strip():
        raise CodexAuthError(
            f"Codex CLI auth file at {src} is missing access_token.",
            code="codex_cli_auth_missing_access_token",
            relogin_required=True,
        )
    if not isinstance(refresh, str) or not refresh.strip():
        raise CodexAuthError(
            f"Codex CLI auth file at {src} is missing refresh_token.",
            code="codex_cli_auth_missing_refresh_token",
            relogin_required=True,
        )
    tokens = {"access_token": access.strip(), "refresh_token": refresh.strip()}
    if not force and _is_expiring(tokens["access_token"], skew_seconds=0):
        raise CodexAuthError(
            f"Codex CLI access_token at {src} has already expired. Run `codex` "
            "to refresh it then retry, or pass --force.",
            code="codex_cli_auth_expired",
            relogin_required=True,
        )
    save_codex_tokens(base, tokens)
    return _import_result_for(base, src, tokens)


# --------------------------------------------------------------------------- #
# Device-code login — fully independent of codex CLI
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class DeviceCodeChallenge:
    user_code: str
    verification_uri: str
    device_auth_id: str
    poll_interval_seconds: int


def request_device_code() -> DeviceCodeChallenge:
    import httpx

    try:
        with httpx.Client(timeout=httpx.Timeout(15.0)) as client:
            response = client.post(
                CODEX_OAUTH_DEVICE_USERCODE_URL,
                json={"client_id": CODEX_OAUTH_CLIENT_ID},
                headers={"Content-Type": "application/json"},
            )
    except Exception as exc:
        raise CodexAuthError(
            f"Failed to request device code: {exc}",
            code="device_code_request_failed",
        ) from exc
    if response.status_code != 200:
        raise CodexAuthError(
            f"Device code request returned status {response.status_code}.",
            code="device_code_request_error",
        )
    try:
        data = response.json()
    except Exception as exc:
        raise CodexAuthError(
            "Device code response was not valid JSON.",
            code="device_code_invalid_json",
        ) from exc
    user_code = data.get("user_code")
    device_auth_id = data.get("device_auth_id")
    if not isinstance(user_code, str) or not user_code:
        raise CodexAuthError(
            "Device code response missing user_code.", code="device_code_incomplete"
        )
    if not isinstance(device_auth_id, str) or not device_auth_id:
        raise CodexAuthError(
            "Device code response missing device_auth_id.",
            code="device_code_incomplete",
        )
    try:
        interval = max(CODEX_DEVICE_POLL_MIN_INTERVAL_SECONDS, int(data.get("interval", 5)))
    except (TypeError, ValueError):
        interval = CODEX_DEVICE_POLL_MIN_INTERVAL_SECONDS
    return DeviceCodeChallenge(
        user_code=user_code,
        verification_uri=CODEX_OAUTH_DEVICE_VERIFICATION_URL,
        device_auth_id=device_auth_id,
        poll_interval_seconds=interval,
    )


def _poll_for_authorization_code(
    challenge: DeviceCodeChallenge, *, timeout_seconds: int
) -> dict[str, str]:
    import httpx

    deadline = time.monotonic() + max(5, timeout_seconds)
    last_error: CodexAuthError | None = None
    with httpx.Client(timeout=httpx.Timeout(15.0)) as client:
        while time.monotonic() < deadline:
            time.sleep(challenge.poll_interval_seconds)
            try:
                resp = client.post(
                    CODEX_OAUTH_DEVICE_TOKEN_URL,
                    json={
                        "device_auth_id": challenge.device_auth_id,
                        "user_code": challenge.user_code,
                    },
                    headers={"Content-Type": "application/json"},
                )
            except Exception as exc:
                last_error = CodexAuthError(
                    f"Device auth polling network error: {exc}",
                    code="device_code_poll_network",
                )
                continue
            if resp.status_code == 200:
                try:
                    body = resp.json()
                except Exception as exc:
                    raise CodexAuthError(
                        "Device auth poll returned invalid JSON.",
                        code="device_code_poll_invalid_json",
                    ) from exc
                authorization_code = body.get("authorization_code")
                code_verifier = body.get("code_verifier")
                if not isinstance(authorization_code, str) or not authorization_code:
                    raise CodexAuthError(
                        "Device auth response missing authorization_code.",
                        code="device_code_incomplete_exchange",
                    )
                if not isinstance(code_verifier, str) or not code_verifier:
                    raise CodexAuthError(
                        "Device auth response missing code_verifier.",
                        code="device_code_incomplete_exchange",
                    )
                return {
                    "authorization_code": authorization_code,
                    "code_verifier": code_verifier,
                }
            if resp.status_code in (403, 404):
                continue
            raise CodexAuthError(
                f"Device auth polling returned status {resp.status_code}.",
                code="device_code_poll_error",
            )
    if last_error is not None:
        raise last_error
    raise CodexAuthError(
        f"Device login timed out after {timeout_seconds}s.",
        code="device_code_timeout",
    )


def _exchange_authorization_code(
    authorization_code: str, code_verifier: str
) -> dict[str, str]:
    import httpx

    try:
        with httpx.Client(timeout=httpx.Timeout(15.0)) as client:
            resp = client.post(
                CODEX_OAUTH_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": authorization_code,
                    "redirect_uri": CODEX_OAUTH_DEVICE_REDIRECT_URI,
                    "client_id": CODEX_OAUTH_CLIENT_ID,
                    "code_verifier": code_verifier,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except Exception as exc:
        raise CodexAuthError(
            f"Token exchange request failed: {exc}",
            code="token_exchange_request_failed",
        ) from exc
    if resp.status_code != 200:
        raise CodexAuthError(
            f"Token exchange returned status {resp.status_code}.",
            code="token_exchange_error",
        )
    try:
        body = resp.json()
    except Exception as exc:
        raise CodexAuthError(
            "Token exchange response was not valid JSON.",
            code="token_exchange_invalid_json",
        ) from exc
    access = body.get("access_token") if isinstance(body, dict) else None
    refresh = body.get("refresh_token") if isinstance(body, dict) else None
    if not isinstance(access, str) or not access.strip():
        raise CodexAuthError(
            "Token exchange did not return an access_token.",
            code="token_exchange_no_access_token",
        )
    if not isinstance(refresh, str) or not refresh.strip():
        raise CodexAuthError(
            "Token exchange did not return a refresh_token.",
            code="token_exchange_no_refresh_token",
        )
    return {"access_token": access.strip(), "refresh_token": refresh.strip()}


def device_code_login(
    base: Path,
    *,
    on_challenge: Any | None = None,
    timeout_seconds: int = CODEX_DEVICE_LOGIN_TIMEOUT_SECONDS,
) -> ImportResult:
    """Run the full OpenAI device-code OAuth flow and persist tokens."""
    challenge = request_device_code()
    if on_challenge is not None:
        on_challenge(challenge)
    code_pair = _poll_for_authorization_code(challenge, timeout_seconds=timeout_seconds)
    tokens = _exchange_authorization_code(
        code_pair["authorization_code"], code_pair["code_verifier"]
    )
    save_codex_tokens(base, tokens)
    return _import_result_for(base, Path("(device-code login)"), tokens)


# --------------------------------------------------------------------------- #
# Status snapshot + tiny CLI (login / import / status)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AuthStatus:
    exists: bool
    expires_in_seconds: int | None
    last_refresh: str | None
    account_id: str | None


def auth_status(base: Path) -> AuthStatus:
    path = dikw_auth_path(base)
    try:
        store = _load_store(path)
    except CodexAuthError:
        return AuthStatus(True, None, None, None)
    node = store.get("providers", {}).get(_PROVIDER_KEY)
    if not isinstance(node, dict):
        return AuthStatus(False, None, None, None)
    tokens = node.get("tokens")
    access = tokens.get("access_token") if isinstance(tokens, dict) else None
    expires_in: int | None = None
    account: str | None = None
    if isinstance(access, str) and access.strip():
        claims = _decode_jwt_claims(access)
        exp = claims.get("exp")
        if isinstance(exp, int | float):
            expires_in = max(0, int(float(exp) - time.time()))
        account = account_id_from_jwt(access)
    last_refresh = node.get("last_refresh")
    return AuthStatus(
        exists=True,
        expires_in_seconds=expires_in,
        last_refresh=last_refresh if isinstance(last_refresh, str) else None,
        account_id=account,
    )


def _main(argv: list[str]) -> int:
    base = default_base()
    cmd = argv[0] if argv else "status"
    if cmd == "login":
        result = device_code_login(
            base,
            on_challenge=lambda c: print(
                f"Open {c.verification_uri} and enter code: {c.user_code}"
            ),
        )
        print(f"Logged in. Tokens stored at {result.dest_path}.")
        if result.account_id:
            print(f"account_id: {result.account_id}")
        return 0
    if cmd == "import":
        force = "--force" in argv[1:]
        result = import_from_codex_cli(base, force=force)
        print(f"Imported from {result.source_path} to {result.dest_path}.")
        if result.account_id:
            print(f"account_id: {result.account_id}")
        return 0
    if cmd == "status":
        # Force lazy import so `status` after a codex-CLI login reflects reality.
        _maybe_migrate_from_codex_cli(base)
        status = auth_status(base)
        if not status.exists:
            print(f"No codex credentials at {dikw_auth_path(base)}.")
            return 1
        exp = (
            f"{status.expires_in_seconds}s"
            if status.expires_in_seconds is not None
            else "unknown"
        )
        print(f"store: {dikw_auth_path(base)}")
        print(f"account_id: {status.account_id or '(none)'}")
        print(f"access_token expires_in: {exp}")
        print(f"last_refresh: {status.last_refresh or '(none)'}")
        return 0
    print(f"unknown command {cmd!r}; use one of: login, import, status", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))

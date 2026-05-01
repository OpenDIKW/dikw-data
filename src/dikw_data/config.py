"""Configuration and environment loading for MiniMax-backed data generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "minimax.yml"
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 6
    initial_backoff_seconds: float = 2.0
    max_backoff_seconds: float = 60.0
    jitter: bool = True
    timeout_seconds: float = 120.0


@dataclass(frozen=True)
class MiniMaxConfig:
    model: str
    base_url: str
    timeout_seconds: float
    sdk_max_retries: int
    retry_policy: RetryPolicy
    concurrency: int = 2
    rate_limit_slowdown_after: int = 3


def load_dotenv(path: Path = DEFAULT_ENV_PATH) -> dict[str, str]:
    """Load simple KEY=VALUE lines without mutating process env."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_required_env(key: str, env_path: Path = DEFAULT_ENV_PATH) -> str:
    values = load_dotenv(env_path)
    value = values.get(key)
    if not value:
        raise RuntimeError(f"{key} is not set in {env_path}")
    return value


def load_minimax_config(path: Path = DEFAULT_CONFIG_PATH) -> MiniMaxConfig:
    if not path.is_file():
        raise FileNotFoundError(f"MiniMax config not found: {path}")
    raw = _load_yaml_mapping(path)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: top-level YAML must be a mapping")

    provider = _mapping(raw.get("provider"), "provider")
    retry = _mapping(raw.get("retry_policy"), "retry_policy")
    runtime = _mapping(raw.get("runtime"), "runtime")

    retry_policy = RetryPolicy(
        max_attempts=int(retry.get("max_attempts", 6)),
        initial_backoff_seconds=float(retry.get("initial_backoff_seconds", 2)),
        max_backoff_seconds=float(retry.get("max_backoff_seconds", 60)),
        jitter=bool(retry.get("jitter", True)),
        timeout_seconds=float(retry.get("timeout_seconds", provider.get("timeout_seconds", 120))),
    )
    return MiniMaxConfig(
        model=str(provider.get("llm_model") or "MiniMax-M2.7"),
        base_url=str(provider.get("llm_base_url") or "https://api.minimaxi.com/anthropic"),
        timeout_seconds=float(provider.get("timeout_seconds", retry_policy.timeout_seconds)),
        sdk_max_retries=int(provider.get("sdk_max_retries", 2)),
        retry_policy=retry_policy,
        concurrency=int(runtime.get("concurrency", 2)),
        rate_limit_slowdown_after=int(runtime.get("rate_limit_slowdown_after", 3)),
    )


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a mapping")
    return value


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore[import-not-found]

        raw = yaml.safe_load(text) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: top-level YAML must be a mapping")
        return raw
    except ModuleNotFoundError:
        return _parse_simple_yaml(text)


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the small nested mapping shape used by configs/minimax.yml.

    This fallback keeps dry-runs usable in minimal Python environments. It is
    intentionally narrow; install PyYAML for general YAML support.
    """
    root: dict[str, Any] = {}
    current: dict[str, Any] | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" ") and stripped.endswith(":"):
            key = stripped[:-1]
            current = {}
            root[key] = current
            continue
        if current is None or ":" not in stripped:
            raise ValueError("fallback YAML parser only supports nested mappings")
        key, value = stripped.split(":", 1)
        current[key.strip()] = _coerce_scalar(value.strip())
    return root


def _coerce_scalar(value: str) -> Any:
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value.strip('"').strip("'")

"""Stable task identities for resumable LLM data-generation jobs."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class LLMTask:
    dataset: str
    stage: str
    source_hash: str
    prompt_version: str
    system: str
    user: str
    expected_json: bool = True

    @property
    def task_id(self) -> str:
        payload = "\n".join(
            [
                self.dataset,
                self.stage,
                self.source_hash,
                self.prompt_version,
                self.system,
                self.user,
            ]
        )
        return sha256(payload.encode("utf-8")).hexdigest()[:32]


def hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


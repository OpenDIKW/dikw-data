"""SQLite audit log for LLM calls and resumable task state."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TERMINAL_SUCCESS = "succeeded"
FAILED = "failed"
NEEDS_MANUAL_REVIEW = "needs_manual_review"


@dataclass(frozen=True)
class AuditRecord:
    task_id: str
    dataset: str
    stage: str
    status: str
    attempts: int
    last_error: str | None
    result_json: dict[str, Any] | list[Any] | None
    raw_response: str | None


class AuditStore:
    def __init__(self, dataset: str, generated_root: Path = Path("generated")) -> None:
        self.dataset = dataset
        self.dataset_dir = generated_root / dataset
        self.dataset_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.dataset_dir / "audit.sqlite"
        self.jsonl_path = self.dataset_dir / f"{dataset}.jsonl"
        self._init_db()

    def get(self, task_id: str) -> AuditRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                select task_id, dataset, stage, status, attempts, last_error,
                       result_json, raw_response
                from llm_tasks
                where task_id = ?
                """,
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return AuditRecord(
            task_id=str(row[0]),
            dataset=str(row[1]),
            stage=str(row[2]),
            status=str(row[3]),
            attempts=int(row[4]),
            last_error=row[5],
            result_json=json.loads(row[6]) if row[6] else None,
            raw_response=row[7],
        )

    def should_skip(self, task_id: str, *, resume: bool, retry_failed: bool) -> bool:
        record = self.get(task_id)
        if record is None:
            return False
        if retry_failed:
            return record.status == TERMINAL_SUCCESS
        if resume:
            return record.status == TERMINAL_SUCCESS
        return False

    def records(
        self, *, stage: str | None = None, status: str | None = None
    ) -> list[AuditRecord]:
        clauses: list[str] = []
        params: list[str] = []
        if stage is not None:
            clauses.append("stage = ?")
            params.append(stage)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where = f"where {' and '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                select task_id, dataset, stage, status, attempts, last_error,
                       result_json, raw_response
                from llm_tasks
                {where}
                order by updated_at
                """,
                params,
            ).fetchall()
        return [
            AuditRecord(
                task_id=str(row[0]),
                dataset=str(row[1]),
                stage=str(row[2]),
                status=str(row[3]),
                attempts=int(row[4]),
                last_error=row[5],
                result_json=json.loads(row[6]) if row[6] else None,
                raw_response=row[7],
            )
            for row in rows
        ]

    def record_started(self, *, task_id: str, dataset: str, stage: str) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                """
                insert into llm_tasks (
                    task_id, dataset, stage, status, attempts, created_at, updated_at
                )
                values (?, ?, ?, 'running', 0, ?, ?)
                on conflict(task_id) do update set
                    status = 'running',
                    updated_at = excluded.updated_at
                """,
                (task_id, dataset, stage, now, now),
            )

    def record_finished(
        self,
        *,
        task_id: str,
        dataset: str,
        stage: str,
        status: str,
        attempts: int,
        raw_response: str | None,
        result_json: dict[str, Any] | list[Any] | None,
        last_error: str | None,
    ) -> None:
        now = _now()
        encoded_result = json.dumps(result_json, ensure_ascii=False) if result_json is not None else None
        with self._connect() as conn:
            conn.execute(
                """
                insert into llm_tasks (
                    task_id, dataset, stage, status, attempts, last_error,
                    raw_response, result_json, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(task_id) do update set
                    status = excluded.status,
                    attempts = excluded.attempts,
                    last_error = excluded.last_error,
                    raw_response = excluded.raw_response,
                    result_json = excluded.result_json,
                    updated_at = excluded.updated_at
                """,
                (
                    task_id,
                    dataset,
                    stage,
                    status,
                    attempts,
                    last_error,
                    raw_response,
                    encoded_result,
                    now,
                    now,
                ),
            )
        self._append_jsonl(
            {
                "task_id": task_id,
                "dataset": dataset,
                "stage": stage,
                "status": status,
                "attempts": attempts,
                "last_error": last_error,
                "result": result_json,
                "updated_at": now,
            }
        )

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists llm_tasks (
                    task_id text primary key,
                    dataset text not null,
                    stage text not null,
                    status text not null,
                    attempts integer not null default 0,
                    last_error text,
                    raw_response text,
                    result_json text,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                "create index if not exists idx_llm_tasks_dataset_stage on llm_tasks(dataset, stage)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _append_jsonl(self, payload: dict[str, Any]) -> None:
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _now() -> str:
    return datetime.now(UTC).isoformat()

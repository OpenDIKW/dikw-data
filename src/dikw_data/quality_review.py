"""LLM-backed dataset quality review storage and task construction."""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from .audit import AuditStore
from .config import MiniMaxConfig, load_minimax_config
from .llm_client import MiniMaxTransport, RetryingMiniMaxClient
from .pipeline import prompt_task
from .tasks import LLMTask


DECISIONS = {"pass", "warn", "fail"}
IMAGE_REF = re.compile(r"!\[([^\]]*)\]\(([^)\n]+)\)")
HEADING_REF = re.compile(r"^##\s+(.+)$", re.MULTILINE)
TARGET_REF = re.compile(r"^Target:\s*(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class ReviewTarget:
    target_type: str
    target_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class QualityReviewItem:
    target_type: str
    target_id: str
    decision: str
    score: int
    reason: str
    suggested_fix: str
    risk_flags: list[str]
    raw_json: dict[str, Any] | None = None


class QualityReviewStore:
    def __init__(self, dataset: str, generated_root: Path = Path("generated")) -> None:
        self.dataset = dataset
        self.dataset_dir = generated_root / dataset
        self.dataset_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.dataset_dir / "quality_review.sqlite"
        self._init_db()

    def start_batch(self) -> str:
        running = self.running_batch()
        if running is not None:
            raise RuntimeError(f"quality review batch already running: {running['batch_id']}")
        now = _now()
        batch_id = f"qr-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
        with self._connect() as conn:
            conn.execute(
                """
                insert into quality_review_batches (
                    batch_id, dataset, status, error, created_at, updated_at
                )
                values (?, ?, 'running', null, ?, ?)
                """,
                (batch_id, self.dataset, now, now),
            )
        return batch_id

    def running_batch(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                select batch_id, dataset, status, error, created_at, updated_at
                from quality_review_batches
                where status = 'running'
                order by created_at desc
                limit 1
                """
            ).fetchone()
        return dict(row) if row is not None else None

    def latest_batch(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                select batch_id, dataset, status, error, created_at, updated_at
                from quality_review_batches
                order by created_at desc
                limit 1
                """
            ).fetchone()
        return dict(row) if row is not None else None

    def finish_batch(self, batch_id: str) -> None:
        self._set_batch_status(batch_id, "succeeded", None)

    def fail_batch(self, batch_id: str, error: str) -> None:
        self._set_batch_status(batch_id, "failed", error)

    def add_items(self, batch_id: str, items: list[QualityReviewItem]) -> None:
        now = _now()
        with self._connect() as conn:
            conn.executemany(
                """
                insert into quality_review_items (
                    batch_id, target_type, target_id, decision, score, reason,
                    suggested_fix, risk_flags, raw_json, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        batch_id,
                        item.target_type,
                        item.target_id,
                        item.decision,
                        item.score,
                        item.reason,
                        item.suggested_fix,
                        json.dumps(item.risk_flags, ensure_ascii=False),
                        json.dumps(item.raw_json, ensure_ascii=False) if item.raw_json is not None else None,
                        now,
                    )
                    for item in items
                ],
            )

    def items(
        self,
        batch_id: str | None = None,
        *,
        decision: str | None = None,
    ) -> list[dict[str, Any]]:
        batch = batch_id or (self.latest_batch() or {}).get("batch_id")
        if not batch:
            return []
        clauses = ["batch_id = ?"]
        params: list[Any] = [batch]
        if decision:
            clauses.append("decision = ?")
            params.append(decision)
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                f"""
                select target_type, target_id, decision, score, reason, suggested_fix,
                       risk_flags, raw_json, created_at
                from quality_review_items
                where {' and '.join(clauses)}
                order by
                    case decision when 'fail' then 0 when 'warn' then 1 else 2 end,
                    target_type,
                    target_id
                """,
                params,
            ).fetchall()
        return [
            {
                **dict(row),
                "risk_flags": json.loads(row["risk_flags"] or "[]"),
                "raw_json": json.loads(row["raw_json"]) if row["raw_json"] else None,
            }
            for row in rows
        ]

    def stats(self, batch_id: str | None = None) -> dict[str, int]:
        batch = batch_id or (self.latest_batch() or {}).get("batch_id")
        stats = {"pass": 0, "warn": 0, "fail": 0}
        if not batch:
            return stats
        with self._connect() as conn:
            rows = conn.execute(
                """
                select decision, count(*)
                from quality_review_items
                where batch_id = ?
                group by decision
                """,
                (batch,),
            ).fetchall()
        for decision, count in rows:
            if decision in stats:
                stats[str(decision)] = int(count)
        return stats

    def _set_batch_status(self, batch_id: str, status: str, error: str | None) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                update quality_review_batches
                set status = ?, error = ?, updated_at = ?
                where batch_id = ?
                """,
                (status, error, _now(), batch_id),
            )

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists quality_review_batches (
                    batch_id text primary key,
                    dataset text not null,
                    status text not null,
                    error text,
                    created_at text not null,
                    updated_at text not null
                )
                """
            )
            conn.execute(
                """
                create table if not exists quality_review_items (
                    id integer primary key autoincrement,
                    batch_id text not null,
                    target_type text not null,
                    target_id text not null,
                    decision text not null,
                    score integer not null,
                    reason text not null,
                    suggested_fix text not null,
                    risk_flags text not null,
                    raw_json text,
                    created_at text not null
                )
                """
            )
            conn.execute(
                "create index if not exists idx_quality_review_items_batch on quality_review_items(batch_id)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)


def collect_review_targets(dataset_dir: Path) -> list[ReviewTarget]:
    corpus_dir = dataset_dir / "corpus"
    docs = {
        path.stem: path.read_text(encoding="utf-8")
        for path in sorted(corpus_dir.glob("*.md"))
    }
    doc_sections = {stem: _sections(text) for stem, text in docs.items()}
    dataset_meta = _load_yaml(dataset_dir / "dataset.yaml") if (dataset_dir / "dataset.yaml").is_file() else {}
    targets: list[ReviewTarget] = [
        ReviewTarget(
            target_type="dataset",
            target_id=str(dataset_meta.get("name") or dataset_dir.name),
            payload={
                "dataset_yaml": dataset_meta,
                "corpus_docs": sorted(docs),
                "has_targets_yaml": (dataset_dir / "targets.yaml").is_file(),
                "query_count": _query_count(dataset_dir / "queries.yaml"),
            },
        )
    ]

    for stem, text in docs.items():
        targets.append(
            ReviewTarget(
                target_type="corpus_doc",
                target_id=stem,
                payload={
                    "doc": stem,
                    "text": _truncate(text, 6000),
                    "headings": HEADING_REF.findall(text),
                    "target_markers": TARGET_REF.findall(text),
                    "image_refs": _image_refs(text),
                },
            )
        )

    queries_path = dataset_dir / "queries.yaml"
    if queries_path.is_file():
        queries = _load_yaml(queries_path).get("queries") or []
        if isinstance(queries, list):
            for index, query in enumerate(queries, start=1):
                if not isinstance(query, dict):
                    continue
                query_id = str(query.get("id") or f"query-{index}")
                targets.append(
                    ReviewTarget(
                        target_type="query",
                        target_id=query_id,
                        payload={
                            "query": query,
                            "known_corpus_docs": sorted(docs),
                        },
                    )
                )

    targets_path = dataset_dir / "targets.yaml"
    if targets_path.is_file():
        raw_targets = _load_yaml(targets_path)
        assets = raw_targets.get("assets") or []
        chunks = raw_targets.get("chunks") or []
        if isinstance(assets, list):
            for index, asset in enumerate(assets, start=1):
                if not isinstance(asset, dict):
                    continue
                asset_id = str(asset.get("id") or f"asset-{index}")
                doc = str(asset.get("doc") or "")
                targets.append(
                    ReviewTarget(
                        target_type="target_asset",
                        target_id=asset_id,
                        payload={
                            "asset": asset,
                            "section_text": _section_for(doc_sections, doc, asset.get("heading")),
                            "image_refs_in_doc": _image_refs(docs.get(doc, "")),
                        },
                    )
                )
        if isinstance(chunks, list):
            for index, chunk in enumerate(chunks, start=1):
                if not isinstance(chunk, dict):
                    continue
                chunk_id = str(chunk.get("id") or f"chunk-{index}")
                doc = str(chunk.get("doc") or "")
                targets.append(
                    ReviewTarget(
                        target_type="target_chunk",
                        target_id=chunk_id,
                        payload={
                            "chunk": chunk,
                            "section_text": _section_for(doc_sections, doc, chunk.get("heading")),
                            "section_image_refs": _image_refs(
                                _section_for(doc_sections, doc, chunk.get("heading"))
                            ),
                        },
                    )
                )

    return targets


def normalize_review_items(result: Any) -> list[QualityReviewItem]:
    raw_items = result.get("items") if isinstance(result, dict) else result
    if not isinstance(raw_items, list):
        raise ValueError("quality review JSON must be an array or contain items array")
    normalized: list[QualityReviewItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ValueError("quality review item must be an object")
        target_type = str(raw.get("target_type") or "").strip()
        target_id = str(raw.get("target_id") or "").strip()
        decision = str(raw.get("decision") or "").strip().lower()
        if not target_type or not target_id:
            raise ValueError("quality review item missing target_type or target_id")
        if decision not in DECISIONS:
            raise ValueError(f"invalid quality review decision: {decision}")
        score = _coerce_score(raw.get("score"))
        risk_flags = raw.get("risk_flags") or []
        if not isinstance(risk_flags, list):
            risk_flags = [str(risk_flags)]
        normalized.append(
            QualityReviewItem(
                target_type=target_type,
                target_id=target_id,
                decision=decision,
                score=score,
                reason=str(raw.get("reason") or "").strip(),
                suggested_fix=str(raw.get("suggested_fix") or "").strip(),
                risk_flags=[str(flag) for flag in risk_flags if str(flag).strip()],
                raw_json=raw,
            )
        )
    return normalized


def run_quality_review(
    dataset: str,
    dataset_path: Path,
    generated: Path = Path("generated"),
    *,
    retry_failed: bool = False,
    config: MiniMaxConfig | None = None,
    transport: MiniMaxTransport | None = None,
    max_attempts: int | None = None,
) -> str:
    return asyncio.run(
        run_quality_review_async(
            dataset,
            dataset_path,
            generated,
            retry_failed=retry_failed,
            config=config,
            transport=transport,
            max_attempts=max_attempts,
        )
    )


async def run_quality_review_async(
    dataset: str,
    dataset_path: Path,
    generated: Path = Path("generated"),
    *,
    retry_failed: bool = False,
    config: MiniMaxConfig | None = None,
    transport: MiniMaxTransport | None = None,
    max_attempts: int | None = None,
) -> str:
    store = QualityReviewStore(dataset, generated)
    retry_ids = _latest_failed_target_ids(store) if retry_failed else set()
    batch_id = store.start_batch()
    try:
        targets = collect_review_targets(dataset_path)
        if retry_failed:
            targets = [target for target in targets if target.target_id in retry_ids]
        if not targets:
            store.finish_batch(batch_id)
            return batch_id

        tasks = _build_tasks(dataset, targets)
        task_targets = {task.task_id: group for task, group in tasks}
        client = RetryingMiniMaxClient(
            config=config or load_minimax_config(),
            audit=AuditStore(dataset, generated),
            transport=transport,
        )
        results = await client.run_many(
            [task for task, _ in tasks],
            resume=False,
            retry_failed=retry_failed,
            max_attempts=max_attempts,
        )
        for result in results:
            group = task_targets[result.task_id]
            if result.status == "succeeded" and result.result is not None:
                try:
                    items = normalize_review_items(result.result)
                except ValueError as exc:
                    items = _failed_items(group, f"Invalid review JSON: {exc}")
                store.add_items(batch_id, items)
            else:
                store.add_items(
                    batch_id,
                    _failed_items(group, result.error or f"LLM task status: {result.status}"),
                )
        store.finish_batch(batch_id)
        return batch_id
    except Exception as exc:
        store.fail_batch(batch_id, str(exc))
        raise


def _build_tasks(dataset: str, targets: list[ReviewTarget], group_size: int = 8) -> list[tuple[LLMTask, list[ReviewTarget]]]:
    tasks: list[tuple[LLMTask, list[ReviewTarget]]] = []
    for index, group in enumerate(_chunks(targets, group_size), start=1):
        source = json.dumps([_target_payload(target) for target in group], ensure_ascii=False, sort_keys=True)
        task = prompt_task(
            dataset=dataset,
            stage="quality_review",
            prompt_version="v1",
            system=(
                "You are a strict evaluator for retrieval evaluation datasets. "
                "Review corpus documents, queries, targets, and metadata for quality. "
                "Do not assume access to image pixels; judge images by path, heading, "
                "alt text, target metadata, and surrounding Markdown only."
            ),
            user=(
                "Review the following dataset targets. Return a JSON array with one object "
                "per input target. Each object must contain target_type, target_id, decision "
                "(pass, warn, or fail), score from 0 to 100, reason, suggested_fix, and "
                "risk_flags. Allowed risk_flags are ambiguous_query, weak_visual_grounding, "
                "target_mismatch, duplicate, stale_or_invalid_fact, and schema_issue.\n\n"
                f"Dataset: {dataset}\n"
                f"Batch index: {index}\n"
                f"Targets:\n{source}"
            ),
            source=source,
        )
        tasks.append((task, group))
    return tasks


def _target_payload(target: ReviewTarget) -> dict[str, Any]:
    return {
        "target_type": target.target_type,
        "target_id": target.target_id,
        **target.payload,
    }


def _failed_items(targets: list[ReviewTarget], reason: str) -> list[QualityReviewItem]:
    return [
        QualityReviewItem(
            target_type=target.target_type,
            target_id=target.target_id,
            decision="fail",
            score=0,
            reason=reason,
            suggested_fix="Retry the quality review or inspect this target manually.",
            risk_flags=["schema_issue"],
        )
        for target in targets
    ]


def _latest_failed_target_ids(store: QualityReviewStore) -> set[str]:
    latest = store.latest_batch()
    if latest is None:
        return set()
    return {
        str(item["target_id"])
        for item in store.items(str(latest["batch_id"]), decision="fail")
    }


def _chunks(items: list[ReviewTarget], size: int) -> list[list[ReviewTarget]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _sections(text: str) -> dict[str, str]:
    matches = list(HEADING_REF.finditer(text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1).strip()] = text[start:end].strip()
    return sections


def _section_for(doc_sections: dict[str, dict[str, str]], doc: str, heading: Any) -> str:
    if not isinstance(heading, str):
        return ""
    return _truncate(doc_sections.get(doc, {}).get(heading, ""), 4000)


def _image_refs(text: str) -> list[dict[str, str]]:
    return [
        {"alt": match.group(1), "path": match.group(2).strip().split(" ", 1)[0]}
        for match in IMAGE_REF.finditer(text)
    ]


def _load_yaml(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def _query_count(path: Path) -> int:
    if not path.is_file():
        return 0
    queries = _load_yaml(path).get("queries")
    return len(queries) if isinstance(queries, list) else 0


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "\n...[truncated]"


def _coerce_score(value: Any) -> int:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        score = 0
    return max(0, min(100, score))


def _now() -> str:
    return datetime.now(UTC).isoformat()

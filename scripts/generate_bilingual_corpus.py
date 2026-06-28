from __future__ import annotations

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from dikw_data.audit import AuditRecord, AuditStore
from dikw_data.llm_client import RetryingMiniMaxClient, TaskResult
from dikw_data.pipeline import add_provider_args, load_config_from_args
from dikw_data.tasks import LLMTask, hash_text

PROMPT_VERSION = "v1"
MISSING_PROMPT_VERSION = "v5-clean"

# Corpus frontmatter provenance marker, by provider.
SOURCE_MARKERS = {
    "minimax": "minimax-synthetic",
    "deepseek": "deepseek-synthetic",
    "codex": "openai-codex-synthetic",
}


@dataclass(frozen=True)
class CorpusTaskMeta:
    stem: str
    language: str
    title: str


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a bilingual synthetic Markdown corpus."
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--topic", default="DIKW knowledge engine evaluation corpus")
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--max-attempts", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--materialize-only", action="store_true")
    parser.add_argument("--only-missing", action="store_true")
    add_provider_args(parser)
    args = parser.parse_args()

    indices = missing_indices(args.dataset, args.count) if args.only_missing else None
    prompt_version = MISSING_PROMPT_VERSION if args.only_missing else PROMPT_VERSION
    tasks, meta_by_task_id = build_tasks(
        dataset=args.dataset,
        topic=args.topic,
        count=args.count,
        indices=indices,
        prompt_version=prompt_version,
    )
    config = load_config_from_args(args)
    source_marker = SOURCE_MARKERS[args.provider]
    audit = AuditStore(args.dataset)
    if args.materialize_only:
        written = materialize_corpus(
            args.dataset,
            [],
            audit=audit,
            meta_by_task_id=meta_by_task_id,
            source_marker=source_marker,
        )
        print(f"wrote {written} corpus files under datasets/{args.dataset}/corpus")
        return 0
    client = RetryingMiniMaxClient(config=config, audit=audit)
    results = asyncio.run(
        client.run_many(
            tasks,
            concurrency=args.concurrency,
            resume=args.resume,
            retry_failed=args.retry_failed,
            max_attempts=args.max_attempts,
            dry_run=args.dry_run,
        )
    )

    for result in results:
        print(
            {
                "task_id": result.task_id,
                "status": result.status,
                "attempts": result.attempts,
                "skipped": result.skipped,
                "error": result.error,
            }
        )

    if args.dry_run:
        return 0

    written = materialize_corpus(
        args.dataset,
        results,
        audit=audit,
        meta_by_task_id=meta_by_task_id,
        source_marker=source_marker,
    )
    print(f"wrote {written} corpus files under datasets/{args.dataset}/corpus")
    return 1 if any(r.status in {"failed", "needs_manual_review"} for r in results) else 0


def build_tasks(
    *,
    dataset: str,
    topic: str,
    count: int,
    indices: list[int] | None = None,
    prompt_version: str = PROMPT_VERSION,
) -> tuple[list[LLMTask], dict[str, CorpusTaskMeta]]:
    tasks: list[LLMTask] = []
    meta_by_task_id: dict[str, CorpusTaskMeta] = {}
    for index in (indices if indices is not None else list(range(1, count + 1))):
        language = "zh" if index % 2 else "en"
        language_name = "Chinese" if language == "zh" else "English"
        stem = f"{language}-synthetic-{index:03d}"
        title = (
            f"DIKW 知识引擎评测文档 {index:03d}"
            if language == "zh"
            else f"DIKW Knowledge Engine Evaluation Note {index:03d}"
        )
        system = (
            "You write synthetic but internally consistent Markdown documents "
            "for retrieval-evaluation corpora."
        )
        user = (
            f"Write one {language_name} Markdown document for a DIKW/RAG retrieval "
            f"evaluation corpus. Topic: {topic}. Document title: {title}. "
            "Make it 180-320 words for English or 280-480 Chinese characters for Chinese. "
            "Include concrete named concepts, implementation tradeoffs, failure modes, "
            "and at least two section headings. Avoid mentioning that the document is synthetic. "
            "Output Markdown only. Do not output JSON. Do not wrap the document in code fences."
        )
        if prompt_version == MISSING_PROMPT_VERSION:
            if language == "zh":
                user = (
                    f"Write the document body in Simplified Chinese. Title: {title}. "
                    f"Topic: {topic}. Produce 220 to 360 Chinese characters. "
                    "Include one H1 heading, two H2 headings, concrete DIKW/RAG concepts, "
                    "one implementation tradeoff, and one failure mode. Output Markdown only. "
                    "Do not output JSON, code fences, analysis, counting notes, or explanation."
                )
            else:
                user = (
                    f"Write one English Markdown document. Title: {title}. Topic: {topic}. "
                    "Produce 180 to 260 words. Include one H1 heading and at least two H2 headings. "
                    "Mention concrete DIKW/RAG concepts, one implementation tradeoff, and one failure mode. "
                    "Output Markdown only. Do not output JSON, code fences, analysis, or explanation."
                )
        source = f"{dataset}:{topic}:{index}:{language}:{stem}:{prompt_version}"
        task = LLMTask(
            dataset=dataset,
            stage="generate_bilingual_corpus",
            source_hash=hash_text(source),
            prompt_version=prompt_version,
            system=system,
            user=user,
            expected_json=False,
        )
        tasks.append(task)
        meta_by_task_id[task.task_id] = CorpusTaskMeta(stem=stem, language=language, title=title)
    return tasks, meta_by_task_id


def missing_indices(dataset: str, count: int) -> list[int]:
    corpus_dir = Path("datasets") / dataset / "corpus"
    missing: list[int] = []
    for index in range(1, count + 1):
        language = "zh" if index % 2 else "en"
        stem = f"{language}-synthetic-{index:03d}.md"
        if not (corpus_dir / stem).is_file():
            missing.append(index)
    return missing


def materialize_corpus(
    dataset: str,
    results: list[TaskResult],
    *,
    audit: AuditStore | None = None,
    meta_by_task_id: dict[str, CorpusTaskMeta] | None = None,
    source_marker: str = "minimax-synthetic",
) -> int:
    corpus_dir = Path("datasets") / dataset / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    seen: set[str] = set()
    if audit is not None:
        for record in audit.records(stage="generate_bilingual_corpus", status="succeeded"):
            written += _write_result(
                corpus_dir, record, seen, meta_by_task_id or {}, source_marker
            )
    for result in results:
        written += _write_result(
            corpus_dir, result, seen, meta_by_task_id or {}, source_marker
        )
    return written


def _write_result(
    corpus_dir: Path,
    result: TaskResult | AuditRecord,
    seen: set[str],
    meta_by_task_id: dict[str, CorpusTaskMeta],
    source_marker: str,
) -> int:
    result_json = result.result if isinstance(result, TaskResult) else result.result_json
    if result.status != "succeeded" or result_json is None:
        return 0
    meta = meta_by_task_id.get(result.task_id)
    if isinstance(result_json, dict) and isinstance(result_json.get("text"), str):
        stem = _safe_stem(meta.stem if meta else result.task_id)
        if stem in seen:
            return 0
        seen.add(stem)
        title = meta.title if meta else stem
        language = meta.language if meta else ""
        markdown = result_json["text"].strip()
        if not markdown:
            return 0
        if not markdown.lstrip().startswith("#"):
            markdown = f"# {title}\n\n{markdown}"
        _write_markdown(corpus_dir, stem, title, language, markdown, source_marker)
        return 1
    written = 0
    docs = result_json if isinstance(result_json, list) else [result_json]
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        stem = _safe_stem(str(doc.get("stem") or result.task_id))
        if stem in seen:
            continue
        seen.add(stem)
        language = str(doc.get("language") or "").lower()
        title = str(doc.get("title") or stem)
        markdown = str(doc.get("markdown") or "").strip()
        if not markdown:
            continue
        if not markdown.lstrip().startswith("#"):
            markdown = f"# {title}\n\n{markdown}"
        _write_markdown(corpus_dir, stem, title, language, markdown, source_marker)
        written += 1
    return written


def _write_markdown(
    corpus_dir: Path,
    stem: str,
    title: str,
    language: str,
    markdown: str,
    source_marker: str = "minimax-synthetic",
) -> None:
    prefix = "---\n"
    prefix += f"title: {title}\n"
    if language:
        prefix += f"language: {language}\n"
    prefix += f"source: {source_marker}\n---\n\n"
    (corpus_dir / f"{stem}.md").write_text(prefix + markdown + "\n", encoding="utf-8")


def _safe_stem(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "synthetic-doc"


if __name__ == "__main__":
    sys.exit(main())

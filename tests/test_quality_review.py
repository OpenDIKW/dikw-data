from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from dikw_data.config import MiniMaxConfig, RetryPolicy
from dikw_data.quality_review import (
    QualityReviewItem,
    QualityReviewStore,
    ReviewTarget,
    _build_tasks,
    collect_review_targets,
    normalize_review_items,
    run_quality_review_async,
)


def test_quality_review_store_creates_batch_items_and_stats(tmp_path: Path) -> None:
    store = QualityReviewStore("demo", tmp_path)

    batch_id = store.start_batch()
    store.add_items(
        batch_id,
        [
            QualityReviewItem(
                target_type="corpus_doc",
                target_id="alpha",
                decision="pass",
                score=92,
                reason="Clear and focused.",
                suggested_fix="",
                risk_flags=[],
            ),
            QualityReviewItem(
                target_type="query",
                target_id="q1",
                decision="fail",
                score=30,
                reason="Expected document is wrong.",
                suggested_fix="Point it at alpha.",
                risk_flags=["target_mismatch"],
            ),
        ],
    )
    store.finish_batch(batch_id)

    latest = store.latest_batch()
    assert latest is not None
    assert latest["status"] == "succeeded"
    assert store.running_batch() is None
    assert store.stats(batch_id) == {"pass": 1, "warn": 0, "fail": 1}
    assert [item["target_id"] for item in store.items(batch_id, decision="fail")] == ["q1"]


def test_quality_review_store_allows_only_one_running_batch(tmp_path: Path) -> None:
    store = QualityReviewStore("demo", tmp_path)
    store.start_batch()

    try:
        store.start_batch()
    except RuntimeError as exc:
        assert "already running" in str(exc)
    else:
        raise AssertionError("expected running batch guard")


def test_collect_review_targets_includes_text_and_multimodal_metadata(tmp_path: Path) -> None:
    dataset = tmp_path / "datasets" / "demo"
    corpus = dataset / "corpus"
    image_dir = corpus / "images" / "fruits"
    image_dir.mkdir(parents=True)
    (image_dir / "apple.png").write_bytes(b"png")
    (corpus / "fruits.md").write_text(
        "# Fruits\n\n"
        "## 苹果 / Apple\n\n"
        "Target: fruits.apple\n\n"
        "![苹果 / Apple](images/fruits/apple.png)\n\n"
        "苹果是红色圆形水果。\n",
        encoding="utf-8",
    )
    (dataset / "queries.yaml").write_text(
        "queries:\n"
        "  - id: q1\n"
        "    query_type: asset\n"
        "    q: 哪张图片是红色苹果？\n"
        "    expect_any: [fruits]\n"
        "    expect_asset_any: [fruits.apple.image]\n",
        encoding="utf-8",
    )
    (dataset / "targets.yaml").write_text(
        "assets:\n"
        "  - id: fruits.apple.image\n"
        "    doc: fruits\n"
        "    path: images/fruits/apple.png\n"
        "    heading: 苹果 / Apple\n"
        "chunks:\n"
        "  - id: fruits.apple.text\n"
        "    doc: fruits\n"
        "    heading: 苹果 / Apple\n"
        "    anchor: fruits.apple\n"
        "    asset_id: fruits.apple.image\n",
        encoding="utf-8",
    )

    targets = collect_review_targets(dataset)
    by_id = {target.target_id: target for target in targets}

    assert by_id["fruits"].target_type == "corpus_doc"
    assert by_id["q1"].target_type == "query"
    assert by_id["fruits.apple.image"].target_type == "target_asset"
    assert by_id["fruits.apple.text"].target_type == "target_chunk"
    assert "苹果是红色圆形水果" in by_id["fruits.apple.text"].payload["section_text"]


def test_collect_review_targets_summarizes_negative_queries_for_dataset_review(tmp_path: Path) -> None:
    dataset = tmp_path / "datasets" / "demo"
    corpus = dataset / "corpus"
    corpus.mkdir(parents=True)
    (dataset / "dataset.yaml").write_text("name: demo\nthresholds: {}\n", encoding="utf-8")
    (corpus / "alpha.md").write_text("# Alpha\n\nA focused document.", encoding="utf-8")
    (dataset / "queries.yaml").write_text(
        "queries:\n"
        "  - id: q1\n"
        "    q: What is Alpha about?\n"
        "    expect_any: [alpha]\n"
        "  - id: q2\n"
        "    q: What is the weather today?\n"
        "    expect_none: true\n",
        encoding="utf-8",
    )

    dataset_target = collect_review_targets(dataset)[0]

    assert dataset_target.target_type == "dataset"
    assert dataset_target.payload["dataset_mode"] == "text_doc_level"
    assert dataset_target.payload["query_summary"] == {
        "total": 2,
        "positive": 1,
        "negative_expect_none": 1,
        "missing_expect_any_docs": [],
        "positive_expect_any_docs": ["alpha"],
    }
    assert "optional" in dataset_target.payload["targets_yaml_note"]


def test_collect_review_targets_adds_expected_doc_context_to_positive_queries(tmp_path: Path) -> None:
    dataset = tmp_path / "datasets" / "demo"
    corpus = dataset / "corpus"
    corpus.mkdir(parents=True)
    (corpus / "alpha.md").write_text(
        "# Alpha\n\n## Main Point\n\nAlpha explains a specific retrieval fact.",
        encoding="utf-8",
    )
    (dataset / "queries.yaml").write_text(
        "queries:\n"
        "  - id: q1\n"
        "    q: What retrieval fact does Alpha explain?\n"
        "    expect_any: [alpha]\n",
        encoding="utf-8",
    )

    by_id = {target.target_id: target for target in collect_review_targets(dataset)}

    query_payload = by_id["q1"].payload
    assert query_payload["query_role"] == "positive"
    assert query_payload["expected_doc_contexts"] == [
        {
            "doc": "alpha",
            "exists": True,
            "headings": ["Main Point"],
            "text": "# Alpha\n\n## Main Point\n\nAlpha explains a specific retrieval fact.",
        }
    ]


def test_quality_review_prompt_explains_expect_none_and_text_targets_yaml() -> None:
    task, _ = _build_tasks(
        "demo",
        [
            ReviewTarget(
                target_type="dataset",
                target_id="demo",
                payload={"dataset_mode": "text_doc_level"},
            ),
        ],
    )[0]

    assert "expect_none=true marks an intentional negative query" in task.user
    assert "targets.yaml is optional for text_doc_level datasets" in task.user
    assert "query targets include expected_doc_contexts" in task.user


def test_normalize_review_items_accepts_items_wrapper_and_clamps_score() -> None:
    items = normalize_review_items(
        {
            "items": [
                {
                    "target_type": "query",
                    "target_id": "q1",
                    "decision": "WARN",
                    "score": 120,
                    "reason": "Too revealing.",
                    "suggested_fix": "Make it less direct.",
                    "risk_flags": ["ambiguous_query", 3],
                }
            ]
        }
    )

    assert len(items) == 1
    item = items[0]
    assert item.target_type == "query"
    assert item.target_id == "q1"
    assert item.decision == "warn"
    assert item.score == 100
    assert item.reason == "Too revealing."
    assert item.suggested_fix == "Make it less direct."
    assert item.risk_flags == ["ambiguous_query", "3"]
    assert item.raw_json is not None


class FakeTransport:
    def __init__(self, outcomes: list[str]) -> None:
        self.outcomes = outcomes
        self.calls = 0

    async def complete(self, *, system: str, user: str, model: str) -> str:
        _ = (system, user, model)
        outcome = self.outcomes[self.calls]
        self.calls += 1
        return outcome


def make_config() -> MiniMaxConfig:
    return MiniMaxConfig(
        model="MiniMax-M2.7",
        base_url="https://api.minimaxi.com/anthropic",
        timeout_seconds=120,
        sdk_max_retries=0,
        retry_policy=RetryPolicy(
            max_attempts=2,
            initial_backoff_seconds=0,
            max_backoff_seconds=0,
            jitter=False,
            timeout_seconds=120,
        ),
        concurrency=1,
    )


@pytest.mark.asyncio
async def test_quality_review_uses_json_repair_and_audit_stage(tmp_path: Path) -> None:
    dataset = tmp_path / "datasets" / "demo"
    corpus = dataset / "corpus"
    corpus.mkdir(parents=True)
    (corpus / "alpha.md").write_text("# Alpha\n\nA focused document.", encoding="utf-8")
    (dataset / "queries.yaml").write_text(
        "queries:\n  - id: q1\n    q: What is Alpha about?\n    expect_any: [alpha]\n",
        encoding="utf-8",
    )
    transport = FakeTransport(
        [
            "not json",
            """
            [
              {
                "target_type": "corpus_doc",
                "target_id": "alpha",
                "decision": "pass",
                "score": 90,
                "reason": "Clear document.",
                "suggested_fix": "",
                "risk_flags": []
              },
              {
                "target_type": "query",
                "target_id": "q1",
                "decision": "pass",
                "score": 88,
                "reason": "Natural query.",
                "suggested_fix": "",
                "risk_flags": []
              }
            ]
            """,
        ]
    )

    batch_id = await run_quality_review_async(
        "demo",
        dataset,
        tmp_path / "generated",
        config=make_config(),
        transport=transport,
    )

    store = QualityReviewStore("demo", tmp_path / "generated")
    assert store.stats(batch_id) == {"pass": 2, "warn": 0, "fail": 0}
    assert transport.calls == 2
    audit_db = tmp_path / "generated" / "demo" / "audit.sqlite"
    assert audit_db.is_file()
    with sqlite3.connect(audit_db) as conn:
        rows = conn.execute("select stage, status from llm_tasks").fetchall()
    assert rows == [("quality_review", "succeeded")]

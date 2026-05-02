from __future__ import annotations

import sqlite3
import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from dikw_data.quality_review import QualityReviewItem, QualityReviewStore
from web.app import create_app


def make_dataset(root: Path, name: str = "demo") -> Path:
    dataset = root / "datasets" / name
    corpus = dataset / "corpus"
    corpus.mkdir(parents=True)
    (dataset / "dataset.yaml").write_text(
        "name: demo\nthresholds: {}\n", encoding="utf-8"
    )
    (corpus / "alpha.md").write_text("# Alpha\n\nA test document.", encoding="utf-8")
    return dataset


def write_audit(root: Path, dataset: str = "demo") -> None:
    generated = root / "generated" / dataset
    generated.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(generated / "audit.sqlite") as conn:
        conn.execute(
            """
            create table llm_tasks (
                task_id text primary key,
                dataset text not null,
                stage text not null,
                status text not null,
                attempts integer not null,
                last_error text,
                raw_response text,
                result_json text,
                created_at text not null,
                updated_at text not null
            )
            """
        )
        conn.execute(
            """
            insert into llm_tasks (
                task_id, dataset, stage, status, attempts, last_error,
                raw_response, result_json, created_at, updated_at
            )
            values ('task-1', 'demo', 'generate_candidates', 'failed', 3,
                    'rate limited', null, null, 'now', 'now')
            """
        )


def test_dataset_pages_show_corpus_and_audit_status(tmp_path: Path) -> None:
    make_dataset(tmp_path)
    write_audit(tmp_path)
    client = TestClient(create_app(tmp_path))

    index = client.get("/")
    assert index.status_code == 200
    assert "demo" in index.text

    dataset = client.get("/datasets/demo")
    assert dataset.status_code == 200
    assert "alpha.md" in dataset.text
    assert "failed" in dataset.text
    assert "Review candidates" in dataset.text
    assert "LLM Generation Audit" in dataset.text
    assert "LLM Quality Review" in dataset.text

    audit = client.get("/datasets/demo/audit")
    assert audit.status_code == 200
    assert "generate_candidates" in audit.text
    assert "rate limited" in audit.text


def test_dataset_page_counts_languages_from_frontmatter(tmp_path: Path) -> None:
    dataset = tmp_path / "datasets" / "demo"
    corpus = dataset / "corpus"
    corpus.mkdir(parents=True)
    (dataset / "dataset.yaml").write_text("name: demo\nthresholds: {}\n", encoding="utf-8")
    (corpus / "chinese-history.md").write_text(
        "---\nlanguage: zh\n---\n\n# 中文文档\n",
        encoding="utf-8",
    )
    (corpus / "world-history.md").write_text(
        "---\nlanguage: en\n---\n\n# English Document\n",
        encoding="utf-8",
    )
    (corpus / "gallery.md").write_text(
        "---\nlanguage: zh-CN\n---\n\n# 多图文档\n",
        encoding="utf-8",
    )
    client = TestClient(create_app(tmp_path))

    response = client.get("/datasets/demo")

    assert response.status_code == 200
    assert "Chinese: 2" in response.text
    assert "English: 1" in response.text


def test_corpus_preview_renders_local_images_and_blocks_traversal(tmp_path: Path) -> None:
    dataset = make_dataset(tmp_path)
    image_dir = dataset / "corpus" / "images" / "fruits"
    image_dir.mkdir(parents=True)
    (image_dir / "apple.png").write_bytes(b"fake-png")
    (dataset / "corpus" / "gallery.md").write_text(
        "# Gallery\n\n![Apple](images/fruits/apple.png)\n",
        encoding="utf-8",
    )
    client = TestClient(create_app(tmp_path))

    page = client.get("/datasets/demo/corpus/gallery.md")

    assert page.status_code == 200
    assert "/datasets/demo/asset/images/fruits/apple.png" in page.text
    assert client.get("/datasets/demo/asset/images/fruits/apple.png").status_code == 200
    assert client.get("/datasets/demo/asset/../dataset.yaml").status_code == 404


def test_review_page_loads_candidates_and_persists_decisions(tmp_path: Path) -> None:
    make_dataset(tmp_path)
    generated = tmp_path / "generated" / "demo"
    generated.mkdir(parents=True)
    write_audit(tmp_path)
    (generated / "demo.jsonl").write_text(
        json.dumps(
            {
                "task_id": "task-2",
                "dataset": "demo",
                "stage": "generate_candidates",
                "status": "succeeded",
                "attempts": 1,
                "last_error": None,
                "result": [
                    {
                        "id": "cand-1",
                        "q": "What does Alpha describe?",
                        "expect_any": ["alpha"],
                        "evidence": "A test document.",
                        "confidence": 0.9,
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    client = TestClient(create_app(tmp_path))

    review = client.get("/datasets/demo/review")
    assert review.status_code == 200
    assert "What does Alpha describe?" in review.text
    assert "pending" in review.text
    assert "attempts 3" in review.text

    saved = client.post(
        "/datasets/demo/review/cand-1",
        data={
            "decision": "rewrite",
            "edited_q": "Which document describes Alpha?",
            "edited_expect_any": "alpha",
            "notes": "clearer wording",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303

    refreshed = client.get("/datasets/demo/review")
    assert "rewrite" in refreshed.text
    assert "Which document describes Alpha?" in refreshed.text
    assert "clearer wording" in refreshed.text


def test_export_writes_only_approved_and_rewritten_queries(tmp_path: Path) -> None:
    make_dataset(tmp_path)
    generated = tmp_path / "generated" / "demo"
    generated.mkdir(parents=True)
    (generated / "candidates.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"id": "approved", "q": "Approved?", "expect_any": ["alpha"]}),
                json.dumps({"id": "rewritten", "q": "Original?", "expect_any": ["alpha"]}),
                json.dumps({"id": "rejected", "q": "Rejected?", "expect_any": ["alpha"]}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    client = TestClient(create_app(tmp_path))
    client.post(
        "/datasets/demo/review/approved",
        data={"decision": "approve", "edited_q": "", "edited_expect_any": ""},
    )
    client.post(
        "/datasets/demo/review/rewritten",
        data={
            "decision": "rewrite",
            "edited_q": "Rewritten?",
            "edited_expect_any": "alpha",
        },
    )
    client.post(
        "/datasets/demo/review/rejected",
        data={"decision": "reject", "edited_q": "", "edited_expect_any": ""},
    )

    exported = client.post("/datasets/demo/export-queries")

    assert exported.status_code == 200
    assert "Exported 2 reviewed queries" in exported.text
    queries = yaml.safe_load((tmp_path / "datasets" / "demo" / "queries.yaml").read_text(encoding="utf-8"))
    assert queries == {
        "queries": [
            {"id": "approved", "q": "Approved?", "expect_any": ["alpha"]},
            {"id": "rewritten", "q": "Rewritten?", "expect_any": ["alpha"]},
        ]
    }


def test_export_rejects_missing_expected_docs_without_overwriting(tmp_path: Path) -> None:
    dataset = make_dataset(tmp_path)
    queries_path = dataset / "queries.yaml"
    queries_path.write_text("queries: []\n", encoding="utf-8")
    generated = tmp_path / "generated" / "demo"
    generated.mkdir(parents=True)
    (generated / "candidates.jsonl").write_text(
        json.dumps({"id": "bad", "q": "Bad?", "expect_any": ["missing"]}) + "\n",
        encoding="utf-8",
    )
    client = TestClient(create_app(tmp_path))
    client.post("/datasets/demo/review/bad", data={"decision": "approve"})

    exported = client.post("/datasets/demo/export-queries")

    assert exported.status_code == 200
    assert "references missing stem: missing" in exported.text
    assert queries_path.read_text(encoding="utf-8") == "queries: []\n"


def test_quality_review_run_creates_batch_and_displays_items(tmp_path: Path) -> None:
    make_dataset(tmp_path)

    def fake_runner(dataset: str, dataset_path: Path, generated: Path, retry_failed: bool) -> None:
        assert dataset == "demo"
        assert dataset_path.name == "demo"
        assert retry_failed is False
        store = QualityReviewStore(dataset, generated)
        batch_id = store.start_batch()
        store.add_items(
            batch_id,
            [
                QualityReviewItem(
                    target_type="corpus_doc",
                    target_id="alpha",
                    decision="warn",
                    score=72,
                    reason="Document is usable but thin.",
                    suggested_fix="Add more concrete retrieval facts.",
                    risk_flags=["ambiguous_query"],
                )
            ],
        )
        store.finish_batch(batch_id)

    client = TestClient(create_app(tmp_path, quality_review_runner=fake_runner))

    response = client.post("/datasets/demo/quality-review/run")

    assert response.status_code == 200
    page = client.get("/datasets/demo/quality-review?decision=warn")
    assert page.status_code == 200
    assert "corpus_doc" in page.text
    assert "alpha" in page.text
    assert "warn" in page.text
    assert "Document is usable but thin." in page.text
    assert "Add more concrete retrieval facts." in page.text


def test_quality_review_run_does_not_duplicate_running_batch(tmp_path: Path) -> None:
    make_dataset(tmp_path)
    QualityReviewStore("demo", tmp_path / "generated").start_batch()
    calls = 0

    def fake_runner(dataset: str, dataset_path: Path, generated: Path, retry_failed: bool) -> None:
        nonlocal calls
        calls += 1

    client = TestClient(create_app(tmp_path, quality_review_runner=fake_runner))

    response = client.post("/datasets/demo/quality-review/run")

    assert response.status_code == 200
    assert calls == 0
    assert "already running" in response.text

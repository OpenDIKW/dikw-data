from __future__ import annotations

from pathlib import Path

from scripts.validate_dataset import validate


def write_base_dataset(root: Path, chunk_extra: str) -> Path:
    dataset = root / "dataset"
    corpus = dataset / "corpus"
    images = corpus / "images" / "fruits"
    images.mkdir(parents=True)
    (dataset / "dataset.yaml").write_text("name: dataset\nthresholds: {}\n", encoding="utf-8")
    (dataset / "queries.yaml").write_text(
        "queries:\n"
        "  - id: q1\n"
        "    q: test\n"
        "    expect_any: [doc]\n",
        encoding="utf-8",
    )
    (images / "apple.png").write_bytes(b"png")
    (images / "banana.png").write_bytes(b"png")
    (corpus / "doc.md").write_text(
        "## Fruit Group\n\n"
        "Target: groups.fruit\n\n"
        "![Apple](images/fruits/apple.png)\n\n"
        "![Banana](images/fruits/banana.png)\n",
        encoding="utf-8",
    )
    (dataset / "targets.yaml").write_text(
        "assets:\n"
        "  - id: fruits.apple.image\n"
        "    doc: doc\n"
        "    path: images/fruits/apple.png\n"
        "    heading: Fruit Group\n"
        "  - id: fruits.banana.image\n"
        "    doc: doc\n"
        "    path: images/fruits/banana.png\n"
        "    heading: Fruit Group\n"
        "chunks:\n"
        "  - id: groups.fruit.text\n"
        "    doc: doc\n"
        "    heading: Fruit Group\n"
        "    anchor: groups.fruit\n"
        f"{chunk_extra}",
        encoding="utf-8",
    )
    return dataset


def test_validate_accepts_single_asset_id_chunk(tmp_path: Path) -> None:
    dataset = write_base_dataset(tmp_path, "    asset_id: fruits.apple.image\n")

    assert validate(dataset) == []


def test_validate_accepts_multi_asset_ids_chunk(tmp_path: Path) -> None:
    dataset = write_base_dataset(
        tmp_path,
        "    asset_ids:\n"
        "      - fruits.apple.image\n"
        "      - fruits.banana.image\n",
    )

    assert validate(dataset) == []


def test_validate_rejects_empty_asset_ids_chunk(tmp_path: Path) -> None:
    dataset = write_base_dataset(tmp_path, "    asset_ids: []\n")

    errors = validate(dataset)

    assert "asset_ids must be a non-empty list" in "\n".join(errors)


def test_validate_rejects_unknown_asset_ids_chunk(tmp_path: Path) -> None:
    dataset = write_base_dataset(
        tmp_path,
        "    asset_ids:\n"
        "      - fruits.missing.image\n",
    )

    errors = validate(dataset)

    assert "references missing asset target: fruits.missing.image" in "\n".join(errors)


def test_validate_rejects_missing_query_id(tmp_path: Path) -> None:
    dataset = write_base_dataset(tmp_path, "    asset_id: fruits.apple.image\n")
    (dataset / "queries.yaml").write_text(
        "queries:\n"
        "  - q: test\n"
        "    expect_any: [doc]\n",
        encoding="utf-8",
    )

    errors = validate(dataset)

    assert "query #1 has empty id" in "\n".join(errors)


def test_validate_rejects_duplicate_query_id(tmp_path: Path) -> None:
    dataset = write_base_dataset(tmp_path, "    asset_id: fruits.apple.image\n")
    (dataset / "queries.yaml").write_text(
        "queries:\n"
        "  - id: q1\n"
        "    q: test one\n"
        "    expect_any: [doc]\n"
        "  - id: q1\n"
        "    q: test two\n"
        "    expect_any: [doc]\n",
        encoding="utf-8",
    )

    errors = validate(dataset)

    assert "duplicate query id: q1" in "\n".join(errors)

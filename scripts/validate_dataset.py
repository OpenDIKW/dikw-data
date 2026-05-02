from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - used by minimal local runtimes
    yaml = None


SUPPORTED_THRESHOLDS = {"hit_at_3", "hit_at_10", "mrr", "ndcg_at_10", "recall_at_100"}
IMAGE_REF = re.compile(r"!\[[^\]]*\]\(([^)\n]+)\)")


def load_yaml(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(text) or {}
    return parse_simple_yaml(text)


def parse_simple_yaml(text: str) -> dict:
    """Parse the simple YAML subset used by this repo's dataset files."""
    lines = text.splitlines()
    result: dict = {}
    i = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip() or raw.lstrip().startswith("#") or raw.startswith(" "):
            i += 1
            continue
        if ":" not in raw:
            i += 1
            continue
        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == ">":
            block: list[str] = []
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith(" ")):
                if lines[i].strip():
                    block.append(lines[i].strip())
                i += 1
            result[key] = "\n".join(block)
            continue
        if value:
            result[key] = parse_simple_value(value)
            i += 1
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and lines[j].startswith("  - "):
            result[key], i = parse_simple_list(lines, j)
            continue
        result[key], i = parse_simple_mapping(lines, j)
    return result


def parse_simple_list(lines: list[str], start: int) -> tuple[list[dict], int]:
    items: list[dict] = []
    current: dict | None = None
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if not line.startswith(" "):
            break
        if line.startswith("  - "):
            if current is not None:
                items.append(current)
            current = {}
            payload = line[4:].strip()
            if payload and ":" in payload:
                k, v = payload.split(":", 1)
                current[k.strip()] = parse_simple_value(v.strip())
        elif line.startswith("    ") and current is not None and ":" in line:
            k, v = line.strip().split(":", 1)
            current[k.strip()] = parse_simple_value(v.strip())
        i += 1
    if current is not None:
        items.append(current)
    return items, i


def parse_simple_mapping(lines: list[str], start: int) -> tuple[dict, int]:
    mapping: dict = {}
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if not line.startswith("  "):
            break
        if ":" in line:
            k, v = line.strip().split(":", 1)
            mapping[k.strip()] = parse_simple_value(v.strip())
        i += 1
    return mapping, i


def parse_simple_value(value: str):
    value = value.strip()
    if value == "{}":
        return {}
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_simple_value(part.strip()) for part in inner.split(",")]
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    try:
        return float(value) if "." in value else int(value)
    except ValueError:
        return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a dikw eval dataset.")
    parser.add_argument("dataset")
    args = parser.parse_args()
    errors = validate(Path(args.dataset))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("dataset valid")
    return 0


def validate(dataset_dir: Path) -> list[str]:
    errors: list[str] = []
    if not dataset_dir.is_dir():
        return [f"dataset directory not found: {dataset_dir}"]
    meta_path = dataset_dir / "dataset.yaml"
    queries_path = dataset_dir / "queries.yaml"
    targets_path = dataset_dir / "targets.yaml"
    corpus_dir = dataset_dir / "corpus"

    if not meta_path.is_file():
        errors.append("missing dataset.yaml")
    if not queries_path.is_file():
        errors.append("missing queries.yaml")
    if not corpus_dir.is_dir():
        errors.append("missing corpus/")
        return errors

    md_paths = sorted(corpus_dir.glob("*.md"))
    stems = {p.stem for p in md_paths}
    if not stems:
        errors.append("corpus/ has no markdown files")

    target_assets: set[str] = set()
    target_chunks: set[str] = set()
    if targets_path.is_file():
        raw_targets = load_yaml(targets_path)
        assets = raw_targets.get("assets")
        chunks = raw_targets.get("chunks")
        if not isinstance(assets, list) or not assets:
            errors.append("targets.yaml must contain non-empty assets list")
        else:
            for index, asset in enumerate(assets, start=1):
                if not isinstance(asset, dict):
                    errors.append(f"asset target #{index} must be a mapping")
                    continue
                asset_id = asset.get("id")
                doc = asset.get("doc")
                path = asset.get("path")
                heading = asset.get("heading")
                if not isinstance(asset_id, str) or not asset_id:
                    errors.append(f"asset target #{index} has empty id")
                else:
                    target_assets.add(asset_id)
                if doc not in stems:
                    errors.append(f"asset target #{index} references missing doc: {doc}")
                if not isinstance(path, str) or not path:
                    errors.append(f"asset target #{index} has empty path")
                elif not (corpus_dir / path).is_file():
                    errors.append(f"asset target #{index} references missing file: {path}")
                if not isinstance(heading, str) or not heading:
                    errors.append(f"asset target #{index} has empty heading")
                elif isinstance(doc, str) and (corpus_dir / f"{doc}.md").is_file():
                    text = (corpus_dir / f"{doc}.md").read_text(encoding="utf-8")
                    if f"## {heading}" not in text:
                        errors.append(
                            f"asset target #{index} heading not found in {doc}.md: {heading}"
                        )
        if not isinstance(chunks, list) or not chunks:
            errors.append("targets.yaml must contain non-empty chunks list")
        else:
            for index, chunk in enumerate(chunks, start=1):
                if not isinstance(chunk, dict):
                    errors.append(f"chunk target #{index} must be a mapping")
                    continue
                chunk_id = chunk.get("id")
                doc = chunk.get("doc")
                heading = chunk.get("heading")
                anchor = chunk.get("anchor")
                asset_id = chunk.get("asset_id")
                asset_ids = chunk.get("asset_ids")
                if not isinstance(chunk_id, str) or not chunk_id:
                    errors.append(f"chunk target #{index} has empty id")
                else:
                    target_chunks.add(chunk_id)
                if doc not in stems:
                    errors.append(f"chunk target #{index} references missing doc: {doc}")
                    continue
                text = (corpus_dir / f"{doc}.md").read_text(encoding="utf-8")
                if not isinstance(heading, str) or not heading:
                    errors.append(f"chunk target #{index} has empty heading")
                elif f"## {heading}" not in text:
                    errors.append(
                        f"chunk target #{index} heading not found in {doc}.md: {heading}"
                    )
                if not isinstance(anchor, str) or not anchor:
                    errors.append(f"chunk target #{index} has empty anchor")
                elif f"Target: {anchor}" not in text:
                    errors.append(
                        f"chunk target #{index} anchor not found in {doc}.md: {anchor}"
                    )
                has_asset_id = isinstance(asset_id, str) and bool(asset_id)
                has_asset_ids = isinstance(asset_ids, list) and bool(asset_ids)
                if has_asset_id and has_asset_ids:
                    errors.append(f"chunk target #{index} must not set both asset_id and asset_ids")
                elif has_asset_id:
                    if target_assets and asset_id not in target_assets:
                        errors.append(
                            f"chunk target #{index} references missing asset target: {asset_id}"
                        )
                elif has_asset_ids:
                    for item in asset_ids:
                        if not isinstance(item, str) or not item:
                            errors.append(f"chunk target #{index} asset_ids contains empty id")
                        elif target_assets and item not in target_assets:
                            errors.append(
                                f"chunk target #{index} references missing asset target: {item}"
                            )
                elif asset_ids is not None:
                    errors.append(f"chunk target #{index} asset_ids must be a non-empty list")
                else:
                    errors.append(f"chunk target #{index} has empty asset_id")

    for md_path in md_paths:
        text = md_path.read_text(encoding="utf-8")
        for ref in IMAGE_REF.findall(text):
            raw_path = ref.strip().split(" ", 1)[0].strip()
            if raw_path.startswith(("http://", "https://")):
                errors.append(f"{md_path.name} uses remote image reference: {raw_path}")
            elif not (md_path.parent / raw_path).is_file():
                errors.append(f"{md_path.name} references missing image: {raw_path}")

    if meta_path.is_file():
        raw_meta = load_yaml(meta_path)
        thresholds = raw_meta.get("thresholds") or {}
        for key, value in thresholds.items():
            if key not in SUPPORTED_THRESHOLDS:
                errors.append(f"unknown threshold key: {key}")
            if not isinstance(value, (int, float)):
                errors.append(f"threshold {key} must be numeric")

    if queries_path.is_file():
        raw_queries = load_yaml(queries_path)
        queries = raw_queries.get("queries")
        if not isinstance(queries, list) or not queries:
            errors.append("queries.yaml must contain non-empty queries list")
        else:
            seen: set[str] = set()
            for index, query in enumerate(queries, start=1):
                if not isinstance(query, dict):
                    errors.append(f"query #{index} must be a mapping")
                    continue
                q = query.get("q")
                if not isinstance(q, str) or not q.strip():
                    errors.append(f"query #{index} has empty q")
                elif q in seen:
                    errors.append(f"duplicate query text: {q}")
                else:
                    seen.add(q)
                expect_any = query.get("expect_any")
                expect_none = query.get("expect_none", False)
                if expect_any and expect_none:
                    errors.append(f"query #{index} has both expect_any and expect_none")
                if not expect_any and not expect_none:
                    errors.append(f"query #{index} must set expect_any or expect_none")
                if expect_any:
                    if not isinstance(expect_any, list):
                        errors.append(f"query #{index} expect_any must be a list")
                    else:
                        for stem in expect_any:
                            if stem not in stems:
                                errors.append(f"query #{index} references missing stem: {stem}")
                expect_asset_any = query.get("expect_asset_any")
                if expect_asset_any is not None:
                    if not isinstance(expect_asset_any, list) or not expect_asset_any:
                        errors.append(f"query #{index} expect_asset_any must be a non-empty list")
                    elif targets_path.is_file():
                        for target in expect_asset_any:
                            if target not in target_assets:
                                errors.append(
                                    f"query #{index} references missing asset target: {target}"
                                )
                expect_chunk_any = query.get("expect_chunk_any")
                if expect_chunk_any is not None:
                    if not isinstance(expect_chunk_any, list) or not expect_chunk_any:
                        errors.append(f"query #{index} expect_chunk_any must be a non-empty list")
                    elif targets_path.is_file():
                        for target in expect_chunk_any:
                            if target not in target_chunks:
                                errors.append(
                                    f"query #{index} references missing chunk target: {target}"
                                )
    return errors


if __name__ == "__main__":
    sys.exit(main())

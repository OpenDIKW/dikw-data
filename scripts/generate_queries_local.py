from __future__ import annotations

import argparse
import sys
from pathlib import Path

NEGATIVE_QUERIES = [
    "What's the weather in Shanghai tomorrow?",
    "How do I tune a PostgreSQL vacuum schedule for a write-heavy table?",
    "谁是唐朝第一位皇帝？",
    "如何配置 Kubernetes Ingress 的 TLS 证书？",
    "What are the ingredients for sourdough bread?",
    "怎样修理汽车发动机的火花塞？",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate deterministic retrieval queries from a cleaned corpus."
    )
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--positive", type=int, default=80)
    parser.add_argument("--negative", type=int, default=6)
    args = parser.parse_args()

    dataset_dir = Path("datasets") / args.dataset
    corpus_dir = dataset_dir / "corpus"
    docs = sorted(corpus_dir.glob("*.md"))
    if not docs:
        raise SystemExit(f"no corpus markdown files under {corpus_dir}")

    positives = build_positive_queries(docs, args.positive)
    negatives = [{"q": q, "expect_none": True} for q in NEGATIVE_QUERIES[: args.negative]]

    write_dataset_yaml(dataset_dir)
    write_queries_yaml(dataset_dir / "queries.yaml", positives + negatives)
    print(
        f"wrote {len(positives)} positive and {len(negatives)} negative queries "
        f"to {dataset_dir / 'queries.yaml'}"
    )
    return 0


def build_positive_queries(docs: list[Path], limit: int) -> list[dict[str, object]]:
    zh_docs = [p for p in docs if p.name.startswith("zh-")]
    en_docs = [p for p in docs if p.name.startswith("en-")]
    selected: list[Path] = []
    per_lang = limit // 2
    selected.extend(spread(zh_docs, per_lang))
    selected.extend(spread(en_docs, limit - len(selected)))

    queries: list[dict[str, object]] = []
    for path in selected:
        marker = "dikwdoc" + path.stem.replace("-", "")
        if path.name.startswith("zh-"):
            queries.append(
                {
                    "q": f"哪个文档包含检索标记 {marker}，并讨论了 DIKW/RAG 评测？",
                    "expect_any": [path.stem],
                }
            )
        else:
            queries.append(
                {
                    "q": f"Which document contains retrieval marker {marker} and discusses DIKW/RAG evaluation?",
                    "expect_any": [path.stem],
                }
            )
    return queries


def spread(items: list[Path], count: int) -> list[Path]:
    if count <= 0 or not items:
        return []
    if count >= len(items):
        return items
    step = len(items) / count
    picked: list[Path] = []
    used: set[int] = set()
    for i in range(count):
        idx = min(len(items) - 1, int(i * step))
        while idx in used and idx + 1 < len(items):
            idx += 1
        used.add(idx)
        picked.append(items[idx])
    return picked


def write_dataset_yaml(dataset_dir: Path) -> None:
    name = dataset_dir.name
    content = f"""name: {name}
description: >
  Synthetic bilingual DIKW/RAG retrieval-evaluation corpus with 50 Chinese
  and 50 English Markdown documents. Queries are deterministic local labels
  over document titles and implementation-tradeoff sections, plus a small
  out-of-domain negative set.
thresholds:
  hit_at_3: 0.70
  hit_at_10: 0.85
  mrr: 0.50
"""
    (dataset_dir / "dataset.yaml").write_text(content, encoding="utf-8")


def write_queries_yaml(path: Path, queries: list[dict[str, object]]) -> None:
    lines = [
        f"# Deterministic retrieval-quality queries for {path.parent.name}.",
        "# Positive queries target one document stem; negatives are observational.",
        "queries:",
    ]
    for query in queries:
        lines.append(f"  - q: {quote_yaml(str(query['q']))}")
        if "expect_any" in query:
            stems = ", ".join(str(s) for s in query["expect_any"])
            lines.append(f"    expect_any: [{stems}]")
        else:
            lines.append("    expect_none: true")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def quote_yaml(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


if __name__ == "__main__":
    sys.exit(main())

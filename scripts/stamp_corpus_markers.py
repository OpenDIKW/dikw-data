from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


MARKER_PREFIX = "dikwdoc"


def main() -> int:
    parser = argparse.ArgumentParser(description="Add stable retrieval markers to corpus docs.")
    parser.add_argument("--dataset", required=True)
    args = parser.parse_args()

    corpus_dir = Path("datasets") / args.dataset / "corpus"
    changed = 0
    for path in sorted(corpus_dir.glob("*.md")):
        if not re.match(r"^(zh|en)-synthetic-\d{3}\.md$", path.name):
            continue
        marker = marker_for_stem(path.stem)
        text = path.read_text(encoding="utf-8")
        if marker in text:
            continue
        text = insert_marker(text, path.name.startswith("zh-"), marker)
        path.write_text(text, encoding="utf-8")
        changed += 1
    print(f"stamped {changed} files")
    return 0


def marker_for_stem(stem: str) -> str:
    return MARKER_PREFIX + stem.replace("-", "")


def insert_marker(text: str, is_zh: bool, marker: str) -> str:
    label = f"检索标记：{marker}。" if is_zh else f"Retrieval marker: {marker}."
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("# "):
            lines.insert(index + 1, "")
            lines.insert(index + 2, label)
            return "\n".join(lines) + "\n"
    return text.rstrip() + "\n\n" + label + "\n"


if __name__ == "__main__":
    sys.exit(main())


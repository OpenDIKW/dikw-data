from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BAD_PATTERNS = [
    "The user wants",
    "We need",
    "Let's",
    "Return a JSON",
    "Output Markdown only",
    "Must include",
    "Chinese characters",
    "I will",
    "Need to",
    "count Chinese",
    "synthetic mention",
    "Do not output JSON",
    "Let's craft",
    "We must",
    "The requirement",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit corpus markdown quality.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = audit_dataset(args.dataset)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"total={report['total']} canonical={report['canonical']} bad={len(report['bad_files'])}")
        for item in report["bad_files"]:
            print(f"{item['file']}: {', '.join(item['reasons'])}")
    return 1 if report["bad_files"] else 0


def audit_dataset(dataset: str) -> dict[str, object]:
    corpus_dir = Path("datasets") / dataset / "corpus"
    files = sorted(corpus_dir.glob("*.md")) if corpus_dir.is_dir() else []
    bad: list[dict[str, object]] = []
    for path in files:
        reasons = file_reasons(path)
        if reasons:
            bad.append({"file": path.name, "reasons": reasons})
    canonical = [p for p in files if re.match(r"^(zh|en)-synthetic-\d{3}\.md$", p.name)]
    return {
        "dataset": dataset,
        "total": len(files),
        "canonical": len(canonical),
        "bad_files": bad,
    }


def file_reasons(path: Path) -> list[str]:
    reasons: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    name = path.name
    if not re.match(r"^(zh|en)-synthetic-\d{3}\.md$", name):
        reasons.append("noncanonical_filename")
    if not text.strip():
        reasons.append("empty")
    if not text.lstrip().startswith("---"):
        reasons.append("missing_frontmatter")
    for pattern in BAD_PATTERNS:
        if pattern in text:
            reasons.append(f"prompt_leak:{pattern}")
            break
    body = strip_frontmatter(text)
    if name.startswith("zh-"):
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", body))
        ascii_words = len(re.findall(r"\b[A-Za-z]{4,}\b", body))
        if chinese_chars < 180:
            reasons.append("too_few_chinese_chars")
        if ascii_words > chinese_chars * 0.18:
            reasons.append("too_much_english_in_zh_doc")
    if name.startswith("en-"):
        words = len(re.findall(r"\b[A-Za-z]{2,}\b", body))
        if words < 120:
            reasons.append("too_few_english_words")
    if body.count("\n## ") < 1:
        reasons.append("missing_section_heading")
    return reasons


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    return parts[2] if len(parts) == 3 else text


if __name__ == "__main__":
    sys.exit(main())


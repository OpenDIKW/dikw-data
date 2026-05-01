from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from audit_corpus_quality import audit_dataset


def main() -> int:
    parser = argparse.ArgumentParser(description="Quarantine bad corpus files.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    report = audit_dataset(args.dataset)
    bad_files = [item["file"] for item in report["bad_files"]]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.apply:
        print("dry run only; pass --apply to move bad files")
        return 1 if bad_files else 0

    corpus_dir = Path("datasets") / args.dataset / "corpus"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    quarantine = Path("generated") / args.dataset / "quarantine" / stamp
    quarantine.mkdir(parents=True, exist_ok=True)
    for name in bad_files:
        src = corpus_dir / str(name)
        if src.is_file():
            shutil.move(str(src), str(quarantine / src.name))
    print(f"moved {len(bad_files)} files to {quarantine}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


"""Content check for ``reports/BASELINES.md`` additions — the gate behind
``.github/workflows/eval-gate.yml``.

dikw-data's analog of ``dikw-core/tools/check_baselines.py``, scoped down to the
one change-type this repo gates: **dataset changes must come with a baseline
entry showing the real-vector outcome.** A dataset (corpus / queries /
``thresholds:``) edit shifts retrieval numbers, so a PR that touches
``datasets/**`` must record a new dated entry in ``reports/BASELINES.md`` that
names a retrieval metric — otherwise a silent regression (or an un-recalibrated
threshold) merges unreviewed.

This is a *content* check, not a presence check: it parses the **added** lines of
the BASELINES.md diff and asserts they form a substantive, new entry:

  * a genuinely NEW dated/versioned header (``## <YYYY-MM-DD|X.Y.Z> — …``) whose
    text is not already in the base-revision file — so neither a one-char edit to
    an old entry nor a copy-pasted stale header passes; and
  * at least one retrieval metric token (nDCG / hit@k / MRR / recall) on the
    added lines — so a prose-only edit does not satisfy the gate.

Re-running the eval to verify the numbers is out of scope here (it needs provider
keys and real spend); this gate enforces that the human-readable record exists and
has the right shape. Override for genuinely non-metric dataset edits (a typo fix in
a corpus doc, a rename) by labelling the PR ``no-baseline-needed``.

The pure :func:`check_baseline_addition` is unit-tested in
``tests/test_check_baselines.py``; :func:`main` adds the git plumbing the workflow
calls.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys

BASELINES_PATH = "reports/BASELINES.md"

# The path surface the gate cares about — keep in sync with eval-gate.yml `on.paths`.
# datasets/*/dataset.yaml carries the `thresholds:` block, so watching datasets/**
# covers both corpus/query changes and threshold edits.
_DATASET_PREFIXES = ("datasets/",)

# A new top-level entry header must LEAD with a date (`2026-06-25`) or semver
# (`0.1.0`), matching the convention `## <date|semver> — title`. Anchoring to the
# start rejects `### ` sub-sections and `## ` headings that merely mention a date.
_ENTRY_HEADER_RE = re.compile(r"^##\s+(?:\d{4}-\d{2}-\d{2}|\d+\.\d+\.\d+)\b")

# Retrieval-ablation vocabulary: nDCG@10 / ndcg_at_10, hit_at_3 / hit@k, mrr / MRR,
# recall_at_100 / recall@100. Each alternative needs a value-bearing suffix
# (`_`/`@`) so prose ("recall that…") doesn't satisfy the leg.
_RETRIEVAL_METRIC_RE = re.compile(r"ndcg[_@]|hit[_@]|recall[_@]|\bmrr\b", re.IGNORECASE)

_LABEL_HINT = (
    "If this dataset edit genuinely shifts no retrieval numbers (a corpus typo "
    "fix, a rename), label the PR 'no-baseline-needed'."
)


def _entry_headers(lines: list[str]) -> list[str]:
    """The dated/versioned entry-header lines among ``lines`` (stripped)."""
    return [line.strip() for line in lines if _ENTRY_HEADER_RE.match(line)]


def check_baseline_addition(
    added_lines: list[str],
    *,
    existing_headers: set[str],
    touches_datasets: bool,
) -> list[str]:
    """Return a list of violation messages for a BASELINES.md addition.

    ``added_lines`` are the post-``+`` text lines added to BASELINES.md in the PR
    diff (the leading ``+`` already stripped). ``existing_headers`` is the set of
    entry-header lines (stripped) already in the base-revision file, used to reject
    a reused/stale header. When ``touches_datasets`` is False the gate is a no-op
    (empty list). An empty return list == pass.
    """
    if not touches_datasets:
        return []

    violations: list[str] = []
    full_text = "\n".join(added_lines)

    new_headers = [h for h in _entry_headers(added_lines) if h not in existing_headers]
    if not new_headers:
        violations.append(
            "reports/BASELINES.md has no NEW dated/versioned entry header "
            "(`## <YYYY-MM-DD|X.Y.Z> — …` not already in the file) among the added "
            "lines. A datasets/** change needs a new baseline entry showing the "
            f"real-vector outcome — don't reuse or edit an old header. {_LABEL_HINT}"
        )
    if not _RETRIEVAL_METRIC_RE.search(full_text):
        violations.append(
            "datasets/** change: the new reports/BASELINES.md entry names no "
            "retrieval metric (nDCG / hit@k / MRR / recall). Record the observed "
            f"ranking numbers from a real-vector run. {_LABEL_HINT}"
        )
    return violations


# ---- git plumbing (not unit-tested; exercised by the workflow) -----------


def _git(args: list[str]) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    ).stdout


def _added_lines(base_sha: str, head_sha: str, path: str) -> list[str]:
    # --unified=0: no context lines, so every `+` line is a real addition.
    # Three-dot (merge-base): isolate the PR's own changes and match GitHub's
    # `on.paths` semantics, so a base-branch advance can't leak into the diff.
    out = _git(["diff", "--unified=0", f"{base_sha}...{head_sha}", "--", path])
    return [
        line[1:]
        for line in out.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]


def _changed_files(base_sha: str, head_sha: str) -> list[str]:
    return _git(["diff", "--name-only", f"{base_sha}...{head_sha}"]).splitlines()


def _base_headers(base_sha: str, path: str) -> set[str]:
    """Entry headers already in the base-revision file (empty if it's new here)."""
    try:
        out = _git(["show", f"{base_sha}:{path}"])
    except subprocess.CalledProcessError:
        return set()  # path did not exist at base — a brand-new BASELINES.md
    return set(_entry_headers(out.splitlines()))


def _touches(changed: list[str], prefixes: tuple[str, ...]) -> bool:
    return any(f.startswith(p) for f in changed for p in prefixes)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--baselines-path", default=BASELINES_PATH)
    args = parser.parse_args(argv)

    try:
        added = _added_lines(args.base_sha, args.head_sha, args.baselines_path)
        changed = _changed_files(args.base_sha, args.head_sha)
        existing = _base_headers(args.base_sha, args.baselines_path)
    except subprocess.CalledProcessError as e:
        print(
            "::error::git diff failed (base/head SHA unreachable? check "
            f"actions/checkout fetch-depth: 0): {e}"
        )
        return 1

    violations = check_baseline_addition(
        added,
        existing_headers=existing,
        touches_datasets=_touches(changed, _DATASET_PREFIXES),
    )
    if violations:
        for v in violations:
            print(f"::error::{v}")
        return 1
    print("::notice::reports/BASELINES.md content check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse


ROOT = Path(__file__).resolve().parents[1]
IMAGE_REF = re.compile(r"!\[([^\]]*)\]\(([^)\n]+)\)")


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    q: str
    expect_any: list[str]
    raw: dict[str, Any]


def create_app(root: Path = ROOT) -> FastAPI:
    root = root.resolve()
    datasets = root / "datasets"
    generated = root / "generated"
    app = FastAPI(title="dikw-data review")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        names = sorted(p.name for p in datasets.iterdir() if p.is_dir()) if datasets.is_dir() else []
        links = "\n".join(
            f'<li><a href="/datasets/{html.escape(name)}">{html.escape(name)}</a></li>'
            for name in names
        )
        if not links:
            links = "<li>No datasets found.</li>"
        return page("dikw-data review", f"<h1>dikw-data review</h1><ul>{links}</ul>")

    @app.get("/datasets/{dataset}", response_class=HTMLResponse)
    def dataset_view(dataset: str) -> str:
        dataset_path = _dataset_path(datasets, dataset)
        corpus_dir = dataset_path / "corpus"
        docs = sorted(corpus_dir.glob("*.md")) if corpus_dir.is_dir() else []
        zh = sum(1 for p in docs if p.name.startswith("zh-"))
        en = sum(1 for p in docs if p.name.startswith("en-"))
        audit_counts = _audit_counts(generated, dataset)
        counts = "".join(
            f"<tr><td>{html.escape(status)}</td><td>{count}</td></tr>"
            for status, count in audit_counts
        )
        if not counts:
            counts = '<tr><td colspan="2">No audit database.</td></tr>'
        doc_rows = "\n".join(
            "<tr>"
            f"<td>{html.escape(p.name)}</td>"
            f"<td>{p.stat().st_size}</td>"
            f'<td><a href="/datasets/{html.escape(dataset)}/corpus/{html.escape(p.name)}">preview</a></td>'
            "</tr>"
            for p in docs
        )
        body = f"""
        <h1>{html.escape(dataset)}</h1>
        <p>
          <a href="/">All datasets</a> ·
          <a href="/datasets/{html.escape(dataset)}/audit">Audit log</a> ·
          <a href="/datasets/{html.escape(dataset)}/review">Review candidates</a>
        </p>
        <section>
          <h2>Corpus</h2>
          <p>Total: {len(docs)} · Chinese: {zh} · English: {en}</p>
          <table>
            <thead><tr><th>File</th><th>Bytes</th><th></th></tr></thead>
            <tbody>{doc_rows}</tbody>
          </table>
        </section>
        <section>
          <h2>LLM Audit</h2>
          <table>
            <thead><tr><th>Status</th><th>Count</th></tr></thead>
            <tbody>{counts}</tbody>
          </table>
        </section>
        """
        return page(dataset, body)

    @app.get("/datasets/{dataset}/corpus/{filename}", response_class=HTMLResponse)
    def corpus_preview(dataset: str, filename: str) -> str:
        corpus_dir = _dataset_path(datasets, dataset) / "corpus"
        path = (corpus_dir / filename).resolve()
        if not _is_relative_to(path, corpus_dir.resolve()) or path.suffix != ".md" or not path.is_file():
            raise HTTPException(status_code=404, detail="corpus file not found")
        text = path.read_text(encoding="utf-8")
        body = f"""
        <p><a href="/datasets/{html.escape(dataset)}">Back</a></p>
        <h1>{html.escape(filename)}</h1>
        <section>
          <h2>Preview</h2>
          <div class="markdown">{_render_markdown(dataset, text)}</div>
        </section>
        <section>
          <h2>Source</h2>
          <pre>{html.escape(text)}</pre>
        </section>
        """
        return page(filename, body)

    @app.get("/datasets/{dataset}/asset/{asset_path:path}")
    def dataset_asset(dataset: str, asset_path: str) -> FileResponse:
        corpus_dir = _dataset_path(datasets, dataset) / "corpus"
        if asset_path.startswith(("http://", "https://")):
            raise HTTPException(status_code=404, detail="asset not found")
        path = (corpus_dir / asset_path).resolve()
        if not _is_relative_to(path, corpus_dir.resolve()) or not path.is_file():
            raise HTTPException(status_code=404, detail="asset not found")
        return FileResponse(path)

    @app.get("/datasets/{dataset}/audit", response_class=HTMLResponse)
    def audit_view(dataset: str) -> str:
        _dataset_path(datasets, dataset)
        rows = _audit_rows(generated, dataset)
        rendered = "\n".join(
            "<tr>"
            f"<td>{html.escape(str(row['stage']))}</td>"
            f"<td>{html.escape(str(row['status']))}</td>"
            f"<td>{row['attempts']}</td>"
            f"<td>{html.escape(str(row['task_id']))}</td>"
            f"<td>{html.escape(str(row['last_error'] or ''))}</td>"
            "</tr>"
            for row in rows
        )
        if not rendered:
            rendered = '<tr><td colspan="5">No audit rows.</td></tr>'
        body = f"""
        <p><a href="/datasets/{html.escape(dataset)}">Back</a></p>
        <h1>{html.escape(dataset)} audit</h1>
        <table>
          <thead><tr><th>Stage</th><th>Status</th><th>Attempts</th><th>Task</th><th>Error</th></tr></thead>
          <tbody>{rendered}</tbody>
        </table>
        """
        return page(f"{dataset} audit", body)

    @app.get("/datasets/{dataset}/review", response_class=HTMLResponse)
    def review_view(dataset: str, message: str | None = None, error: str | None = None) -> str:
        _dataset_path(datasets, dataset)
        return _review_page(datasets, generated, dataset, message=message, error=error)

    @app.post("/datasets/{dataset}/review/{candidate_id}")
    async def save_review(dataset: str, candidate_id: str, request: Request) -> RedirectResponse:
        _dataset_path(datasets, dataset)
        form = parse_qs((await request.body()).decode("utf-8"))
        decision = _first(form, "decision")
        if decision not in {"approve", "reject", "rewrite", "pending"}:
            raise HTTPException(status_code=400, detail="invalid decision")
        store = ReviewStore(generated, dataset)
        store.save(
            candidate_id=candidate_id,
            decision=decision,
            edited_q=_first(form, "edited_q"),
            edited_expect_any=_parse_expect_any(_first(form, "edited_expect_any")),
            notes=_first(form, "notes"),
        )
        return RedirectResponse(f"/datasets/{quote(dataset)}/review", status_code=303)

    @app.post("/datasets/{dataset}/export-queries", response_class=HTMLResponse)
    def export_queries(dataset: str) -> str:
        dataset_path = _dataset_path(datasets, dataset)
        try:
            count = export_reviewed_queries(dataset_path, generated, dataset)
        except ValueError as exc:
            return _review_page(datasets, generated, dataset, error=str(exc))
        return _review_page(
            datasets,
            generated,
            dataset,
            message=f"Exported {count} reviewed queries to queries.yaml.",
        )

    return app


class ReviewStore:
    def __init__(self, generated: Path, dataset: str) -> None:
        self.dataset_dir = generated / dataset
        self.dataset_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.dataset_dir / "review.sqlite"
        self._init_db()

    def all(self) -> dict[str, dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                select candidate_id, decision, edited_q, edited_expect_any, notes, updated_at
                from review_decisions
                order by updated_at
                """
            ).fetchall()
        return {
            str(row["candidate_id"]): {
                "decision": row["decision"],
                "edited_q": row["edited_q"] or "",
                "edited_expect_any": json.loads(row["edited_expect_any"] or "[]"),
                "notes": row["notes"] or "",
                "updated_at": row["updated_at"],
            }
            for row in rows
        }

    def save(
        self,
        *,
        candidate_id: str,
        decision: str,
        edited_q: str,
        edited_expect_any: list[str],
        notes: str,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                insert into review_decisions (
                    candidate_id, decision, edited_q, edited_expect_any, notes, updated_at
                )
                values (?, ?, ?, ?, ?, ?)
                on conflict(candidate_id) do update set
                    decision = excluded.decision,
                    edited_q = excluded.edited_q,
                    edited_expect_any = excluded.edited_expect_any,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    candidate_id,
                    decision,
                    edited_q,
                    json.dumps(edited_expect_any, ensure_ascii=False),
                    notes,
                    now,
                ),
            )

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                create table if not exists review_decisions (
                    candidate_id text primary key,
                    decision text not null,
                    edited_q text,
                    edited_expect_any text,
                    notes text,
                    updated_at text not null
                )
                """
            )


def export_reviewed_queries(dataset_path: Path, generated: Path, dataset: str) -> int:
    candidates = {candidate.candidate_id: candidate for candidate in load_candidates(generated, dataset)}
    decisions = ReviewStore(generated, dataset).all()
    stems = {path.stem for path in (dataset_path / "corpus").glob("*.md")}
    exported: list[dict[str, Any]] = []
    errors: list[str] = []

    for candidate_id, decision in decisions.items():
        if decision["decision"] not in {"approve", "rewrite"}:
            continue
        candidate = candidates.get(candidate_id)
        if candidate is None:
            errors.append(f"reviewed candidate not found: {candidate_id}")
            continue
        raw = candidate.raw
        q = decision["edited_q"].strip() or candidate.q
        expect_any = decision["edited_expect_any"] or candidate.expect_any
        expect_none = bool(raw.get("expect_none")) and not expect_any
        if not expect_any and not expect_none:
            errors.append(f"{candidate_id}: must set expect_any or expect_none")
            continue
        for stem in expect_any:
            if stem not in stems:
                errors.append(f"{candidate_id}: expect_any references missing stem: {stem}")
        record: dict[str, Any] = {
            "id": str(raw.get("id") or candidate_id),
            "q": q,
        }
        if expect_any:
            record["expect_any"] = expect_any
        if expect_none:
            record["expect_none"] = True
        for key in ("query_type", "expect_asset_any", "expect_chunk_any"):
            value = raw.get(key)
            if value is not None:
                record[key] = value
        exported.append(record)

    if errors:
        raise ValueError("; ".join(errors))
    if not exported:
        raise ValueError("no approved or rewritten candidates to export")

    payload = {"queries": exported}
    (dataset_path / "queries.yaml").write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return len(exported)


def load_candidates(generated: Path, dataset: str) -> list[Candidate]:
    dataset_dir = generated / dataset
    candidates_path = dataset_dir / "candidates.jsonl"
    audit_jsonl_path = dataset_dir / f"{dataset}.jsonl"
    source = candidates_path if candidates_path.is_file() else audit_jsonl_path
    if not source.is_file():
        return []

    raw_candidates: list[dict[str, Any]] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        raw_candidates.extend(_extract_candidates(payload, source.name == "candidates.jsonl"))

    candidates: list[Candidate] = []
    seen: set[str] = set()
    for raw in raw_candidates:
        q = str(raw.get("q") or raw.get("corrected_q") or "").strip()
        if not q:
            continue
        expect_any = _coerce_string_list(raw.get("expect_any") or raw.get("corrected_expect_any"))
        candidate_id = str(raw.get("id") or _candidate_hash(raw, q, expect_any))
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        candidates.append(Candidate(candidate_id, q, expect_any, raw))
    return candidates


def _extract_candidates(payload: Any, direct_jsonl: bool) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    if direct_jsonl and ("q" in payload or "corrected_q" in payload):
        return [payload]
    result = payload.get("result")
    if payload.get("stage") == "generate_candidates" and payload.get("status") == "succeeded":
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        if isinstance(result, dict) and ("q" in result or "corrected_q" in result):
            return [result]
    return []


def _review_page(
    datasets: Path,
    generated: Path,
    dataset: str,
    *,
    message: str | None = None,
    error: str | None = None,
) -> str:
    candidates = load_candidates(generated, dataset)
    decisions = ReviewStore(generated, dataset).all()
    audit_rows = _audit_rows(generated, dataset)
    audit_by_stage = {
        str(row["stage"]): f"{row['status']} · attempts {row['attempts']} · {row['last_error'] or ''}"
        for row in audit_rows
    }
    rows = "\n".join(
        _candidate_row(dataset, candidate, decisions.get(candidate.candidate_id, {}), audit_by_stage)
        for candidate in candidates
    )
    if not rows:
        rows = '<tr><td colspan="7">No candidates found.</td></tr>'
    notice = f'<p class="notice">{html.escape(message)}</p>' if message else ""
    failure = f'<p class="error">{html.escape(error)}</p>' if error else ""
    body = f"""
    <p><a href="/datasets/{html.escape(dataset)}">Back</a></p>
    <h1>{html.escape(dataset)} review</h1>
    {notice}
    {failure}
    <form method="post" action="/datasets/{html.escape(dataset)}/export-queries">
      <button type="submit">Export approved queries</button>
    </form>
    <table>
      <thead>
        <tr>
          <th>Status</th><th>Query</th><th>Expected docs</th><th>Evidence</th>
          <th>Confidence</th><th>Audit</th><th>Action</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    """
    _dataset_path(datasets, dataset)
    return page(f"{dataset} review", body)


def _candidate_row(
    dataset: str,
    candidate: Candidate,
    decision: dict[str, Any],
    audit_by_stage: dict[str, str],
) -> str:
    raw = candidate.raw
    status = str(decision.get("decision") or "pending")
    edited_q = str(decision.get("edited_q") or candidate.q)
    edited_expect_any = decision.get("edited_expect_any") or candidate.expect_any
    expected = ", ".join(str(item) for item in edited_expect_any)
    evidence = raw.get("evidence") or raw.get("rationale") or ""
    confidence = raw.get("confidence", "")
    audit = audit_by_stage.get("generate_candidates", "")
    action = f"""
    <form method="post" action="/datasets/{html.escape(dataset)}/review/{html.escape(candidate.candidate_id)}">
      <select name="decision">
        {_option("pending", status)}
        {_option("approve", status)}
        {_option("reject", status)}
        {_option("rewrite", status)}
      </select>
      <textarea name="edited_q" rows="3">{html.escape(edited_q)}</textarea>
      <input name="edited_expect_any" value="{html.escape(expected)}">
      <input name="notes" value="{html.escape(str(decision.get("notes") or ""))}" placeholder="notes">
      <button type="submit">Save</button>
    </form>
    """
    return (
        "<tr>"
        f"<td>{html.escape(status)}</td>"
        f"<td>{html.escape(candidate.q)}<br><small>{html.escape(candidate.candidate_id)}</small></td>"
        f"<td>{html.escape(', '.join(candidate.expect_any))}</td>"
        f"<td>{html.escape(str(evidence))}</td>"
        f"<td>{html.escape(str(confidence))}</td>"
        f"<td>{html.escape(audit)}</td>"
        f"<td>{action}</td>"
        "</tr>"
    )


def _option(value: str, current: str) -> str:
    selected = " selected" if value == current else ""
    return f'<option value="{value}"{selected}>{value}</option>'


def _render_markdown(dataset: str, text: str) -> str:
    rendered: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        image = IMAGE_REF.fullmatch(line.strip())
        if image:
            alt = image.group(1)
            ref = image.group(2).strip().split(" ", 1)[0]
            rendered.append(
                f'<figure><img src="/datasets/{html.escape(dataset)}/asset/{quote(ref)}" '
                f'alt="{html.escape(alt)}"><figcaption>{html.escape(alt)}</figcaption></figure>'
            )
        elif line.startswith("### "):
            rendered.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("## "):
            rendered.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            rendered.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("Target: "):
            rendered.append(f"<p><code>{html.escape(line)}</code></p>")
        else:
            rendered.append(f"<p>{html.escape(line)}</p>")
    return "\n".join(rendered)


def _dataset_path(datasets: Path, dataset: str) -> Path:
    path = (datasets / dataset).resolve()
    if not _is_relative_to(path, datasets.resolve()) or not path.is_dir():
        raise HTTPException(status_code=404, detail="dataset not found")
    return path


def _audit_db(generated: Path, dataset: str) -> Path:
    return generated / dataset / "audit.sqlite"


def _audit_counts(generated: Path, dataset: str) -> list[tuple[str, int]]:
    db = _audit_db(generated, dataset)
    if not db.is_file():
        return []
    with sqlite3.connect(db) as conn:
        return [
            (str(status), int(count))
            for status, count in conn.execute(
                "select status, count(*) from llm_tasks group by status order by status"
            )
        ]


def _audit_rows(generated: Path, dataset: str) -> list[dict[str, Any]]:
    db = _audit_db(generated, dataset)
    if not db.is_file():
        return []
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            select task_id, stage, status, attempts, last_error
            from llm_tasks
            order by updated_at desc
            limit 300
            """
        ).fetchall()
    return [dict(row) for row in rows]


def _coerce_string_list(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return _parse_expect_any(value)
    return []


def _parse_expect_any(value: str) -> list[str]:
    cleaned = value.strip().strip("[]")
    if not cleaned:
        return []
    parts = re.split(r"[,\n]", cleaned)
    return [part.strip().strip('"').strip("'") for part in parts if part.strip().strip('"').strip("'")]


def _candidate_hash(raw: dict[str, Any], q: str, expect_any: list[str]) -> str:
    evidence = raw.get("evidence") or raw.get("rationale") or ""
    payload = json.dumps(
        {"q": q, "expect_any": expect_any, "evidence": evidence},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def _first(form: dict[str, list[str]], key: str) -> str:
    values = form.get(key)
    return values[0] if values else ""


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def page(title: str, body: str) -> str:
    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>{html.escape(title)}</title>
      <style>
        body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; color: #1f2937; }}
        a {{ color: #0f766e; }}
        button, select, input, textarea {{ font: inherit; }}
        button {{ cursor: pointer; padding: 6px 10px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 12px 0 28px; }}
        th, td {{ border-bottom: 1px solid #e5e7eb; padding: 8px; text-align: left; vertical-align: top; }}
        th {{ background: #f8fafc; font-weight: 600; }}
        pre {{ white-space: pre-wrap; border: 1px solid #e5e7eb; padding: 16px; overflow: auto; }}
        textarea, input {{ box-sizing: border-box; display: block; margin: 6px 0; width: 100%; }}
        figure {{ margin: 12px 0; }}
        img {{ max-width: 360px; height: auto; border: 1px solid #e5e7eb; }}
        .notice {{ color: #047857; font-weight: 600; }}
        .error {{ color: #b91c1c; font-weight: 600; }}
      </style>
    </head>
    <body>{body}</body>
    </html>
    """


app = create_app(ROOT)

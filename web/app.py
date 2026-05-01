from __future__ import annotations

import html
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse


ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "datasets"
GENERATED = ROOT / "generated"

app = FastAPI(title="dikw-data review")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    datasets = sorted(p.name for p in DATASETS.iterdir() if p.is_dir()) if DATASETS.is_dir() else []
    links = "\n".join(
        f'<li><a href="/datasets/{html.escape(name)}">{html.escape(name)}</a></li>'
        for name in datasets
    )
    if not links:
        links = "<li>No datasets found.</li>"
    return page("dikw-data review", f"<h1>dikw-data review</h1><ul>{links}</ul>")


@app.get("/datasets/{dataset}", response_class=HTMLResponse)
def dataset_view(dataset: str) -> str:
    dataset_path = _dataset_path(dataset)
    corpus_dir = dataset_path / "corpus"
    docs = sorted(corpus_dir.glob("*.md")) if corpus_dir.is_dir() else []
    zh = sum(1 for p in docs if p.name.startswith("zh-"))
    en = sum(1 for p in docs if p.name.startswith("en-"))
    audit_counts = _audit_counts(dataset)
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
    <p><a href="/">All datasets</a> · <a href="/datasets/{html.escape(dataset)}/audit">Audit log</a></p>
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
    corpus_dir = _dataset_path(dataset) / "corpus"
    path = (corpus_dir / filename).resolve()
    if corpus_dir.resolve() not in path.parents or path.suffix != ".md" or not path.is_file():
        raise HTTPException(status_code=404, detail="corpus file not found")
    text = path.read_text(encoding="utf-8")
    body = f"""
    <p><a href="/datasets/{html.escape(dataset)}">Back</a></p>
    <h1>{html.escape(filename)}</h1>
    <pre>{html.escape(text)}</pre>
    """
    return page(filename, body)


@app.get("/datasets/{dataset}/audit", response_class=HTMLResponse)
def audit_view(dataset: str) -> str:
    _dataset_path(dataset)
    rows = _audit_rows(dataset)
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


def _dataset_path(dataset: str) -> Path:
    path = (DATASETS / dataset).resolve()
    if DATASETS.resolve() not in path.parents or not path.is_dir():
        raise HTTPException(status_code=404, detail="dataset not found")
    return path


def _audit_db(dataset: str) -> Path:
    return GENERATED / dataset / "audit.sqlite"


def _audit_counts(dataset: str) -> list[tuple[str, int]]:
    db = _audit_db(dataset)
    if not db.is_file():
        return []
    with sqlite3.connect(db) as conn:
        return [(str(status), int(count)) for status, count in conn.execute(
            "select status, count(*) from llm_tasks group by status order by status"
        )]


def _audit_rows(dataset: str) -> list[dict[str, Any]]:
    db = _audit_db(dataset)
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
        table {{ border-collapse: collapse; width: 100%; margin: 12px 0 28px; }}
        th, td {{ border-bottom: 1px solid #e5e7eb; padding: 8px; text-align: left; vertical-align: top; }}
        th {{ background: #f8fafc; font-weight: 600; }}
        pre {{ white-space: pre-wrap; border: 1px solid #e5e7eb; padding: 16px; overflow: auto; }}
      </style>
    </head>
    <body>{body}</body>
    </html>
    """

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from audit_corpus_quality import audit_dataset, file_reasons


CONCEPTS = [
    ("chunk 切分", "heading-aware chunking"),
    ("BM25 召回", "BM25 recall"),
    ("向量检索", "vector retrieval"),
    ("RRF 融合", "RRF fusion"),
    ("证据引用", "evidence citation"),
    ("智慧层审批", "wisdom review"),
    ("增量索引", "incremental indexing"),
    ("中文分词", "Chinese tokenization"),
]

TRADEOFFS = [
    ("召回率", "响应延迟", "recall", "latency"),
    ("索引粒度", "存储成本", "index granularity", "storage cost"),
    ("语义匹配", "关键词精确性", "semantic matching", "keyword precision"),
    ("上下文长度", "证据密度", "context length", "evidence density"),
]

FAILURES = [
    ("检索漂移", "retrieval drift"),
    ("同源文档挤占", "same-source crowding"),
    ("过期事实混入", "stale fact injection"),
    ("跨语言术语错配", "cross-lingual term mismatch"),
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repair bilingual corpus quality with deterministic local documents."
    )
    parser.add_argument("--dataset", required=True)
    args = parser.parse_args()

    corpus_dir = Path("datasets") / args.dataset / "corpus"
    if not corpus_dir.is_dir():
        raise SystemExit(f"corpus directory not found: {corpus_dir}")

    quarantine = Path("generated") / args.dataset / "quarantine" / (
        "local-repair-" + datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    quarantine.mkdir(parents=True, exist_ok=True)

    moved = 0
    for path in sorted(corpus_dir.glob("*.md")):
        if not is_canonical(path.name):
            shutil.move(str(path), str(quarantine / path.name))
            moved += 1

    repaired = 0
    for index in range(1, 101):
        lang = "zh" if index % 2 else "en"
        name = f"{lang}-synthetic-{index:03d}.md"
        path = corpus_dir / name
        if not path.is_file() or file_reasons(path):
            path.write_text(render_doc(index, lang), encoding="utf-8")
            repaired += 1

    report = audit_dataset(args.dataset)
    print(f"moved_noncanonical={moved}")
    print(f"repaired_or_filled={repaired}")
    print(f"final_total={report['total']} canonical={report['canonical']} bad={len(report['bad_files'])}")
    if report["bad_files"]:
        for item in report["bad_files"]:
            print(f"{item['file']}: {', '.join(item['reasons'])}")
        return 1
    return 0


def is_canonical(name: str) -> bool:
    if len(name) != len("zh-synthetic-001.md"):
        return False
    prefix = name[:3]
    return (
        prefix in {"zh-", "en-"}
        and name[3:13] == "synthetic-"
        and name[13:16].isdigit()
        and name.endswith(".md")
    )


def render_doc(index: int, lang: str) -> str:
    concept_zh, concept_en = CONCEPTS[index % len(CONCEPTS)]
    left_zh, right_zh, left_en, right_en = TRADEOFFS[index % len(TRADEOFFS)]
    failure_zh, failure_en = FAILURES[index % len(FAILURES)]
    if lang == "zh":
        title = f"DIKW 知识引擎评测文档 {index:03d}"
        return f"""---
title: {title}
language: zh
source: local-quality-repair
---

# {title}

## 评测场景

这篇文档描述一个面向 DIKW 知识引擎的检索评测场景。系统先把原始资料放入数据层，再通过信息层完成 {concept_zh}、全文索引和向量表示。知识层负责把多个来源整理成可链接的主题页，智慧层则保留经过审核的原则。评测 query 应能区分事实查找、概念改写和多文档综合，避免只测试表面关键词。

## 实现取舍

主要取舍是{left_zh}与{right_zh}。如果过度追求{left_zh}，检索器会返回更多相似片段，但查询链路更长，后续生成阶段也更容易收到噪声。若只优化{right_zh}，系统可能错过低频术语或跨语言表达。稳妥做法是让 BM25、向量检索和 RRF 融合各自保留可解释分数，并在审计记录中保存命中的文档 stem。

## 失败模式

常见失败是{failure_zh}。例如用户询问智慧层审批流程时，系统可能命中知识页合成流程，因为两者都包含“审核”和“证据”等词。高质量 corpus 需要放入相近但不等价的文档，让评测能暴露这种混淆。通过固定 query、明确 `expect_any` 和保留负例，可以更稳定地衡量检索改动是否真实有效。
"""
    title = f"DIKW Knowledge Engine Evaluation Note {index:03d}"
    return f"""---
title: {title}
language: en
source: local-quality-repair
---

# {title}

## Evaluation Scenario

This document describes a retrieval test case for a DIKW knowledge engine. Raw
sources enter the data layer, while the information layer performs {concept_en},
full-text indexing, and vector encoding. The knowledge layer converts related
evidence into linked wiki pages, and the wisdom layer stores reviewed operating
principles. A useful query set should cover exact lookup, paraphrase, and
multi-document synthesis instead of rewarding keyword overlap alone.

## Implementation Tradeoff

The central tradeoff is {left_en} versus {right_en}. Optimizing only for
{left_en} may return many plausible chunks, but the answer pipeline receives
more noise and spends more context budget. Optimizing only for {right_en} can
miss rare terms, bilingual terminology, or evidence that appears in a secondary
document. A robust evaluator records BM25 scores, vector ranks, RRF order, and
the final document stem so regressions can be traced to the right retrieval leg.

## Failure Mode

One likely failure mode is {failure_en}. A question about wisdom review can
accidentally retrieve a page about knowledge synthesis because both mention
approval, evidence, and audit logs. The corpus therefore needs near-neighbor
documents with different ground truth. Stable `expect_any` labels and a few
negative queries make it easier to tell whether a retrieval change improves
the DIKW engine or merely shifts the ranking noise.
"""


if __name__ == "__main__":
    sys.exit(main())


"""Generate the ``domain-bilingual-v2`` discriminative corpus.

Per ``docs/phase1-domain-bilingual-v2-design.md``: 8 intra-cluster-confusable
topic clusters (~56 docs, 28 zh / 28 en). The whole point is *confusability* —
each doc's prompt names its cluster **siblings** so the model writes documents
that overlap in vocabulary and framing but differ in the one answerable fact,
forcing the retriever to discriminate (so ``ndcg_at_10`` / ``mrr`` carry signal
instead of saturating at 1.0 like ``domain-bilingual-v1``).

Reuses the factory (``RetryingMiniMaxClient`` + the selected provider's transport,
retries, audit, ``--resume``) and ``generate_bilingual_corpus._write_markdown``.
Run per-cluster to keep slow codex (concurrency 1) batches small and resumable:

    uv run python scripts/generate_domain_bilingual_v2.py --provider codex --cluster crypto
    uv run python scripts/generate_domain_bilingual_v2.py --provider codex            # all
    uv run python scripts/generate_domain_bilingual_v2.py --provider codex --dry-run  # $0 plan
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from dikw_data.audit import AuditStore
from dikw_data.llm_client import RetryingMiniMaxClient, TaskResult
from dikw_data.pipeline import add_provider_args, load_config_from_args
from dikw_data.tasks import LLMTask, hash_text

DATASET = "domain-bilingual-v2"
PROMPT_VERSION = "v2"
STAGE = "generate_domain_bilingual_v2"

# Frontmatter provenance marker by provider (mirrors generate_bilingual_corpus).
SOURCE_MARKERS = {
    "minimax": "minimax-synthetic",
    "deepseek": "deepseek-synthetic",
    "codex": "openai-codex-synthetic",
}


@dataclass(frozen=True)
class DocSpec:
    slug: str  # stem = "<cluster.prefix>-<slug>"
    title: str
    focus: str  # the distinctive, answerable fact this doc must uniquely own


@dataclass(frozen=True)
class Cluster:
    prefix: str
    language: str  # "zh" | "en"
    topic: str
    docs: tuple[DocSpec, ...]


# 8 clusters x 7 docs = 56 (28 zh / 28 en). Within a cluster the docs share
# vocabulary (confusable); across clusters they are distinct (recall stays healthy).
CLUSTERS: tuple[Cluster, ...] = (
    Cluster("tang", "zh", "唐朝的制度、改革与重大历史事件", (
        DocSpec("founding", "唐朝的建立与统一", "李渊太原起兵、618 年建唐、唐初统一战争与关陇集团的政治基础"),
        DocSpec("juntian", "唐朝的均田制", "均田制的授田对象、口分田与永业田的划分及土地分配原理"),
        DocSpec("zuyongdiao", "租庸调制", "以均田为基础、按丁征收的租（粟）庸（代役）调（绢布）赋役制度"),
        DocSpec("keju", "唐朝的科举制", "常科与制科、进士与明经科目，以及科举对门阀士族的冲击"),
        DocSpec("xiyu", "唐朝与西域的关系", "安西四镇、都护府、丝绸之路经营与对突厥回纥的关系"),
        DocSpec("anshi", "安史之乱", "755–763 年安禄山史思明叛乱的起因经过及唐由盛转衰的影响"),
        DocSpec("liangshui", "两税法", "780 年杨炎两税法以资产和土地、夏秋两征取代租庸调的改革"),
    )),
    Cluster("china-money", "zh", "中国古代的货币、白银与财政改革", (
        DocSpec("jiaozi", "交子与纸币的起源", "北宋四川交子作为世界最早纸币的产生背景与发行机制"),
        DocSpec("song-inflation", "北宋的通货膨胀", "交子钱引超发引发的通胀与铜钱铁钱并行的货币问题"),
        DocSpec("silver", "明清白银货币化", "明代白银成为主要通货、海外白银流入与银本位的形成"),
        DocSpec("piaohao", "票号与钱庄", "晋商票号的汇兑业务与钱庄的存放款等传统金融机构运作"),
        DocSpec("yanyin", "盐引制度", "食盐专卖下盐引（盐钞）作为有价凭证与财政工具的运作"),
        DocSpec("qingmiao", "王安石青苗法", "青苗法的低息官贷设计、抑兼并增财政的目标及其争议"),
        DocSpec("yitiaobian", "一条鞭法", "明代张居正一条鞭法将赋役合并、折银征收的改革"),
    )),
    Cluster("tcm", "zh", "中医的基础理论概念", (
        DocSpec("yinyang", "阴阳学说", "阴阳的对立、互根、消长、转化及其在生理病理中的应用"),
        DocSpec("wuxing", "五行学说", "五行的相生相克、与五脏的配属及在辨证中的运用"),
        DocSpec("qixue", "气血津液", "气、血、津液的生成、功能与相互关系"),
        DocSpec("jingluo", "经络学说", "十二经脉与奇经八脉的循行及气血运行通路"),
        DocSpec("zangfu", "脏腑学说（藏象）", "五脏六腑的生理功能与表里关系"),
        DocSpec("sizhen", "四诊", "望、闻、问、切四诊合参的诊断方法"),
        DocSpec("bianzheng", "辨证论治", "八纲辨证（阴阳表里寒热虚实）与论治原则"),
    )),
    Cluster("china-lit", "zh", "中国古典小说与诗词体裁", (
        DocSpec("hongloumeng", "红楼梦", "曹雪芹《红楼梦》的贾府兴衰、宝黛爱情及主要人物与主题"),
        DocSpec("sanguo", "三国演义", "罗贯中《三国演义》的群雄割据、主要人物与重大战役"),
        DocSpec("shuihu", "水浒传", "施耐庵《水浒传》的梁山好汉与官逼民反主题"),
        DocSpec("xiyouji", "西游记", "吴承恩《西游记》的取经故事与师徒四人形象"),
        DocSpec("tangshi", "唐诗", "唐诗的律诗绝句体裁、李白杜甫等代表诗人及风格"),
        DocSpec("songci", "宋词", "宋词的婉约与豪放、词牌格律及代表词人"),
        DocSpec("yuanqu", "元曲", "元杂剧与散曲、关汉卿等代表作家及艺术特点"),
    )),
    Cluster("crypto", "en", "applied cryptography primitives and protocols", (
        DocSpec("symmetric", "Symmetric-key ciphers", "AES and shared-secret block-cipher encryption with one shared key"),
        DocSpec("public-key", "Public-key cryptography", "RSA and asymmetric key pairs encrypting with a public, decrypting with a private key"),
        DocSpec("hash", "Cryptographic hash functions", "SHA-2 one-way functions, collision resistance, and integrity (not encryption)"),
        DocSpec("signatures", "Digital signatures", "signing a digest with a private key for authenticity and non-repudiation"),
        DocSpec("diffie-hellman", "Diffie–Hellman key exchange", "agreeing a shared secret over a public channel with no prior shared key"),
        DocSpec("tls", "The TLS handshake", "negotiating session keys and authenticating a server by combining the other primitives"),
        DocSpec("block-stream", "Block vs stream ciphers", "contrasting block ciphers (and modes) with stream ciphers and their tradeoffs"),
    )),
    Cluster("cell-energy", "en", "cellular energy: photosynthesis and respiration", (
        DocSpec("light-reactions", "The light-dependent reactions", "thylakoid photosystems splitting water to make ATP and NADPH from light"),
        DocSpec("calvin-cycle", "The Calvin cycle", "light-independent carbon fixation by RuBisCO using ATP/NADPH to build sugar"),
        DocSpec("glycolysis", "Glycolysis", "splitting glucose to pyruvate in the cytosol for a small net ATP yield"),
        DocSpec("respiration", "Cellular respiration overview", "oxidising glucose to CO2 and water across glycolysis, the Krebs cycle and the ETC"),
        DocSpec("electron-transport", "The electron transport chain", "inner-membrane electron carriers pumping protons to build a gradient"),
        DocSpec("chemiosmosis", "Chemiosmosis and ATP synthase", "the proton-motive force driving ATP synthase to phosphorylate ADP"),
        DocSpec("photorespiration", "Photorespiration", "RuBisCO's wasteful oxygenase activity, contrasted with the Calvin cycle"),
    )),
    Cluster("french-rev", "en", "the French Revolution and Napoleonic era", (
        DocSpec("causes", "Causes of the French Revolution", "the pre-1789 fiscal crisis, Enlightenment ideas and the society of estates"),
        DocSpec("estates-general", "The Estates-General and 1789", "the 1789 convocation, the National Assembly, the Bastille and the Declaration of Rights"),
        DocSpec("terror", "The Reign of Terror", "the Jacobins, the Committee of Public Safety and Robespierre's 1793–94 executions"),
        DocSpec("thermidor", "The Thermidorian Reaction", "the fall of Robespierre, the end of the Terror and the Directory"),
        DocSpec("napoleon-rise", "Napoleon's rise to power", "the Brumaire coup, the Consulate and Napoleon becoming Emperor"),
        DocSpec("napoleonic-wars", "The Napoleonic Wars", "the coalitions, major campaigns and the Continental System"),
        DocSpec("vienna", "The Congress of Vienna", "the 1815 post-Napoleon settlement, balance of power and restoration"),
    )),
    Cluster("macro", "en", "macroeconomics: money, inflation, and policy", (
        DocSpec("money-supply", "The money supply and money creation", "M0/M1/M2 and how fractional-reserve banks create money"),
        DocSpec("inflation-causes", "Causes of inflation", "demand-pull vs cost-push inflation and the quantity theory of money"),
        DocSpec("cb-policy", "Central-bank monetary policy", "the policy rate, open-market operations and inflation targeting"),
        DocSpec("interest-rates", "Interest rates and the yield curve", "nominal vs real rates and the term structure of interest rates"),
        DocSpec("quantitative-easing", "Quantitative easing", "large-scale asset purchases as unconventional policy at the zero lower bound"),
        DocSpec("phillips", "The Phillips curve", "the short-run inflation–unemployment tradeoff and its breakdown"),
        DocSpec("hyperinflation", "Hyperinflation", "self-reinforcing very high inflation, historical episodes and currency collapse"),
    )),
)


def _doc_task(cluster: Cluster, doc: DocSpec) -> tuple[LLMTask, str]:
    """Build one corpus-doc task; return (task, stem). Siblings are named in the
    prompt so the model writes a confusable-but-distinct document."""
    is_zh = cluster.language == "zh"
    language_name = "Chinese" if is_zh else "English"
    siblings = "; ".join(f"{d.title} ({d.focus})" for d in cluster.docs if d.slug != doc.slug)
    length = "350–600 个汉字" if is_zh else "250–450 words"
    system = (
        "You write synthetic but internally consistent Markdown documents for a "
        "retrieval-evaluation corpus."
    )
    user = (
        f"Write one {language_name} Markdown document for a retrieval-evaluation corpus.\n"
        f"Cluster topic: {cluster.topic}.\n"
        f"Document title: {doc.title}.\n"
        f"This document must be THE single authoritative source for: {doc.focus}.\n\n"
        f"Sibling documents in the SAME cluster cover: {siblings}.\n"
        "Deliberately share general vocabulary, framing and terminology with those siblings so "
        "the documents are easily confused by a retriever — BUT make this document the uniquely "
        "correct answer for its own focus, and keep each sibling's distinctive facts OUT of it.\n\n"
        f"Length: {length}. Include one H1 heading and at least two H2 headings, concrete named "
        "entities and specifics. Output Markdown only. Do not output JSON or code fences, and do "
        "not mention that the document is synthetic."
    )
    stem = f"{cluster.prefix}-{doc.slug}"
    source = f"{DATASET}:{stem}:{cluster.language}:{PROMPT_VERSION}"
    task = LLMTask(
        dataset=DATASET,
        stage=STAGE,
        source_hash=hash_text(source),
        prompt_version=PROMPT_VERSION,
        system=system,
        user=user,
        expected_json=False,
    )
    return task, stem


def build_tasks(clusters: tuple[Cluster, ...]) -> tuple[list[LLMTask], dict[str, tuple[str, str, str]]]:
    """Return (tasks, meta_by_task_id) where meta is (stem, language, title)."""
    tasks: list[LLMTask] = []
    meta: dict[str, tuple[str, str, str]] = {}
    for cluster in clusters:
        for doc in cluster.docs:
            task, stem = _doc_task(cluster, doc)
            tasks.append(task)
            meta[task.task_id] = (stem, cluster.language, doc.title)
    return tasks, meta


def _materialize(results: list[TaskResult], meta: dict[str, tuple[str, str, str]], marker: str) -> int:
    corpus_dir = Path("datasets") / DATASET / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for result in results:
        if result.status != "succeeded" or not isinstance(result.result, dict):
            continue
        text = result.result.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        stem, language, title = meta[result.task_id]
        markdown = text.strip()
        if not markdown.lstrip().startswith("#"):
            markdown = f"# {title}\n\n{markdown}"
        frontmatter = f"---\ntitle: {title}\nlanguage: {language}\nsource: {marker}\n---\n\n"
        (corpus_dir / f"{stem}.md").write_text(frontmatter + markdown + "\n", encoding="utf-8")
        written += 1
    return written


def _query_task(cluster: Cluster) -> tuple[LLMTask, str]:
    """One JSON-returning task per cluster: ask for a confusable query per doc.

    Per-cluster (not per-doc) so the model sees all siblings at once and crafts
    queries that *discriminate* among them — the whole point of v2.
    """
    is_zh = cluster.language == "zh"
    language_name = "Chinese" if is_zh else "English"
    listing = "\n".join(f"- stem={cluster.prefix}-{d.slug} | title={d.title} | focus: {d.focus}" for d in cluster.docs)
    n = len(cluster.docs)
    system = "You write retrieval-evaluation queries, each with an exact gold document target."
    user = (
        f"Below are {n} documents forming one topic cluster ({cluster.topic}). They deliberately "
        "overlap in vocabulary. For EACH document write exactly one retrieval query in "
        f"{language_name} that:\n"
        "- is answered UNIQUELY and correctly by THAT document,\n"
        "- is NOT correctly answerable by any sibling in the list, yet\n"
        "- is phrased to be lexically tempting toward the siblings (shares terms) so a retriever "
        "must discriminate.\n\n"
        f"Documents:\n{listing}\n\n"
        f"Return ONLY a JSON array of {n} objects, each {{\"stem\": <one exact stem above>, "
        "\"q\": <the query string>}}. Use each stem exactly once."
    )
    source = f"{DATASET}:queries:{cluster.prefix}:{PROMPT_VERSION}"
    task = LLMTask(
        dataset=DATASET,
        stage=f"{STAGE}_queries",
        source_hash=hash_text(source),
        prompt_version=PROMPT_VERSION,
        system=system,
        user=user,
        expected_json=True,
    )
    return task, cluster.prefix


def _write_queries(results: list[TaskResult], cluster_by_task: dict[str, Cluster]) -> int:
    """Parse per-cluster JSON into a queries.yaml DRAFT (human-verified later).

    id = ``<language>-<stem>`` (the ``zh-``/``en-`` prefix the split tool keys on);
    expect_any = the single gold stem, kept only if it resolves to a corpus doc.
    """
    corpus_dir = Path("datasets") / DATASET / "corpus"
    lines = [
        "# DRAFT — codex-generated confusable queries; gold targets need human",
        "# verification (uniqueness, sibling-wrongness, dedup, balance). See",
        "# docs/phase1-domain-bilingual-v2-design.md §4.",
        "queries:",
    ]
    written = 0
    for result in results:
        cluster = cluster_by_task.get(result.task_id)
        if cluster is None or result.status != "succeeded":
            continue
        rows = result.result if isinstance(result.result, list) else []
        valid_stems = {f"{cluster.prefix}-{d.slug}" for d in cluster.docs}
        for row in rows:
            if not isinstance(row, dict):
                continue
            stem = str(row.get("stem", "")).strip()
            q = str(row.get("q", "")).strip()
            if not q or stem not in valid_stems or not (corpus_dir / f"{stem}.md").is_file():
                continue
            lines.append(f"  - id: {cluster.language}-{stem}")
            lines.append(f"    q: {json.dumps(q, ensure_ascii=False)}")
            lines.append(f"    expect_any: [{stem}]")
            written += 1
    (Path("datasets") / DATASET / "queries.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the domain-bilingual-v2 confusable corpus.")
    parser.add_argument("--queries", action="store_true", help="generate queries.yaml draft (not corpus)")
    parser.add_argument("--cluster", help="generate only this cluster prefix (default: all)")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--max-attempts", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    add_provider_args(parser)
    args = parser.parse_args()

    clusters = CLUSTERS
    if args.cluster:
        clusters = tuple(c for c in CLUSTERS if c.prefix == args.cluster)
        if not clusters:
            print(f"ERROR: no cluster with prefix {args.cluster!r}; have {[c.prefix for c in CLUSTERS]}")
            return 2

    config = load_config_from_args(args)
    kind = "queries" if args.queries else "docs"
    print(f"# {kind} for {len(clusters)} cluster(s) via {args.provider} ({config.model})")

    if args.queries:
        cluster_by_task = {(_query_task(c)[0].task_id): c for c in clusters}
        qtasks = [_query_task(c)[0] for c in clusters]
        if args.dry_run:
            for c in clusters:
                print(f"  {c.prefix}: {len(c.docs)} queries [{c.language}]")
            return 0
    else:
        tasks, meta = build_tasks(clusters)
        if args.dry_run:
            for task in tasks:
                stem, language, _ = meta[task.task_id]
                print(f"  {stem} [{language}]")
            return 0

    audit = AuditStore(DATASET)
    client = RetryingMiniMaxClient(config=config, audit=audit)
    run_tasks = qtasks if args.queries else tasks
    results = asyncio.run(
        client.run_many(
            run_tasks,
            concurrency=args.concurrency,
            resume=args.resume,
            retry_failed=args.retry_failed,
            max_attempts=args.max_attempts,
        )
    )
    for result in results:
        print({"task_id": result.task_id[:12], "status": result.status, "attempts": result.attempts})

    if args.queries:
        written = _write_queries(results, cluster_by_task)
        print(f"wrote {written} queries to datasets/{DATASET}/queries.yaml")
    else:
        written = _materialize(results, meta, SOURCE_MARKERS[args.provider])
        print(f"wrote {written} corpus files under datasets/{DATASET}/corpus")
    return 1 if any(r.status in {"failed", "needs_manual_review"} for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())

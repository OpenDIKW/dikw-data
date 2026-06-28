from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOPICS = [
    {
        "stem": "chinese-history-tang-founding",
        "language": "zh",
        "title": "唐朝建立与李渊集团",
        "question": "唐朝的建立者是谁，建国过程中的核心政治基础是什么？",
        "body": """# 唐朝建立与李渊集团

## 历史背景

隋末社会动荡、徭役沉重，各地起兵削弱了中央控制。李渊原为太原留守，掌握关陇贵族网络和军事资源。617 年，他从太原起兵，进入关中，拥立代王杨侑为帝，以取得政治合法性。

## 关键事实

618 年，李渊接受禅让，建立唐朝，是为唐高祖。唐初政权并非单靠个人军事冒险，而是依托关陇集团、太原兵力和关中地区的行政资源。随后李世民等人继续平定割据势力，唐朝才逐步完成统一。
""",
    },
    {
        "stem": "chinese-history-wang-anshi-reform",
        "language": "zh",
        "title": "王安石变法的目标与争议",
        "question": "王安石变法试图解决哪些财政和社会问题，为什么引发争议？",
        "body": """# 王安石变法的目标与争议

## 改革目标

北宋中期面临财政压力、边防支出增加和土地兼并等问题。王安石主持的新法包括青苗法、募役法、市易法和方田均税法，目标是增加国家财政能力，减轻部分农户对高利贷和差役的依赖。

## 争议焦点

反对者认为新法执行过急，地方官为了完成指标可能加重百姓负担。支持者则强调国家需要更主动地调节经济资源。王安石变法的争议不只在政策本身，也在于中央集权、官僚执行和社会承受能力之间的张力。
""",
    },
    {
        "stem": "world-history-industrial-revolution",
        "language": "en",
        "title": "Industrial Revolution and Factory Production",
        "question": "What changed when factory production replaced household production during the Industrial Revolution?",
        "body": """# Industrial Revolution and Factory Production

## Core Change

The Industrial Revolution shifted production from households and small workshops into factories powered by water, steam, and later electricity. Textile manufacturing was an early example: spinning and weaving machines raised output, concentrated labor, and required new forms of supervision.

## Social Effects

Factory production changed the rhythm of work. Labor became tied to clocks, wages, and urban housing rather than seasonal household production. The change increased output but also created problems such as unsafe working conditions, child labor, and crowded industrial cities.
""",
    },
    {
        "stem": "world-history-french-revolution",
        "language": "en",
        "title": "French Revolution and Political Legitimacy",
        "question": "How did the French Revolution challenge older ideas of political legitimacy?",
        "body": """# French Revolution and Political Legitimacy

## Old Order

Before 1789, French monarchy drew legitimacy from dynasty, religion, and inherited privilege. The Estates-General reflected social hierarchy rather than equal citizenship.

## Revolutionary Shift

The French Revolution argued that sovereignty belonged to the nation. The Declaration of the Rights of Man and of the Citizen framed rights as universal rather than granted by a king. This change inspired constitutional politics, mass participation, and later conflicts over terror, war, and republican authority.
""",
    },
    {
        "stem": "science-plate-tectonics",
        "language": "zh",
        "title": "板块构造与地震分布",
        "question": "为什么板块边界附近更容易发生地震和火山活动？",
        "body": """# 板块构造与地震分布

## 基本机制

板块构造理论认为，地球岩石圈由多个板块组成，板块在软流圈上缓慢移动。板块边界分为张裂边界、汇聚边界和转换边界，不同边界对应不同的地质活动。

## 地震与火山

在汇聚边界，海洋板块可能俯冲到大陆板块之下，产生深源地震和火山弧。在转换边界，板块水平错动会积累应力，突然释放时形成地震。因此，环太平洋地区成为地震和火山活动密集区域。
""",
    },
    {
        "stem": "science-photosynthesis",
        "language": "en",
        "title": "Photosynthesis and Energy Conversion",
        "question": "What role does chlorophyll play in photosynthesis?",
        "body": """# Photosynthesis and Energy Conversion

## Light Capture

Photosynthesis converts light energy into chemical energy. Chlorophyll molecules in chloroplasts absorb mainly blue and red light, exciting electrons that move through an electron transport chain.

## Sugar Formation

The light reactions produce ATP and NADPH. The Calvin cycle then uses those molecules to fix carbon dioxide into sugars. Chlorophyll does not directly make sugar; it starts the energy conversion that makes sugar production possible.
""",
    },
    {
        "stem": "medicine-vaccination-immunity",
        "language": "zh",
        "title": "疫苗与免疫记忆",
        "question": "疫苗为什么能帮助人体形成免疫记忆？",
        "body": """# 疫苗与免疫记忆

## 原理

疫苗通过安全方式向免疫系统展示病原体的抗原，例如灭活病原体、蛋白片段或 mRNA 指令。免疫细胞识别抗原后，会产生抗体反应，并形成记忆 B 细胞和记忆 T 细胞。

## 保护作用

当人体之后遇到真实病原体，免疫记忆能让反应更快、更强，从而降低重症风险。疫苗并不保证所有人完全不感染，但通常能显著降低严重疾病和传播风险。
""",
    },
    {
        "stem": "medicine-antibiotic-resistance",
        "language": "en",
        "title": "Antibiotic Resistance",
        "question": "Why does unnecessary antibiotic use increase resistance?",
        "body": """# Antibiotic Resistance

## Selection Pressure

Antibiotics kill susceptible bacteria, but resistant variants may survive. When antibiotics are used unnecessarily or stopped too early, they create selection pressure that lets resistant bacteria multiply.

## Public Health Risk

Resistance can spread through plasmids, hospitals, farms, and community transmission. The result is that ordinary infections become harder to treat. Stewardship programs reduce misuse by matching drug choice, dose, and duration to evidence.
""",
    },
    {
        "stem": "law-contract-offer-acceptance",
        "language": "zh",
        "title": "合同成立中的要约与承诺",
        "question": "合同成立为什么通常需要要约和承诺？",
        "body": """# 合同成立中的要约与承诺

## 基本概念

在合同法中，要约是希望与他人订立合同的明确意思表示，承诺是受要约人同意要约内容的意思表示。二者一致，通常表明当事人对主要条款形成合意。

## 风险边界

如果表达只是邀请对方报价，通常不构成要约。若承诺改变了价格、数量或履行期限等实质内容，可能被视为新的要约。区分这些概念有助于判断合同是否已经成立。
""",
    },
    {
        "stem": "law-copyright-fair-use",
        "language": "en",
        "title": "Copyright and Fair Use",
        "question": "What factors are commonly considered in fair use analysis?",
        "body": """# Copyright and Fair Use

## Four Factors

Fair use analysis often considers the purpose of use, the nature of the copyrighted work, the amount used, and the effect on the potential market. Transformative educational or critical uses are more likely to favor fair use than purely commercial copying.

## Practical Limit

Fair use is context-specific and not a mechanical checklist. Using a short excerpt for commentary may be allowed, while reproducing the core of a creative work can still be risky even if the excerpt is not very long.
""",
    },
    {
        "stem": "finance-compound-interest",
        "language": "zh",
        "title": "复利与长期投资",
        "question": "复利为什么会放大长期投资收益？",
        "body": """# 复利与长期投资

## 复利机制

复利指收益继续产生收益。若投资收益被重新投入，本金会随时间扩大，下一期收益也以更大的本金为基础计算。因此，在收益率稳定时，时间越长，复利效应越明显。

## 风险提醒

复利不是保证收益。市场波动、费用、税收和错误的资产配置都会影响最终结果。理解复利的意义在于重视时间、成本控制和风险分散，而不是追求短期高收益。
""",
    },
    {
        "stem": "finance-inflation-bonds",
        "language": "en",
        "title": "Inflation and Bond Prices",
        "question": "Why can rising inflation reduce the price of existing bonds?",
        "body": """# Inflation and Bond Prices

## Interest Rate Link

When inflation rises, central banks may raise interest rates. New bonds then offer higher yields, making older bonds with lower coupons less attractive. To compete, the market price of existing bonds usually falls.

## Duration Risk

Long-duration bonds are more sensitive to rate changes because their cash flows arrive farther in the future. Inflation-linked bonds can reduce this risk, but they still have price volatility when real yields change.
""",
    },
    {
        "stem": "geography-monsoon-climate",
        "language": "zh",
        "title": "季风气候与降水分布",
        "question": "季风为什么会导致明显的雨季和旱季？",
        "body": """# 季风气候与降水分布

## 形成原因

季风主要由海陆热力差异和气压带季节移动造成。夏季大陆升温快，形成低压，海洋湿润气流向陆地输送水汽；冬季大陆降温快，风向反转，空气较干燥。

## 降水影响

南亚和东亚许多地区受季风影响明显。夏季风强弱会影响农业灌溉、洪涝风险和水库调度。若季风来得晚或偏弱，可能造成旱情；若水汽过强，则可能引发洪水。
""",
    },
    {
        "stem": "geography-river-deltas",
        "language": "en",
        "title": "River Deltas and Sediment",
        "question": "How do river deltas form?",
        "body": """# River Deltas and Sediment

## Formation

A river delta forms when a river carries sediment to a slower body of water such as a sea or lake. As the current slows, sand, silt, and clay settle out and build new land.

## Human Pressure

Dams can trap sediment upstream, reducing delta growth. At the same time, groundwater pumping and sea-level rise can make deltas sink or flood. Many large deltas are fertile and densely populated, so these changes create major planning challenges.
""",
    },
    {
        "stem": "literature-dream-red-chamber",
        "language": "zh",
        "title": "红楼梦中的家族兴衰",
        "question": "《红楼梦》如何通过贾府表现家族兴衰？",
        "body": """# 红楼梦中的家族兴衰

## 叙事核心

《红楼梦》以贾府为中心，描写贵族家庭的日常生活、人情关系和制度性衰败。大观园既是青春与才情的空间，也是家族繁华的短暂象征。

## 主题表达

小说通过财务亏空、礼法压力、婚姻安排和人物命运，表现盛极而衰的过程。贾宝玉、林黛玉和薛宝钗的关系不只是爱情叙事，也折射家族利益与个人情感之间的冲突。
""",
    },
    {
        "stem": "literature-shakespeare-macbeth",
        "language": "en",
        "title": "Macbeth and Ambition",
        "question": "How does Macbeth portray the danger of unchecked ambition?",
        "body": """# Macbeth and Ambition

## Tragic Desire

Shakespeare's Macbeth presents ambition as a force that can destroy judgment. Macbeth begins as a respected warrior, but the witches' prophecy and Lady Macbeth's pressure turn possibility into obsession.

## Moral Collapse

After Duncan's murder, Macbeth uses more violence to protect his crown. Each crime makes him less secure, not more powerful. The play links unchecked ambition with fear, isolation, and the breakdown of moral order.
""",
    },
    {
        "stem": "chinese-history-qin-unification",
        "language": "zh",
        "title": "秦统一六国与郡县制",
        "question": "秦朝统一后为什么推行郡县制，它与分封制有什么不同？",
        "body": """# 秦统一六国与郡县制

## 统一背景

战国后期，秦国通过商鞅变法积累了较强的军事和行政能力。秦王嬴政先后灭韩、赵、魏、楚、燕、齐，于公元前 221 年完成统一，建立中国历史上第一个中央集权王朝。

## 制度变化

秦朝废除分封制，推行郡县制，由中央任命地方官员管理行政事务。分封制依靠宗族和诸侯维系地方秩序，郡县制则强调官僚任免和中央控制。该制度增强了统一国家的行政整合能力，也加重了基层治理压力。
""",
    },
    {
        "stem": "chinese-history-opium-war",
        "language": "zh",
        "title": "鸦片战争与近代中国开端",
        "question": "鸦片战争为什么常被视为中国近代史的开端？",
        "body": """# 鸦片战争与近代中国开端

## 战争原因

19 世纪上半叶，中英贸易失衡、鸦片走私和清政府禁烟政策共同加剧冲突。林则徐虎门销烟后，英国以保护贸易为由发动战争。

## 历史影响

1842 年《南京条约》签订，清政府割让香港岛、开放通商口岸并支付赔款。鸦片战争打破了传统朝贡和闭关体系，使中国被迫进入不平等条约体系，因此常被视为中国近代史的开端。
""",
    },
    {
        "stem": "world-history-roman-republic",
        "language": "en",
        "title": "Roman Republic and Checks on Power",
        "question": "How did the Roman Republic try to prevent one person from holding too much power?",
        "body": """# Roman Republic and Checks on Power

## Shared Authority

The Roman Republic divided authority among consuls, the Senate, assemblies, and magistrates. Two consuls served at the same time and could block each other's actions, reducing the chance that one leader could dominate the state.

## Limits and Tensions

Annual terms, veto powers, and mixed institutions were meant to check ambition. Yet social inequality, military loyalty to generals, and civil wars weakened republican safeguards. The later rise of Julius Caesar showed that institutions alone could fail when political norms collapsed.
""",
    },
    {
        "stem": "world-history-cold-war-containment",
        "language": "en",
        "title": "Cold War Containment Policy",
        "question": "What was the main goal of containment during the Cold War?",
        "body": """# Cold War Containment Policy

## Strategic Goal

Containment was a United States strategy aimed at limiting the spread of Soviet influence after World War II. Rather than directly overthrowing the Soviet Union, policymakers sought to prevent communist expansion through alliances, economic aid, military deterrence, and regional commitments.

## Examples

The Truman Doctrine, Marshall Plan, NATO, and the Korean War all reflected containment thinking. The policy shaped decades of diplomacy and conflict, but it also led the United States into controversial interventions where local politics were interpreted through a Cold War lens.
""",
    },
    {
        "stem": "technology-public-key-cryptography",
        "language": "zh",
        "title": "公钥密码学与数字签名",
        "question": "公钥密码学如何支持数字签名和身份验证？",
        "body": """# 公钥密码学与数字签名

## 密钥结构

公钥密码学使用一对密钥：公钥可以公开，私钥必须保密。发送方可以用私钥生成数字签名，接收方用对应公钥验证签名是否匹配。

## 应用价值

数字签名能证明消息确实来自私钥持有者，并检测内容是否被篡改。HTTPS 证书、软件包签名和区块链交易都依赖类似机制。风险在于私钥泄露会破坏身份可信度，因此密钥管理和吊销机制同样重要。
""",
    },
    {
        "stem": "technology-database-indexes",
        "language": "en",
        "title": "Database Indexes and Query Speed",
        "question": "Why can an index make database reads faster but writes slower?",
        "body": """# Database Indexes and Query Speed

## Read Performance

A database index stores selected column values in a structure such as a B-tree, allowing the database to find matching rows without scanning the whole table. Indexes are especially useful for filters, joins, and ordered results.

## Write Cost

Every insert, update, or delete must also update affected indexes. Too many indexes increase storage use and write latency. Good schema design chooses indexes that match important query patterns rather than indexing every column.
""",
    },
    {
        "stem": "economics-supply-demand",
        "language": "zh",
        "title": "供给需求与价格变化",
        "question": "供给和需求如何共同影响市场价格？",
        "body": """# 供给需求与价格变化

## 基本关系

需求表示消费者在不同价格下愿意购买的数量，供给表示生产者愿意出售的数量。当需求增加而供给不变时，价格通常上升；当供给增加而需求不变时，价格通常下降。

## 市场调整

价格变化会影响买卖双方行为。高价格鼓励生产者扩大供给，也可能抑制消费者购买。现实市场还会受到税收、补贴、预期和替代品影响，因此供需模型是分析起点，而不是完整解释。
""",
    },
    {
        "stem": "economics-externalities",
        "language": "en",
        "title": "Externalities and Market Failure",
        "question": "Why can externalities cause market outcomes to be inefficient?",
        "body": """# Externalities and Market Failure

## Private and Social Costs

An externality occurs when an economic activity affects people who are not part of the transaction. Pollution is a negative externality because a factory may not pay the full social cost of dirty air or water.

## Policy Response

When external costs are ignored, markets can produce too much of the harmful activity. Taxes, regulation, tradable permits, or liability rules can push private decisions closer to social costs. Positive externalities, such as vaccination, may justify subsidies.
""",
    },
]


NEGATIVES = [
    ("How do I configure a Docker bridge network?", "en"),
    ("今天北京的天气怎么样？", "zh"),
    ("What is the best recipe for sourdough bread?", "en"),
    ("如何修理自行车变速器？", "zh"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a diverse synthetic eval dataset.")
    parser.add_argument("--dataset", default="synthetic-diverse-v1")
    args = parser.parse_args()

    root = Path("datasets") / args.dataset
    corpus = root / "corpus"
    corpus.mkdir(parents=True, exist_ok=True)
    for topic in TOPICS:
        write_doc(corpus, topic)
    write_dataset_yaml(root, args.dataset)
    write_queries_yaml(root / "queries.yaml")
    print(f"wrote {len(TOPICS)} docs and {len(TOPICS) + len(NEGATIVES)} queries to {root}")
    return 0


def write_doc(corpus: Path, topic: dict[str, str]) -> None:
    frontmatter = (
        "---\n"
        f"title: {topic['title']}\n"
        f"language: {topic['language']}\n"
        "source: local-diverse-synthetic\n"
        "---\n\n"
    )
    (corpus / f"{topic['stem']}.md").write_text(frontmatter + topic["body"] + "\n", encoding="utf-8")


def write_dataset_yaml(root: Path, dataset: str) -> None:
    text = f"""name: {dataset}
description: >
  Diverse synthetic retrieval dataset covering Chinese history, world history,
  science, medicine, law, finance, geography, and literature in Chinese and
  English. Designed to broaden corpus variety beyond DIKW/RAG-specific docs.
# Thresholds intentionally omitted until calibrated with dikw eval.
"""
    (root / "dataset.yaml").write_text(text, encoding="utf-8")


def write_queries_yaml(path: Path) -> None:
    lines = ["queries:"]
    for topic in TOPICS:
        lines.append(f"  - q: {quote(topic['question'])}")
        lines.append(f"    expect_any: [{topic['stem']}]")
    for question, _lang in NEGATIVES:
        lines.append(f"  - q: {quote(question)}")
        lines.append("    expect_none: true")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


if __name__ == "__main__":
    sys.exit(main())

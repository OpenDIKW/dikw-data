from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "datasets" / "synthetic-fruits-multimodal-v1"
CORPUS_DIR = DATASET_DIR / "corpus"
IMAGE_DIR = CORPUS_DIR / "images" / "fruits"

W = 256
H = 256


def blend(base: tuple[int, int, int], top: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    alpha = max(0.0, min(1.0, alpha))
    return tuple(round(base[i] * (1 - alpha) + top[i] * alpha) for i in range(3))


def circle(px: float, py: float, cx: float, cy: float, r: float) -> float:
    d = math.hypot(px - cx, py - cy)
    return 1.0 if d <= r else 0.0


def ellipse(px: float, py: float, cx: float, cy: float, rx: float, ry: float, angle: float = 0.0) -> float:
    ca = math.cos(angle)
    sa = math.sin(angle)
    x = px - cx
    y = py - cy
    xr = x * ca + y * sa
    yr = -x * sa + y * ca
    return 1.0 if (xr / rx) ** 2 + (yr / ry) ** 2 <= 1.0 else 0.0


def polygon(px: float, py: float, points: list[tuple[float, float]]) -> float:
    inside = False
    j = len(points) - 1
    for i, (xi, yi) in enumerate(points):
        xj, yj = points[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-9) + xi):
            inside = not inside
        j = i
    return 1.0 if inside else 0.0


def draw_icon(kind: str) -> list[tuple[int, int, int]]:
    bg = (249, 249, 244)
    pixels: list[tuple[int, int, int]] = []
    for y in range(H):
        for x in range(W):
            p = bg
            # soft table shadow
            if ellipse(x, y, 128, 214, 76, 14):
                p = blend(p, (210, 210, 200), 0.32)

            if kind == "apple":
                if circle(x, y, 104, 128, 50) or circle(x, y, 150, 128, 50) or ellipse(x, y, 128, 150, 64, 58):
                    p = blend(p, (196, 34, 45), 0.96)
                if ellipse(x, y, 151, 77, 32, 14, -0.62):
                    p = blend(p, (67, 142, 62), 0.95)
                if ellipse(x, y, 127, 84, 7, 23, 0.16):
                    p = blend(p, (95, 55, 32), 0.95)
                if ellipse(x, y, 102, 113, 17, 31, -0.65):
                    p = blend(p, (240, 126, 125), 0.45)

            elif kind == "banana":
                outer = ellipse(x, y, 128, 139, 91, 35, -0.45)
                inner = ellipse(x, y, 137, 115, 88, 34, -0.45)
                if outer and not inner:
                    p = blend(p, (238, 201, 52), 0.98)
                if outer and not inner and (x + y) % 23 == 0:
                    p = blend(p, (166, 123, 34), 0.55)
                if ellipse(x, y, 64, 178, 11, 8, -0.45) or ellipse(x, y, 202, 91, 12, 8, -0.45):
                    p = blend(p, (98, 67, 37), 0.85)

            elif kind == "orange":
                if circle(x, y, 128, 136, 65):
                    p = blend(p, (230, 127, 29), 0.97)
                if ellipse(x, y, 103, 112, 18, 33, -0.75):
                    p = blend(p, (251, 184, 92), 0.42)
                if ellipse(x, y, 141, 71, 28, 13, -0.45):
                    p = blend(p, (69, 145, 70), 0.95)

            elif kind == "strawberry":
                body = circle(x, y, 128, 141, 62) and polygon(x, y, [(65, 119), (191, 119), (128, 218)])
                top = polygon(x, y, [(80, 91), (101, 122), (124, 90), (143, 122), (175, 91), (160, 132), (95, 132)])
                if body:
                    p = blend(p, (212, 30, 56), 0.98)
                if top:
                    p = blend(p, (54, 142, 64), 0.95)
                if body and ((x * 3 + y * 5) % 37 < 2):
                    p = blend(p, (255, 227, 130), 0.9)

            elif kind == "grape":
                centers = [(106, 101), (132, 101), (158, 104), (93, 128), (119, 130), (145, 132), (171, 132), (107, 158), (134, 160), (160, 160), (132, 187)]
                for idx, (cx, cy) in enumerate(centers):
                    if circle(x, y, cx, cy, 18):
                        color = (111, 62, 155) if idx % 2 else (86, 51, 136)
                        p = blend(p, color, 0.95)
                    if ellipse(x, y, cx - 6, cy - 7, 5, 7, -0.7):
                        p = blend(p, (178, 136, 213), 0.35)
                if ellipse(x, y, 149, 70, 29, 11, -0.52):
                    p = blend(p, (72, 139, 75), 0.95)

            elif kind == "watermelon":
                rind = polygon(x, y, [(51, 167), (205, 167), (128, 75)])
                flesh = polygon(x, y, [(69, 160), (187, 160), (128, 91)])
                if rind:
                    p = blend(p, (55, 137, 73), 0.96)
                if flesh:
                    p = blend(p, (229, 62, 72), 0.96)
                if polygon(x, y, [(62, 164), (194, 164), (187, 155), (69, 155)]):
                    p = blend(p, (229, 232, 164), 0.85)
                for sx, sy in [(111, 131), (131, 145), (151, 129), (126, 115)]:
                    if ellipse(x, y, sx, sy, 4, 8):
                        p = blend(p, (44, 34, 31), 0.95)

            elif kind == "pineapple":
                leaves = [
                    [(128, 39), (113, 93), (143, 93)],
                    [(91, 55), (106, 105), (127, 88)],
                    [(165, 55), (149, 105), (129, 88)],
                    [(111, 48), (119, 101), (136, 92)],
                    [(145, 48), (138, 101), (121, 92)],
                ]
                for pts in leaves:
                    if polygon(x, y, pts):
                        p = blend(p, (62, 142, 75), 0.95)
                if ellipse(x, y, 128, 151, 51, 72):
                    p = blend(p, (222, 161, 47), 0.98)
                    if (x + y) % 24 < 2 or (x - y) % 25 < 2:
                        p = blend(p, (126, 91, 35), 0.35)

            elif kind == "kiwi":
                if circle(x, y, 128, 137, 68):
                    p = blend(p, (134, 92, 50), 0.95)
                if circle(x, y, 128, 137, 56):
                    p = blend(p, (104, 165, 66), 0.98)
                if circle(x, y, 128, 137, 20):
                    p = blend(p, (239, 235, 188), 0.95)
                if circle(x, y, 128, 137, 4):
                    p = blend(p, (245, 247, 213), 0.98)
                for i in range(24):
                    a = i * math.tau / 24
                    sx = 128 + math.cos(a) * 38
                    sy = 137 + math.sin(a) * 38
                    if circle(x, y, sx, sy, 2.2):
                        p = blend(p, (34, 33, 28), 0.9)

            elif kind == "mango":
                if ellipse(x, y, 128, 139, 57, 75, -0.35):
                    p = blend(p, (239, 164, 43), 0.97)
                if ellipse(x, y, 104, 114, 28, 47, -0.45):
                    p = blend(p, (229, 88, 54), 0.52)
                if ellipse(x, y, 146, 169, 36, 45, -0.2):
                    p = blend(p, (247, 199, 70), 0.5)
                if ellipse(x, y, 154, 70, 31, 12, -0.55):
                    p = blend(p, (76, 145, 69), 0.95)

            elif kind == "lemon":
                body = ellipse(x, y, 128, 137, 74, 45, -0.28)
                tips = circle(x, y, 58, 160, 14) or circle(x, y, 198, 113, 14)
                if body or tips:
                    p = blend(p, (237, 220, 65), 0.98)
                if ellipse(x, y, 107, 119, 25, 18, -0.4):
                    p = blend(p, (255, 246, 139), 0.42)

            pixels.append(p)
    return pixels


def write_png(path: Path, pixels: list[tuple[int, int, int]]) -> None:
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        for x in range(W):
            raw.extend(pixels[y * W + x])

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


FRUITS = [
    ("apple", "苹果", "Apple", "红苹果富含膳食纤维和多酚，图像特征是圆形红色果身、短果梗和绿色叶片。"),
    ("banana", "香蕉", "Banana", "香蕉通常呈弯月形，成熟时表皮金黄，是高钾和易消化碳水的常见水果。"),
    ("orange", "橙子", "Orange", "橙子有明亮橙色外皮和圆形轮廓，常用于测试颜色相近目标的图文匹配。"),
    ("strawberry", "草莓", "Strawberry", "草莓外观呈红色心形或圆锥形，表面有浅色小籽，顶部有绿色萼片。"),
    ("grape", "葡萄", "Grape", "葡萄以成串小圆果出现，紫葡萄的多颗果粒适合评测数量、聚类和局部图像召回。"),
    ("watermelon", "西瓜", "Watermelon", "西瓜切片具有绿色瓜皮、浅色内层和红色果肉，黑色籽粒是显著视觉线索。"),
    ("pineapple", "菠萝", "Pineapple", "菠萝有金黄色椭圆果身、交错纹理和绿色冠叶，适合测试纹理与形状组合。"),
    ("kiwi", "猕猴桃", "Kiwi", "猕猴桃切面由棕色外皮、绿色果肉、白色中心和环形黑籽构成。"),
    ("mango", "芒果", "Mango", "芒果多为黄橙色椭圆果形，局部带红色或绿色过渡，适合测试细粒度颜色描述。"),
    ("lemon", "柠檬", "Lemon", "柠檬常见为亮黄色椭圆形，两端略尖，与橙子可形成相近颜色但不同形状的对照。"),
]


def write_markdown() -> None:
    lines = [
        "---",
        "title: 多水果图片召回评测",
        "language: zh-CN",
        "source: local-synthetic",
        "modality: image-text",
        "version: synthetic-fruits-multimodal-v1",
        "---",
        "",
        "# 多水果图片召回评测",
        "",
        "本文档用于评测多模态检索系统能否根据文本线索召回包含对应水果图片的文档或图片资产。每个小节都包含一张本地 PNG 图片和一段可检索描述，覆盖颜色、形状、纹理、局部结构和中英文名称。",
        "",
    ]
    for slug, zh, en, desc in FRUITS:
        lines.extend(
            [
                f"## {zh} / {en}",
                "",
                f"![{zh}图片 - {en}](./images/fruits/{slug}.png)",
                "",
                desc,
                "",
                f"检索提示：{zh}、{en}、水果图片、颜色、形状、局部特征。",
                "",
            ]
        )
    (CORPUS_DIR / "fruits-gallery.md").write_text("\n".join(lines), encoding="utf-8")


def write_dataset_files() -> None:
    (DATASET_DIR / "dataset.yaml").write_text(
        "\n".join(
            [
                "name: synthetic-fruits-multimodal-v1",
                "description: >",
                "  One-document multimodal retrieval fixture containing local PNG fruit images",
                "  referenced from Markdown. It is intended to verify image asset parsing,",
                "  multimodal embedding, and text-to-image recall behavior.",
                "thresholds:",
                "  hit_at_3: 1.0",
                "  hit_at_10: 1.0",
                "  mrr: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )
    queries = [
        ("哪张图片展示了红色圆形苹果和绿色叶片？", "apple"),
        ("Find the curved yellow banana image.", "banana"),
        ("检索包含橙色圆形橙子的水果图片。", "orange"),
        ("哪种水果图片有红色果身、浅色籽和绿色萼片？", "strawberry"),
        ("Find the purple grape cluster image.", "grape"),
        ("检索绿色瓜皮、红色果肉和黑籽的西瓜切片。", "watermelon"),
        ("Which image has a yellow pineapple body with green crown leaves?", "pineapple"),
        ("查找绿色切面、白色中心和黑色环形籽的猕猴桃。", "kiwi"),
        ("Find the orange-yellow mango with red color transition.", "mango"),
        ("检索亮黄色椭圆形、两端略尖的柠檬图片。", "lemon"),
    ]
    lines = ["queries:"]
    for text, tag in queries:
        lines.extend(
            [
                f"  - id: fruit_{tag}",
                f"    q: {text}",
                "    expect_any: [fruits-gallery]",
            ]
        )
    (DATASET_DIR / "queries.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    for slug, *_ in FRUITS:
        write_png(IMAGE_DIR / f"{slug}.png", draw_icon(slug))
    write_markdown()
    write_dataset_files()
    print(f"wrote {DATASET_DIR}")


if __name__ == "__main__":
    main()

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / "datasets" / "synthetic-animals-multimodal-v1"
CORPUS_DIR = DATASET_DIR / "corpus"
IMAGE_DIR = CORPUS_DIR / "images" / "animals"

W = 256
H = 256


def blend(base: tuple[int, int, int], top: tuple[int, int, int], alpha: float) -> tuple[int, int, int]:
    alpha = max(0.0, min(1.0, alpha))
    return tuple(round(base[i] * (1 - alpha) + top[i] * alpha) for i in range(3))


def circle(px: float, py: float, cx: float, cy: float, r: float) -> bool:
    return math.hypot(px - cx, py - cy) <= r


def ellipse(px: float, py: float, cx: float, cy: float, rx: float, ry: float, angle: float = 0.0) -> bool:
    ca = math.cos(angle)
    sa = math.sin(angle)
    x = px - cx
    y = py - cy
    xr = x * ca + y * sa
    yr = -x * sa + y * ca
    return (xr / rx) ** 2 + (yr / ry) ** 2 <= 1.0


def polygon(px: float, py: float, points: list[tuple[float, float]]) -> bool:
    inside = False
    j = len(points) - 1
    for i, (xi, yi) in enumerate(points):
        xj, yj = points[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-9) + xi):
            inside = not inside
        j = i
    return inside


def eye(x: float, y: float, cx: float, cy: float) -> bool:
    return circle(x, y, cx, cy, 4)


def draw_icon(kind: str) -> list[tuple[int, int, int]]:
    bg = (247, 249, 246)
    pixels: list[tuple[int, int, int]] = []
    for y in range(H):
        for x in range(W):
            p = bg
            if ellipse(x, y, 128, 220, 78, 12):
                p = blend(p, (210, 213, 205), 0.35)

            if kind == "cat":
                if polygon(x, y, [(74, 89), (101, 45), (112, 101)]):
                    p = blend(p, (218, 145, 69), 0.96)
                if polygon(x, y, [(181, 89), (155, 45), (143, 101)]):
                    p = blend(p, (218, 145, 69), 0.96)
                if circle(x, y, 128, 133, 64):
                    p = blend(p, (224, 151, 74), 0.98)
                if eye(x, y, 105, 124) or eye(x, y, 151, 124):
                    p = blend(p, (30, 35, 30), 0.96)
                if ellipse(x, y, 128, 145, 9, 6):
                    p = blend(p, (93, 48, 45), 0.9)
                if (abs(y - 150) < 2 and 88 < x < 115) or (abs(y - 150) < 2 and 141 < x < 168):
                    p = blend(p, (80, 58, 47), 0.55)

            elif kind == "dog":
                if ellipse(x, y, 82, 127, 23, 43, 0.25) or ellipse(x, y, 174, 127, 23, 43, -0.25):
                    p = blend(p, (105, 72, 43), 0.96)
                if circle(x, y, 128, 136, 63):
                    p = blend(p, (181, 127, 74), 0.98)
                if ellipse(x, y, 128, 158, 34, 24):
                    p = blend(p, (232, 201, 158), 0.85)
                if eye(x, y, 105, 128) or eye(x, y, 151, 128):
                    p = blend(p, (28, 28, 28), 0.96)
                if ellipse(x, y, 128, 151, 10, 7):
                    p = blend(p, (45, 35, 30), 0.95)

            elif kind == "rabbit":
                if ellipse(x, y, 101, 82, 17, 55, -0.18) or ellipse(x, y, 154, 82, 17, 55, 0.18):
                    p = blend(p, (224, 224, 218), 0.98)
                if ellipse(x, y, 101, 82, 8, 42, -0.18) or ellipse(x, y, 154, 82, 8, 42, 0.18):
                    p = blend(p, (239, 181, 187), 0.72)
                if circle(x, y, 128, 149, 61):
                    p = blend(p, (229, 229, 223), 0.98)
                if eye(x, y, 106, 140) or eye(x, y, 150, 140):
                    p = blend(p, (35, 35, 34), 0.95)
                if ellipse(x, y, 128, 157, 7, 5):
                    p = blend(p, (221, 135, 145), 0.9)

            elif kind == "panda":
                if circle(x, y, 89, 93, 25) or circle(x, y, 167, 93, 25):
                    p = blend(p, (35, 38, 36), 0.96)
                if circle(x, y, 128, 138, 65):
                    p = blend(p, (238, 239, 232), 0.98)
                if ellipse(x, y, 105, 130, 18, 25, -0.35) or ellipse(x, y, 151, 130, 18, 25, 0.35):
                    p = blend(p, (35, 38, 36), 0.96)
                if eye(x, y, 105, 128) or eye(x, y, 151, 128):
                    p = blend(p, (245, 245, 240), 0.92)
                if ellipse(x, y, 128, 154, 10, 7):
                    p = blend(p, (32, 32, 31), 0.95)

            elif kind == "elephant":
                if ellipse(x, y, 77, 137, 36, 48, -0.25) or ellipse(x, y, 179, 137, 36, 48, 0.25):
                    p = blend(p, (141, 151, 154), 0.95)
                if circle(x, y, 128, 133, 60):
                    p = blend(p, (154, 164, 167), 0.98)
                if ellipse(x, y, 128, 171, 18, 48):
                    p = blend(p, (132, 143, 148), 0.98)
                if eye(x, y, 108, 124) or eye(x, y, 148, 124):
                    p = blend(p, (28, 31, 31), 0.92)
                if polygon(x, y, [(86, 159), (61, 177), (92, 174)]) or polygon(x, y, [(170, 159), (195, 177), (164, 174)]):
                    p = blend(p, (238, 232, 210), 0.9)

            elif kind == "lion":
                if circle(x, y, 128, 135, 77):
                    p = blend(p, (162, 95, 38), 0.96)
                for a in range(18):
                    ang = a * math.tau / 18
                    cx = 128 + math.cos(ang) * 69
                    cy = 135 + math.sin(ang) * 69
                    if polygon(x, y, [(128, 135), (cx + math.cos(ang - 0.18) * 24, cy + math.sin(ang - 0.18) * 24), (cx + math.cos(ang + 0.18) * 24, cy + math.sin(ang + 0.18) * 24)]):
                        p = blend(p, (139, 78, 33), 0.72)
                if circle(x, y, 128, 137, 49):
                    p = blend(p, (219, 154, 70), 0.96)
                if eye(x, y, 110, 130) or eye(x, y, 146, 130):
                    p = blend(p, (30, 28, 24), 0.96)
                if ellipse(x, y, 128, 149, 8, 6):
                    p = blend(p, (88, 50, 35), 0.92)

            elif kind == "penguin":
                if ellipse(x, y, 128, 143, 50, 75):
                    p = blend(p, (36, 45, 52), 0.98)
                if ellipse(x, y, 128, 158, 34, 53):
                    p = blend(p, (238, 238, 230), 0.96)
                if eye(x, y, 111, 111) or eye(x, y, 145, 111):
                    p = blend(p, (18, 18, 17), 0.96)
                if polygon(x, y, [(119, 126), (137, 126), (128, 141)]):
                    p = blend(p, (232, 151, 48), 0.95)
                if polygon(x, y, [(99, 216), (119, 216), (108, 227)]) or polygon(x, y, [(137, 216), (157, 216), (148, 227)]):
                    p = blend(p, (225, 142, 45), 0.95)

            elif kind == "owl":
                if circle(x, y, 101, 119, 40) or circle(x, y, 155, 119, 40) or ellipse(x, y, 128, 151, 62, 67):
                    p = blend(p, (132, 87, 48), 0.98)
                if circle(x, y, 105, 128, 24) or circle(x, y, 151, 128, 24):
                    p = blend(p, (236, 217, 155), 0.95)
                if eye(x, y, 105, 128) or eye(x, y, 151, 128):
                    p = blend(p, (29, 28, 24), 0.98)
                if polygon(x, y, [(121, 144), (135, 144), (128, 158)]):
                    p = blend(p, (218, 142, 48), 0.95)
                if polygon(x, y, [(83, 81), (111, 98), (93, 108)]) or polygon(x, y, [(173, 81), (145, 98), (163, 108)]):
                    p = blend(p, (97, 62, 37), 0.96)

            elif kind == "fox":
                if polygon(x, y, [(74, 82), (102, 48), (110, 105)]) or polygon(x, y, [(182, 82), (154, 48), (146, 105)]):
                    p = blend(p, (205, 91, 42), 0.96)
                if circle(x, y, 128, 136, 61):
                    p = blend(p, (218, 101, 45), 0.98)
                if polygon(x, y, [(76, 143), (128, 206), (180, 143), (151, 174), (105, 174)]):
                    p = blend(p, (238, 230, 210), 0.93)
                if eye(x, y, 106, 128) or eye(x, y, 150, 128):
                    p = blend(p, (28, 27, 24), 0.96)
                if ellipse(x, y, 128, 159, 9, 7):
                    p = blend(p, (40, 32, 26), 0.95)

            elif kind == "turtle":
                if ellipse(x, y, 128, 150, 68, 48):
                    p = blend(p, (74, 135, 75), 0.98)
                    if abs((x - 128) % 28) < 2 or abs((y - 150) % 24) < 2:
                        p = blend(p, (44, 91, 55), 0.28)
                if circle(x, y, 196, 145, 18):
                    p = blend(p, (94, 151, 83), 0.98)
                if eye(x, y, 202, 139):
                    p = blend(p, (25, 28, 23), 0.96)
                for cx, cy in [(83, 115), (84, 184), (155, 114), (158, 185)]:
                    if ellipse(x, y, cx, cy, 18, 11, 0.6):
                        p = blend(p, (83, 139, 76), 0.95)

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


ANIMALS = [
    ("cat", "猫", "Cat", "猫是常见伴侣动物，图片特征包括三角耳、圆脸、胡须和灵活的面部轮廓。"),
    ("dog", "狗", "Dog", "狗具有下垂耳、短吻部和亲近人类的视觉形象，常用于测试宠物类别召回。"),
    ("rabbit", "兔子", "Rabbit", "兔子最显著的视觉线索是长耳、浅色皮毛和小鼻子，适合检索形状描述。"),
    ("panda", "熊猫", "Panda", "熊猫有黑白分明的毛色、黑眼圈和圆形耳朵，是颜色对比很强的动物图像。"),
    ("elephant", "大象", "Elephant", "大象的关键特征包括大耳朵、长鼻子和灰色体色，便于评测局部结构识别。"),
    ("lion", "狮子", "Lion", "雄狮有浓密鬃毛、金棕色面部和强烈的径向轮廓，可测试纹理与形状组合。"),
    ("penguin", "企鹅", "Penguin", "企鹅具有黑白身体、橙色喙和直立姿态，适合作为鸟类与哺乳动物的对照样本。"),
    ("owl", "猫头鹰", "Owl", "猫头鹰有大眼睛、短喙和圆形头部，图像中眼部区域非常突出。"),
    ("fox", "狐狸", "Fox", "狐狸通常有橙红色毛发、尖耳和白色胸脸区域，适合颜色和脸部轮廓检索。"),
    ("turtle", "乌龟", "Turtle", "乌龟有绿色或棕色龟壳、伸出的头部和短足，适合测试壳体纹理识别。"),
]


def write_markdown() -> None:
    lines = [
        "---",
        "title: 多动物图片召回评测",
        "language: zh-CN",
        "source: local-synthetic",
        "modality: image-text",
        "version: synthetic-animals-multimodal-v1",
        "---",
        "",
        "# 多动物图片召回评测",
        "",
        "本文档用于评测多模态检索系统能否根据动物名称、颜色、形状和局部结构描述召回对应图片资产。每个小节都包含一张本地 PNG 图片和一段中英文可检索描述。",
        "",
    ]
    for slug, zh, en, desc in ANIMALS:
        lines.extend(
            [
                f"## {zh} / {en}",
                "",
                f"![{zh}图片 - {en}](./images/animals/{slug}.png)",
                "",
                desc,
                "",
                f"检索提示：{zh}、{en}、动物图片、颜色、形状、局部特征。",
                "",
            ]
        )
    (CORPUS_DIR / "animals-gallery.md").write_text("\n".join(lines), encoding="utf-8")


def write_dataset_files() -> None:
    (DATASET_DIR / "dataset.yaml").write_text(
        "\n".join(
            [
                "name: synthetic-animals-multimodal-v1",
                "description: >",
                "  One-document multimodal retrieval fixture containing local PNG animal images",
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
        ("检索有三角耳、胡须和圆脸的猫图片。", "cat"),
        ("Find the dog image with floppy ears and a short muzzle.", "dog"),
        ("哪张动物图片展示长耳朵和浅色皮毛的兔子？", "rabbit"),
        ("Find the black-and-white panda with dark eye patches.", "panda"),
        ("检索灰色大耳朵和长鼻子的大象图片。", "elephant"),
        ("Which image shows a lion with a brown mane?", "lion"),
        ("查找黑白身体和橙色喙的企鹅图片。", "penguin"),
        ("Find the owl image with large round eyes.", "owl"),
        ("检索橙红色毛发、尖耳和白色面部的狐狸。", "fox"),
        ("Which image shows a turtle with a patterned shell?", "turtle"),
    ]
    lines = ["queries:"]
    for text, tag in queries:
        lines.extend(
            [
                f"  - id: animal_{tag}",
                f"    q: {text}",
                "    expect_any: [animals-gallery]",
            ]
        )
    (DATASET_DIR / "queries.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    for slug, *_ in ANIMALS:
        write_png(IMAGE_DIR / f"{slug}.png", draw_icon(slug))
    write_markdown()
    write_dataset_files()
    print(f"wrote {DATASET_DIR}")


if __name__ == "__main__":
    main()

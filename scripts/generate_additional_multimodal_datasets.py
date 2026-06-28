from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
W = 256
H = 256

Color = tuple[int, int, int]


def blend(base: Color, top: Color, alpha: float) -> Color:
    alpha = max(0.0, min(1.0, alpha))
    return tuple(round(base[i] * (1 - alpha) + top[i] * alpha) for i in range(3))


class Canvas:
    def __init__(self, bg: Color = (248, 249, 246)) -> None:
        self.pixels = [bg for _ in range(W * H)]
        self.ellipse(128, 220, 80, 12, (210, 213, 205), 0.35)

    def set(self, x: int, y: int, color: Color, alpha: float = 1.0) -> None:
        if 0 <= x < W and 0 <= y < H:
            i = y * W + x
            self.pixels[i] = blend(self.pixels[i], color, alpha)

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: Color, alpha: float = 1.0) -> None:
        for y in range(max(0, y0), min(H, y1 + 1)):
            for x in range(max(0, x0), min(W, x1 + 1)):
                self.set(x, y, color, alpha)

    def circle(self, cx: float, cy: float, r: float, color: Color, alpha: float = 1.0) -> None:
        for y in range(max(0, int(cy - r)), min(H, int(cy + r) + 1)):
            for x in range(max(0, int(cx - r)), min(W, int(cx + r) + 1)):
                if math.hypot(x - cx, y - cy) <= r:
                    self.set(x, y, color, alpha)

    def ellipse(self, cx: float, cy: float, rx: float, ry: float, color: Color, alpha: float = 1.0, angle: float = 0.0) -> None:
        ca = math.cos(angle)
        sa = math.sin(angle)
        span = int(max(rx, ry)) + 3
        for y in range(max(0, int(cy - span)), min(H, int(cy + span) + 1)):
            for x in range(max(0, int(cx - span)), min(W, int(cx + span) + 1)):
                dx = x - cx
                dy = y - cy
                xr = dx * ca + dy * sa
                yr = -dx * sa + dy * ca
                if (xr / rx) ** 2 + (yr / ry) ** 2 <= 1.0:
                    self.set(x, y, color, alpha)

    def polygon(self, points: list[tuple[float, float]], color: Color, alpha: float = 1.0) -> None:
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        for y in range(max(0, int(min(ys))), min(H, int(max(ys)) + 1)):
            for x in range(max(0, int(min(xs))), min(W, int(max(xs)) + 1)):
                inside = False
                j = len(points) - 1
                for i, (xi, yi) in enumerate(points):
                    xj, yj = points[j]
                    if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi):
                        inside = not inside
                    j = i
                if inside:
                    self.set(x, y, color, alpha)

    def line(self, x1: float, y1: float, x2: float, y2: float, width: float, color: Color, alpha: float = 1.0) -> None:
        minx = max(0, int(min(x1, x2) - width))
        maxx = min(W, int(max(x1, x2) + width) + 1)
        miny = max(0, int(min(y1, y2) - width))
        maxy = min(H, int(max(y1, y2) + width) + 1)
        vx = x2 - x1
        vy = y2 - y1
        length2 = vx * vx + vy * vy
        for y in range(miny, maxy):
            for x in range(minx, maxx):
                t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((x - x1) * vx + (y - y1) * vy) / length2))
                px = x1 + t * vx
                py = y1 + t * vy
                if math.hypot(x - px, y - py) <= width:
                    self.set(x, y, color, alpha)


def write_png(path: Path, pixels: list[Color]) -> None:
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


def wheel(c: Canvas, x: int, y: int) -> None:
    c.circle(x, y, 16, (35, 38, 40))
    c.circle(x, y, 8, (232, 235, 232))


def vehicle_icon(slug: str) -> list[Color]:
    c = Canvas()
    if slug == "car":
        c.rect(66, 130, 190, 171, (54, 112, 190))
        c.polygon([(88, 130), (110, 98), (153, 98), (175, 130)], (77, 143, 213))
        wheel(c, 94, 174); wheel(c, 164, 174)
    elif slug == "bus":
        c.rect(55, 95, 201, 170, (236, 182, 48)); c.rect(72, 110, 184, 132, (187, 225, 239)); wheel(c, 88, 173); wheel(c, 168, 173)
    elif slug == "train":
        c.rect(54, 98, 188, 167, (74, 133, 181)); c.polygon([(188, 98), (211, 122), (211, 167), (188, 167)], (51, 104, 154)); c.line(55, 191, 205, 191, 3, (80, 80, 78)); c.line(66, 180, 77, 201, 2, (80, 80, 78))
    elif slug == "airplane":
        c.ellipse(130, 128, 76, 13, (208, 214, 219)); c.polygon([(114, 127), (72, 82), (132, 116)], (87, 144, 197)); c.polygon([(123, 135), (83, 181), (141, 141)], (87, 144, 197)); c.polygon([(190, 128), (216, 106), (207, 131)], (208, 214, 219))
    elif slug == "ship":
        c.polygon([(54, 151), (206, 151), (180, 187), (83, 187)], (51, 105, 154)); c.rect(103, 105, 164, 150, (230, 232, 226)); c.rect(130, 79, 151, 105, (207, 73, 53)); c.line(55, 195, 205, 195, 3, (70, 132, 188))
    elif slug == "bicycle":
        wheel(c, 82, 171); wheel(c, 174, 171); c.line(82, 171, 120, 126, 4, (47, 92, 135)); c.line(120, 126, 174, 171, 4, (47, 92, 135)); c.line(101, 171, 151, 171, 4, (47, 92, 135)); c.line(120, 126, 101, 171, 4, (47, 92, 135)); c.line(120, 126, 150, 108, 4, (47, 92, 135))
    elif slug == "motorcycle":
        wheel(c, 80, 174); wheel(c, 176, 174); c.line(83, 169, 124, 136, 5, (38, 54, 62)); c.line(124, 136, 174, 170, 5, (38, 54, 62)); c.ellipse(132, 129, 31, 13, (204, 70, 53)); c.line(156, 121, 185, 102, 4, (38, 54, 62))
    elif slug == "ambulance":
        c.rect(56, 114, 197, 169, (238, 238, 232)); c.rect(80, 95, 148, 114, (238, 238, 232)); c.rect(92, 126, 116, 151, (208, 51, 61)); c.rect(101, 117, 108, 160, (208, 51, 61)); wheel(c, 88, 173); wheel(c, 168, 173)
    elif slug == "fire_truck":
        c.rect(50, 116, 207, 170, (210, 48, 44)); c.rect(146, 96, 190, 116, (210, 48, 44)); c.line(64, 102, 151, 102, 4, (222, 196, 93)); c.line(64, 112, 151, 112, 4, (222, 196, 93)); wheel(c, 86, 174); wheel(c, 170, 174)
    elif slug == "subway":
        c.rect(70, 77, 186, 176, (66, 126, 163)); c.rect(91, 98, 165, 127, (185, 223, 235)); c.circle(101, 154, 7, (242, 231, 120)); c.circle(155, 154, 7, (242, 231, 120)); c.line(91, 195, 111, 176, 3, (82, 82, 80)); c.line(165, 195, 145, 176, 3, (82, 82, 80))
    return c.pixels


def plant_icon(slug: str) -> list[Color]:
    c = Canvas()
    if slug == "rose":
        c.line(128, 190, 128, 116, 5, (64, 140, 72)); c.ellipse(105, 151, 25, 10, (64, 140, 72), angle=-0.35); c.ellipse(151, 159, 25, 10, (64, 140, 72), angle=0.35)
        for a in range(8):
            c.ellipse(128 + math.cos(a * math.tau / 8) * 18, 102 + math.sin(a * math.tau / 8) * 14, 21, 13, (204, 48, 72), angle=a)
        c.circle(128, 102, 18, (178, 37, 62))
    elif slug == "sunflower":
        c.line(128, 195, 128, 126, 6, (65, 142, 74))
        for a in range(16):
            c.ellipse(128 + math.cos(a * math.tau / 16) * 33, 102 + math.sin(a * math.tau / 16) * 33, 18, 8, (240, 198, 50), angle=a)
        c.circle(128, 102, 25, (105, 71, 39))
    elif slug == "bamboo":
        for x in [98, 127, 156]:
            c.rect(x - 6, 62, x + 6, 198, (69, 149, 74))
            for y in [88, 119, 150, 181]:
                c.line(x - 8, y, x + 8, y, 2, (43, 109, 51))
        c.ellipse(83, 92, 30, 10, (71, 153, 83), angle=-0.45); c.ellipse(170, 125, 30, 10, (71, 153, 83), angle=0.45)
    elif slug == "cactus":
        c.rect(115, 78, 141, 196, (62, 148, 91)); c.circle(128, 78, 13, (62, 148, 91)); c.line(99, 128, 99, 97, 12, (62, 148, 91)); c.line(99, 128, 116, 128, 12, (62, 148, 91)); c.line(157, 143, 157, 111, 12, (62, 148, 91)); c.line(140, 143, 157, 143, 12, (62, 148, 91))
    elif slug == "pine_tree":
        c.rect(119, 151, 137, 205, (111, 76, 43)); c.polygon([(128, 52), (70, 139), (186, 139)], (49, 112, 66)); c.polygon([(128, 84), (63, 174), (193, 174)], (43, 101, 61))
    elif slug == "lotus":
        c.ellipse(128, 192, 78, 11, (84, 149, 94), 0.6)
        for a in [-0.8, -0.4, 0, 0.4, 0.8]:
            c.ellipse(128 + math.sin(a) * 34, 133 - abs(a) * 8, 18, 43, (229, 122, 166), angle=a)
        c.circle(128, 148, 16, (232, 194, 64))
    elif slug == "maple":
        c.line(128, 196, 128, 132, 5, (111, 76, 43)); c.polygon([(128, 54), (145, 108), (191, 84), (158, 132), (203, 145), (149, 152), (128, 201), (107, 152), (53, 145), (98, 132), (65, 84), (111, 108)], (199, 69, 46))
    elif slug == "tulip":
        c.line(128, 194, 128, 120, 5, (65, 143, 73)); c.ellipse(104, 150, 26, 10, (65, 143, 73), angle=-0.4); c.ellipse(151, 158, 25, 10, (65, 143, 73), angle=0.35); c.polygon([(96, 89), (113, 126), (128, 88), (143, 126), (160, 89), (151, 147), (105, 147)], (215, 72, 126))
    elif slug == "fern":
        c.line(128, 199, 128, 62, 4, (55, 130, 70))
        for y in range(78, 185, 16):
            offset = (y - 78) / 4
            c.line(128, y, 88 - offset / 3, y + 18, 3, (70, 153, 83)); c.line(128, y, 168 + offset / 3, y + 18, 3, (70, 153, 83))
    elif slug == "rice":
        for x in [105, 121, 137, 153]:
            c.line(x, 200, x - 16, 82, 4, (82, 146, 73))
            for y in [88, 106, 124, 142]:
                c.ellipse(x - 16, y, 7, 13, (219, 178, 74), angle=-0.35)
    return c.pixels


def tool_icon(slug: str) -> list[Color]:
    c = Canvas()
    metal = (110, 124, 132)
    if slug == "hammer":
        c.line(91, 197, 155, 100, 10, (128, 82, 48)); c.rect(111, 76, 188, 101, metal)
    elif slug == "wrench":
        c.line(89, 190, 167, 112, 10, metal); c.circle(176, 99, 26, metal); c.circle(188, 90, 18, (248, 249, 246)); c.circle(83, 196, 15, metal)
    elif slug == "screwdriver":
        c.line(79, 190, 164, 105, 8, (196, 59, 48)); c.line(155, 96, 192, 59, 5, metal); c.polygon([(190, 57), (207, 41), (201, 66)], metal)
    elif slug == "pliers":
        c.line(96, 194, 128, 133, 8, (204, 71, 56)); c.line(160, 194, 128, 133, 8, (204, 71, 56)); c.ellipse(114, 104, 16, 40, metal, angle=-0.35); c.ellipse(142, 104, 16, 40, metal, angle=0.35); c.circle(128, 134, 8, (54, 61, 64))
    elif slug == "scissors":
        c.circle(92, 179, 18, metal); c.circle(164, 179, 18, metal); c.line(101, 168, 178, 84, 5, metal); c.line(155, 168, 78, 84, 5, metal); c.circle(128, 144, 7, (54, 61, 64))
    elif slug == "tape_measure":
        c.rect(76, 104, 171, 179, (237, 192, 51)); c.circle(123, 142, 30, (231, 173, 42)); c.line(171, 139, 219, 139, 7, metal); c.rect(213, 131, 228, 147, metal)
    elif slug == "drill":
        c.rect(76, 94, 164, 137, (67, 123, 188)); c.rect(96, 137, 132, 197, (67, 123, 188)); c.polygon([(164, 104), (215, 116), (164, 128)], metal); c.rect(133, 137, 160, 158, (45, 84, 131))
    elif slug == "brush":
        c.line(86, 190, 145, 123, 9, (121, 77, 43)); c.rect(140, 91, 184, 129, metal); c.rect(145, 55, 179, 91, (82, 139, 194))
    elif slug == "shovel":
        c.line(128, 73, 128, 167, 7, (121, 77, 43)); c.polygon([(92, 160), (164, 160), (146, 214), (110, 214)], metal); c.circle(128, 61, 18, (121, 77, 43)); c.circle(128, 61, 10, (248, 249, 246))
    elif slug == "flashlight":
        c.polygon([(78, 137), (159, 111), (174, 151), (93, 178)], (65, 72, 78)); c.polygon([(159, 111), (206, 96), (221, 137), (174, 151)], (222, 190, 82)); c.polygon([(206, 96), (246, 77), (229, 160), (221, 137)], (245, 228, 126), 0.55)
    return c.pixels


def food_icon(slug: str) -> list[Color]:
    c = Canvas()
    if slug == "bread":
        c.ellipse(128, 136, 70, 55, (206, 144, 75)); c.rect(61, 130, 195, 183, (210, 151, 82)); c.ellipse(102, 116, 22, 28, (230, 181, 106), 0.5)
    elif slug == "pizza":
        c.polygon([(128, 61), (57, 191), (199, 191)], (234, 178, 74)); c.polygon([(128, 76), (74, 181), (182, 181)], (220, 86, 55)); c.circle(107, 139, 9, (170, 54, 45)); c.circle(145, 159, 9, (170, 54, 45)); c.line(57, 191, 199, 191, 7, (212, 145, 72))
    elif slug == "sushi":
        for x in [82, 128, 174]:
            c.ellipse(x, 139, 32, 25, (42, 45, 43)); c.ellipse(x, 139, 24, 17, (242, 241, 232)); c.circle(x, 139, 10, (214, 83, 70))
    elif slug == "dumpling":
        for x in [86, 128, 170]:
            c.ellipse(x, 152, 39, 28, (237, 226, 190)); c.line(x - 24, 142, x + 24, 142, 2, (196, 179, 140))
    elif slug == "burger":
        c.ellipse(128, 111, 72, 26, (213, 151, 74)); c.rect(61, 120, 195, 139, (78, 136, 70)); c.rect(66, 139, 190, 158, (103, 64, 38)); c.rect(65, 158, 191, 175, (232, 196, 61)); c.ellipse(128, 185, 70, 15, (213, 151, 74))
    elif slug == "salad":
        c.ellipse(128, 162, 79, 40, (227, 229, 220)); c.ellipse(128, 145, 68, 28, (71, 149, 73)); c.circle(103, 137, 11, (218, 68, 55)); c.circle(151, 146, 10, (238, 204, 66)); c.circle(132, 129, 12, (91, 171, 79))
    elif slug == "noodles":
        c.ellipse(128, 166, 76, 38, (224, 226, 218)); c.ellipse(128, 151, 62, 25, (224, 182, 84)); c.line(91, 146, 166, 153, 3, (185, 125, 48)); c.line(95, 158, 170, 145, 3, (185, 125, 48)); c.line(70, 101, 181, 129, 3, (96, 77, 45))
    elif slug == "cake":
        c.rect(72, 114, 184, 183, (238, 190, 194)); c.rect(72, 114, 184, 132, (246, 239, 229)); c.rect(94, 84, 103, 114, (238, 204, 67)); c.rect(126, 78, 135, 114, (238, 204, 67)); c.rect(158, 84, 167, 114, (238, 204, 67)); c.circle(98, 80, 5, (227, 92, 57)); c.circle(130, 74, 5, (227, 92, 57)); c.circle(162, 80, 5, (227, 92, 57))
    elif slug == "rice":
        c.ellipse(128, 166, 76, 36, (222, 224, 218)); c.ellipse(128, 139, 58, 33, (244, 244, 236)); c.circle(104, 133, 6, (232, 232, 223)); c.circle(139, 126, 5, (232, 232, 223))
    elif slug == "soup":
        c.ellipse(128, 161, 76, 37, (224, 226, 218)); c.ellipse(128, 144, 62, 24, (210, 92, 55)); c.circle(108, 140, 6, (244, 205, 80)); c.circle(150, 147, 6, (82, 151, 80)); c.line(74, 190, 182, 190, 3, (196, 198, 191))
    return c.pixels


def landmark_icon(slug: str) -> list[Color]:
    c = Canvas()
    stone = (151, 132, 105)
    if slug == "great_wall":
        for i in range(5):
            x = 45 + i * 35
            c.rect(x, 130 - i * 7, x + 42, 160 - i * 7, stone)
            c.rect(x + 4, 122 - i * 7, x + 12, 130 - i * 7, stone)
        c.line(42, 178, 214, 145, 4, (90, 98, 70))
    elif slug == "eiffel_tower":
        c.line(92, 198, 128, 55, 5, (83, 88, 95)); c.line(164, 198, 128, 55, 5, (83, 88, 95)); c.line(83, 153, 173, 153, 4, (83, 88, 95)); c.line(101, 105, 155, 105, 3, (83, 88, 95)); c.line(96, 198, 160, 198, 5, (83, 88, 95))
    elif slug == "pyramid":
        c.polygon([(128, 58), (48, 190), (208, 190)], (204, 172, 99)); c.polygon([(128, 58), (208, 190), (142, 190)], (177, 139, 78)); c.line(76, 145, 183, 145, 2, (157, 126, 74))
    elif slug == "statue_of_liberty":
        c.rect(109, 145, 147, 204, (86, 154, 139)); c.circle(128, 95, 25, (91, 168, 152)); c.polygon([(128, 50), (116, 85), (140, 85)], (91, 168, 152)); c.line(157, 132, 198, 65, 5, (91, 168, 152)); c.circle(200, 60, 10, (237, 202, 75))
    elif slug == "taj_mahal":
        c.rect(67, 126, 189, 192, (229, 224, 207)); c.circle(128, 116, 40, (229, 224, 207)); c.rect(52, 103, 65, 198, (229, 224, 207)); c.rect(191, 103, 204, 198, (229, 224, 207)); c.polygon([(128, 55), (114, 97), (142, 97)], (229, 224, 207))
    elif slug == "sydney_opera":
        c.polygon([(62, 181), (111, 82), (122, 181)], (231, 232, 222)); c.polygon([(101, 181), (152, 70), (164, 181)], (231, 232, 222)); c.polygon([(142, 181), (196, 98), (206, 181)], (231, 232, 222)); c.line(52, 185, 214, 185, 5, (93, 139, 170))
    elif slug == "forbidden_city":
        c.rect(56, 136, 200, 190, (170, 64, 46)); c.polygon([(45, 136), (211, 136), (188, 106), (68, 106)], (198, 146, 55)); c.polygon([(74, 106), (182, 106), (164, 82), (92, 82)], (198, 146, 55)); c.rect(117, 153, 139, 190, (94, 55, 37))
    elif slug == "colosseum":
        c.ellipse(128, 140, 82, 55, (173, 143, 101)); c.rect(49, 140, 207, 188, (173, 143, 101))
        for x in [72, 102, 132, 162]:
            c.ellipse(x, 158, 10, 22, (88, 75, 62))
    elif slug == "tower_bridge":
        c.rect(68, 91, 95, 190, (150, 136, 114)); c.rect(161, 91, 188, 190, (150, 136, 114)); c.polygon([(62, 91), (101, 91), (82, 62)], (150, 136, 114)); c.polygon([(155, 91), (194, 91), (176, 62)], (150, 136, 114)); c.line(82, 122, 176, 122, 4, (81, 113, 151)); c.line(82, 159, 176, 159, 4, (81, 113, 151))
    elif slug == "mount_fuji":
        c.polygon([(128, 59), (45, 193), (211, 193)], (72, 110, 148)); c.polygon([(128, 59), (101, 103), (155, 103)], (239, 239, 231)); c.line(45, 194, 211, 194, 4, (83, 137, 94))
    return c.pixels


Dataset = dict[str, object]


DATASETS: list[Dataset] = [
    {
        "name": "synthetic-vehicles-multimodal-v1",
        "title": "多交通工具图片召回评测",
        "gallery": "vehicles-gallery",
        "image_dir": "vehicles",
        "intro": "本文档用于评测系统能否根据交通工具名称、用途、形状和局部结构召回对应图片资产。",
        "drawer": vehicle_icon,
        "items": [
            ("car", "汽车", "Car", "汽车通常有车身、车窗和四个车轮，是道路交通中最常见的私人交通工具。", "检索蓝色汽车、车窗和两个可见车轮。"),
            ("bus", "公交车", "Bus", "公交车车身较长，车窗成排排列，用于城市公共交通。", "Find the yellow bus with long body and windows."),
            ("train", "火车", "Train", "火车在轨道上运行，常由多节车厢组成，适合测试轨道和车厢特征。", "检索蓝色火车和轨道。"),
            ("airplane", "飞机", "Airplane", "飞机具有细长机身、机翼和尾翼，常用于空中交通图像检索。", "Find the airplane with wings and fuselage."),
            ("ship", "轮船", "Ship", "轮船有船体、甲板和烟囱，适合测试水上交通工具召回。", "检索有船体和烟囱的轮船。"),
            ("bicycle", "自行车", "Bicycle", "自行车有两个大轮、车架和把手，依靠人力驱动。", "Find the bicycle with two wheels and frame."),
            ("motorcycle", "摩托车", "Motorcycle", "摩托车有两个车轮、发动机区域和把手，外形比自行车更厚重。", "检索摩托车图片。"),
            ("ambulance", "救护车", "Ambulance", "救护车通常有白色车身和红色医疗十字标识，用于急救运输。", "Find the ambulance with red medical cross."),
            ("fire_truck", "消防车", "Fire Truck", "消防车多为红色，常带有梯子和大型车身，用于消防救援。", "检索红色消防车和梯子。"),
            ("subway", "地铁", "Subway", "地铁列车有正面车窗、车灯和轨道，常用于城市轨道交通。", "Find the subway train front with tracks."),
        ],
    },
    {
        "name": "synthetic-plants-multimodal-v1",
        "title": "多植物图片召回评测",
        "gallery": "plants-gallery",
        "image_dir": "plants",
        "intro": "本文档用于评测系统能否根据植物名称、花色、叶形、茎干和生态特征召回对应图片资产。",
        "drawer": plant_icon,
        "items": [
            ("rose", "玫瑰", "Rose", "玫瑰有层叠花瓣、绿色茎和叶，常见为红色花朵。", "检索红色玫瑰和绿色茎叶。"),
            ("sunflower", "向日葵", "Sunflower", "向日葵有黄色放射状花瓣和棕色花盘，视觉中心突出。", "Find the sunflower with yellow petals."),
            ("bamboo", "竹子", "Bamboo", "竹子由绿色分节茎秆和细长叶片构成，适合测试重复结构。", "检索分节绿色竹子。"),
            ("cactus", "仙人掌", "Cactus", "仙人掌有厚实绿色茎和侧枝，常见于干旱环境。", "Find the cactus with arms."),
            ("pine_tree", "松树", "Pine Tree", "松树有针叶状树冠和棕色树干，轮廓呈层叠三角形。", "检索三角形树冠的松树。"),
            ("lotus", "荷花", "Lotus", "荷花有粉色花瓣和宽大浮叶，常出现在水面环境。", "Find the pink lotus flower."),
            ("maple", "枫树", "Maple", "枫叶常呈掌状分裂，秋季红色或橙色特征明显。", "检索红色枫叶。"),
            ("tulip", "郁金香", "Tulip", "郁金香有杯状花冠、直立花茎和宽叶，色彩鲜明。", "Find the tulip with cup-shaped petals."),
            ("fern", "蕨类", "Fern", "蕨类植物有羽状复叶，叶片沿主轴成对展开。", "检索羽状蕨类叶片。"),
            ("rice", "稻谷", "Rice", "成熟稻穗由细长茎和金黄色谷粒组成，是农作物图像的重要样本。", "Find the golden rice panicles."),
        ],
    },
    {
        "name": "synthetic-tools-multimodal-v1",
        "title": "多工具图片召回评测",
        "gallery": "tools-gallery",
        "image_dir": "tools",
        "intro": "本文档用于评测系统能否根据工具名称、用途、手柄、金属部件和局部结构召回对应图片资产。",
        "drawer": tool_icon,
        "items": [
            ("hammer", "锤子", "Hammer", "锤子由金属锤头和长柄组成，用于敲击钉子或物体。", "检索锤子、金属锤头和木柄。"),
            ("wrench", "扳手", "Wrench", "扳手有开口或环形夹持端，用于拧动螺母和螺栓。", "Find the wrench with open jaw."),
            ("screwdriver", "螺丝刀", "Screwdriver", "螺丝刀有手柄、长杆和尖端，用于拧紧或拆卸螺丝。", "检索螺丝刀和尖端。"),
            ("pliers", "钳子", "Pliers", "钳子有两个手柄和夹持钳口，可用于夹紧或弯折材料。", "Find the pliers with two handles."),
            ("scissors", "剪刀", "Scissors", "剪刀有两个圆形握环和交叉刀刃，用于裁剪材料。", "检索交叉刀刃剪刀。"),
            ("tape_measure", "卷尺", "Tape Measure", "卷尺有黄色外壳和伸出的金属尺带，常用于测量长度。", "Find the tape measure with metal tape."),
            ("drill", "电钻", "Drill", "电钻有机身、手柄和钻头，是典型电动工具。", "检索电钻和钻头。"),
            ("brush", "刷子", "Brush", "刷子由刷毛、金属箍和手柄组成，用于涂刷或清洁。", "Find the brush with bristles."),
            ("shovel", "铲子", "Shovel", "铲子有长柄和宽铲头，常用于挖掘或搬运土壤。", "检索铲子和宽铲头。"),
            ("flashlight", "手电筒", "Flashlight", "手电筒有筒身、发光端和光束，用于照明。", "Find the flashlight beam."),
        ],
    },
    {
        "name": "synthetic-foods-multimodal-v1",
        "title": "多食物图片召回评测",
        "gallery": "foods-gallery",
        "image_dir": "foods",
        "intro": "本文档用于评测系统能否根据食物名称、形状、颜色、配料和容器线索召回对应图片资产。",
        "drawer": food_icon,
        "items": [
            ("bread", "面包", "Bread", "面包通常呈金棕色，有柔软内部和烘烤外皮。", "检索金棕色面包。"),
            ("pizza", "披萨", "Pizza", "披萨切片有三角形轮廓、奶酪、酱料和配料。", "Find the triangular pizza slice."),
            ("sushi", "寿司", "Sushi", "寿司常由海苔、米饭和鱼肉或馅料组成，形状小而规整。", "检索寿司卷。"),
            ("dumpling", "饺子", "Dumpling", "饺子有半月形面皮和褶边，是常见中式食物。", "Find the dumplings with folded edges."),
            ("burger", "汉堡", "Burger", "汉堡由面包、蔬菜、肉饼和奶酪分层组成。", "检索分层汉堡。"),
            ("salad", "沙拉", "Salad", "沙拉包含绿色蔬菜和多种彩色配料，常放在碗中。", "Find the bowl of salad."),
            ("noodles", "面条", "Noodles", "面条呈长条状，常盛在碗中并伴随酱汁或汤底。", "检索碗中的面条。"),
            ("cake", "蛋糕", "Cake", "蛋糕通常有奶油层和蜡烛，适合测试甜点类召回。", "Find the birthday cake with candles."),
            ("rice", "米饭", "Rice", "米饭由白色米粒组成，常盛在碗里，是主食样本。", "检索白米饭。"),
            ("soup", "汤", "Soup", "汤一般盛在碗中，液体表面可见配料和颜色。", "Find the bowl of soup."),
        ],
    },
    {
        "name": "synthetic-landmarks-multimodal-v1",
        "title": "多地标图片召回评测",
        "gallery": "landmarks-gallery",
        "image_dir": "landmarks",
        "intro": "本文档用于评测系统能否根据建筑名称、地域文化、形状和标志性结构召回对应图片资产。",
        "drawer": landmark_icon,
        "items": [
            ("great_wall", "长城", "Great Wall", "长城由连续城墙和垛口构成，沿山脊蜿蜒延伸。", "检索蜿蜒城墙和垛口。"),
            ("eiffel_tower", "埃菲尔铁塔", "Eiffel Tower", "埃菲尔铁塔有高耸金属桁架结构和宽阔塔脚。", "Find the Eiffel Tower lattice silhouette."),
            ("pyramid", "金字塔", "Pyramid", "金字塔有巨大的三角形侧面和沙色石材外观。", "检索沙色金字塔。"),
            ("statue_of_liberty", "自由女神像", "Statue of Liberty", "自由女神像有绿色铜像、冠冕和高举火炬的姿态。", "Find the Statue of Liberty with torch."),
            ("taj_mahal", "泰姬陵", "Taj Mahal", "泰姬陵以白色穹顶、对称塔楼和纪念性正立面著称。", "检索白色穹顶泰姬陵。"),
            ("sydney_opera", "悉尼歌剧院", "Sydney Opera House", "悉尼歌剧院有帆形屋顶和海港边界特征。", "Find the sail-shaped opera house."),
            ("forbidden_city", "故宫", "Forbidden City", "故宫有红墙、黄色屋顶和中轴对称宫殿结构。", "检索红墙黄瓦故宫。"),
            ("colosseum", "罗马斗兽场", "Colosseum", "罗马斗兽场有椭圆形外墙和连续拱门。", "Find the Colosseum arches."),
            ("tower_bridge", "伦敦塔桥", "Tower Bridge", "伦敦塔桥有两座塔楼和跨河桥面，是伦敦标志性建筑。", "检索双塔桥梁。"),
            ("mount_fuji", "富士山", "Mount Fuji", "富士山有对称山体和雪冠，是日本自然地标。", "Find Mount Fuji with snow cap."),
        ],
    },
]


def write_dataset(dataset: Dataset) -> None:
    name = str(dataset["name"])
    title = str(dataset["title"])
    gallery = str(dataset["gallery"])
    image_dir_name = str(dataset["image_dir"])
    intro = str(dataset["intro"])
    drawer = dataset["drawer"]
    items = dataset["items"]
    assert callable(drawer)

    dataset_dir = ROOT / "datasets" / name
    corpus_dir = dataset_dir / "corpus"
    image_dir = corpus_dir / "images" / image_dir_name
    image_dir.mkdir(parents=True, exist_ok=True)

    for slug, *_ in items:  # type: ignore[assignment]
        write_png(image_dir / f"{slug}.png", drawer(slug))  # type: ignore[misc]

    md = [
        "---",
        f"title: {title}",
        "language: zh-CN",
        "source: local-synthetic",
        "modality: image-text",
        f"version: {name}",
        "---",
        "",
        f"# {title}",
        "",
        intro,
        "",
    ]
    query_lines = ["queries:"]
    for slug, zh, en, desc, query in items:  # type: ignore[misc]
        md.extend(
            [
                f"## {zh} / {en}",
                "",
                f"![{zh}图片 - {en}](./images/{image_dir_name}/{slug}.png)",
                "",
                desc,
                "",
                f"检索提示：{zh}、{en}、图片、颜色、形状、局部特征。",
                "",
            ]
        )
        query_lines.extend([f"  - id: {image_dir_name}_{slug}", f"    q: {query}", f"    expect_any: [{gallery}]"])

    (corpus_dir / f"{gallery}.md").write_text("\n".join(md), encoding="utf-8")
    (dataset_dir / "queries.yaml").write_text("\n".join(query_lines) + "\n", encoding="utf-8")
    (dataset_dir / "dataset.yaml").write_text(
        "\n".join(
            [
                f"name: {name}",
                "description: >",
                f"  One-document multimodal retrieval fixture for {image_dir_name} with local PNG",
                "  images referenced from Markdown. It is intended to verify image asset",
                "  parsing, multimodal embedding, and text-to-image recall behavior.",
                "thresholds:",
                "  hit_at_3: 1.0",
                "  hit_at_10: 1.0",
                "  mrr: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    for dataset in DATASETS:
        write_dataset(dataset)
        print(f"wrote {dataset['name']}")


if __name__ == "__main__":
    main()

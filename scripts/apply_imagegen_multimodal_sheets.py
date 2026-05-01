from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DATASET = "synthetic-multimodal-datasets-v1"
SHEET_DIR = Path.home() / ".codex" / "generated_images" / "019dca28-eaa6-77f0-8a22-0e9235befec2"


@dataclass(frozen=True)
class SheetSpec:
    image_dir: str
    sheet_name: str
    slugs: tuple[str, ...]


SHEETS = [
    SheetSpec(
        image_dir="fruits",
        sheet_name="ig_017498eff26b4d770169f220e5dd7c81918526bea4afdb7e63.png",
        slugs=("apple", "banana", "orange", "strawberry", "grape", "watermelon", "pineapple", "kiwi", "mango", "lemon"),
    ),
    SheetSpec(
        image_dir="animals",
        sheet_name="ig_017498eff26b4d770169f22142d264819198891c68b941f451.png",
        slugs=("cat", "dog", "rabbit", "panda", "elephant", "lion", "penguin", "owl", "fox", "turtle"),
    ),
    SheetSpec(
        image_dir="plants",
        sheet_name="ig_017498eff26b4d770169f22183055081918fbc0ecc0d776f52.png",
        slugs=("rose", "sunflower", "bamboo", "cactus", "pine_tree", "lotus", "maple", "tulip", "fern", "rice"),
    ),
    SheetSpec(
        image_dir="tools",
        sheet_name="ig_017498eff26b4d770169f221c0cdc881918e26310d10051c66.png",
        slugs=("hammer", "wrench", "screwdriver", "pliers", "scissors", "tape_measure", "drill", "brush", "shovel", "flashlight"),
    ),
    SheetSpec(
        image_dir="foods",
        sheet_name="ig_017498eff26b4d770169f2220715a8819181cc2158b7b0e461.png",
        slugs=("bread", "pizza", "sushi", "dumpling", "burger", "salad", "noodles", "cake", "rice", "soup"),
    ),
    SheetSpec(
        image_dir="vehicles",
        sheet_name="ig_017498eff26b4d770169f2223f42b481918cb77f42c793b2fa.png",
        slugs=("car", "bus", "train", "airplane", "ship", "bicycle", "motorcycle", "ambulance", "fire_truck", "subway"),
    ),
    SheetSpec(
        image_dir="landmarks",
        sheet_name="ig_017498eff26b4d770169f2228a20288191b590193058f1af98.png",
        slugs=("great_wall", "eiffel_tower", "pyramid", "statue_of_liberty", "taj_mahal", "sydney_opera", "forbidden_city", "colosseum", "tower_bridge", "mount_fuji"),
    ),
]


def square_pad(image: Image.Image) -> Image.Image:
    width, height = image.size
    side = max(width, height)
    out = Image.new("RGB", (side, side), "white")
    out.paste(image.convert("RGB"), ((side - width) // 2, (side - height) // 2))
    return out


def crop_sheet(spec: SheetSpec) -> None:
    sheet_path = SHEET_DIR / spec.sheet_name
    if not sheet_path.is_file():
        raise FileNotFoundError(sheet_path)

    out_dir = ROOT / "datasets" / DATASET / "corpus" / "images" / spec.image_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(sheet_path) as sheet:
        width, height = sheet.size
        cell_w = width / 5
        cell_h = height / 2
        for index, slug in enumerate(spec.slugs):
            col = index % 5
            row = index // 5
            left = round(col * cell_w)
            upper = round(row * cell_h)
            right = round((col + 1) * cell_w)
            lower = round((row + 1) * cell_h)
            crop = sheet.crop((left, upper, right, lower))
            final = square_pad(crop).resize((512, 512), Image.Resampling.LANCZOS)
            final.save(out_dir / f"{slug}.png", optimize=True)


def main() -> None:
    for spec in SHEETS:
        crop_sheet(spec)
        print(f"applied {DATASET}/{spec.image_dir}")


if __name__ == "__main__":
    main()

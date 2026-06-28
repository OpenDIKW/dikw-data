from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DATASET = "synthetic-multimodal-datasets-v1"
DATASET_DIR = ROOT / "datasets" / DATASET
CORPUS_DIR = DATASET_DIR / "corpus"


@dataclass(frozen=True)
class Group:
    doc: str
    slug: str
    zh: str
    en: str
    assets: tuple[str, ...]
    image_paths: tuple[str, ...]
    summary: str
    detail: str
    chunk_query: str
    asset_query: str

    @property
    def anchor(self) -> str:
        return f"groups.{self.slug}"

    @property
    def chunk_id(self) -> str:
        return f"{self.anchor}.text"

    @property
    def heading(self) -> str:
        return f"{self.zh} / {self.en}"


DOC_TITLES = {
    "visual-comparisons": "多图视觉对比评测",
    "functional-sets": "多图功能组合评测",
    "scene-object-groups": "多图场景对象组合评测",
}


GROUPS: tuple[Group, ...] = (
    Group("visual-comparisons", "citrus_comparison", "柑橘色水果对比", "Citrus Color Comparison", ("fruits.orange.image", "fruits.lemon.image", "fruits.mango.image"), ("images/fruits/orange.png", "images/fruits/lemon.png", "images/fruits/mango.png"), "这一组比较橙色或黄色水果的相近外观。", "橙子偏圆且表皮橙色，柠檬更偏椭圆并带尖端，芒果通常呈黄橙色椭圆并可能带红绿色过渡。", "哪个小节同时比较了橙子、柠檬和芒果的颜色与形状差异？", "检索这组用于比较橙子、柠檬和芒果外观差异的图片。"),
    Group("visual-comparisons", "pet_face_comparison", "宠物面部对比", "Pet Face Comparison", ("animals.cat.image", "animals.dog.image", "animals.fox.image"), ("images/animals/cat.png", "images/animals/dog.png", "images/animals/fox.png"), "这一组比较常见犬猫类动物的面部线索。", "猫突出三角耳和胡须，狗常见下垂耳和短吻部，狐狸以橙红毛色、尖耳和白色面部区域区分。", "哪个小节比较猫、狗和狐狸的耳朵、吻部和面部颜色？", "检索猫、狗和狐狸三张面部特征对比图片。"),
    Group("visual-comparisons", "urban_transit_comparison", "城市交通工具对比", "Urban Transit Comparison", ("vehicles.bus.image", "vehicles.train.image", "vehicles.subway.image"), ("images/vehicles/bus.png", "images/vehicles/train.png", "images/vehicles/subway.png"), "这一组比较城市公共交通和轨道交通图像。", "公交车有长车身和成排车窗，火车强调车厢与轨道延展，地铁更突出城市轨道列车的正面和轨道环境。", "哪个小节同时介绍公交车、火车和地铁的视觉区别？", "检索公交车、火车和地铁组成的城市交通对比图片组。"),
    Group("visual-comparisons", "round_sports_balls", "圆形运动球对比", "Round Sports Ball Comparison", ("sports.soccer_ball.image", "sports.basketball.image", "foods.rice.image"), ("images/sports/soccer_ball.png", "images/sports/basketball.png", "images/foods/rice.png"), "这一组用圆形或颗粒视觉元素构造细粒度区分。", "足球和篮球都是球体，但足球有拼块纹理，篮球有橙色表面和黑色弧线；米饭则是碗中小颗粒聚集，并非运动球。", "哪个小节把足球、篮球和米饭放在一起说明圆形目标与颗粒目标的差异？", "检索足球、篮球和米饭这组三类圆形或颗粒视觉目标。"),
    Group("visual-comparisons", "keyboard_input_devices", "键盘与输入设备对比", "Keyboard and Input Device Comparison", ("electronics.laptop.image", "office.calculator.image", "instruments.piano.image"), ("images/electronics/laptop.png", "images/office/calculator.png", "images/instruments/piano.png"), "这一组比较具有重复按键结构的对象。", "笔记本电脑结合屏幕和键盘，计算器有数字按键和小屏幕，钢琴键盘以黑白琴键形成长条重复结构。", "哪个小节比较笔记本电脑、计算器和钢琴键盘的按键结构？", "检索笔记本电脑、计算器和钢琴键盘三张按键结构图片。"),
    Group("visual-comparisons", "protective_wear_comparison", "防护穿戴物对比", "Protective Wear Comparison", ("medical.face_mask.image", "sports.bicycle_helmet.image", "clothing.umbrella.image"), ("images/medical/face_mask.png", "images/sports/bicycle_helmet.png", "images/clothing/umbrella.png"), "这一组比较不同防护用品的形态。", "口罩覆盖口鼻并带耳带，自行车头盔覆盖头部并有通风孔，雨伞通过展开伞面遮挡雨水或阳光。", "哪个小节对比口罩、骑行头盔和雨伞的防护方式？", "检索口罩、自行车头盔和雨伞组成的防护用品图片组。"),
    Group("visual-comparisons", "long_handheld_tools", "长柄手持工具对比", "Long Handheld Tool Comparison", ("tools.hammer.image", "tools.screwdriver.image", "tools.shovel.image"), ("images/tools/hammer.png", "images/tools/screwdriver.png", "images/tools/shovel.png"), "这一组比较长柄或细长手持工具。", "锤子由锤头和柄组成，螺丝刀有手柄和金属杆，铲子则由长柄和宽铲头形成更长的纵向轮廓。", "哪个小节比较锤子、螺丝刀和铲子的长柄结构？", "检索锤子、螺丝刀和铲子这组三种手持工具图片。"),
    Group("visual-comparisons", "flower_shape_comparison", "花卉形态对比", "Flower Shape Comparison", ("plants.rose.image", "plants.sunflower.image", "plants.tulip.image"), ("images/plants/rose.png", "images/plants/sunflower.png", "images/plants/tulip.png"), "这一组比较三种花卉的花冠形态。", "玫瑰有层叠花瓣，向日葵具有放射状黄色花瓣和圆形花盘，郁金香的杯状花冠和直立花茎更明显。", "哪个小节比较玫瑰、向日葵和郁金香的花形差异？", "检索玫瑰、向日葵和郁金香三张花卉对比图片。"),
    Group("visual-comparisons", "string_instrument_comparison", "弦乐器外观对比", "String Instrument Comparison", ("instruments.guitar.image", "instruments.violin.image", "instruments.cello.image"), ("images/instruments/guitar.png", "images/instruments/violin.png", "images/instruments/cello.png"), "这一组比较弦乐器的尺寸与结构。", "吉他有共鸣箱和音孔，小提琴较小并常与琴弓配合，大提琴更大且竖直演奏，三者都以琴弦和木质琴身为核心。", "哪个小节比较吉他、小提琴和大提琴的尺寸和弦乐结构？", "检索吉他、小提琴和大提琴组成的弦乐器图片组。"),
    Group("visual-comparisons", "famous_architecture_shapes", "地标建筑轮廓对比", "Famous Architecture Shape Comparison", ("landmarks.eiffel_tower.image", "landmarks.pyramid.image", "landmarks.sydney_opera.image"), ("images/landmarks/eiffel_tower.png", "images/landmarks/pyramid.png", "images/landmarks/sydney_opera.png"), "这一组比较地标建筑的几何轮廓。", "埃菲尔铁塔是高耸金属桁架，金字塔是沙色三角体，悉尼歌剧院以白色帆形屋顶形成现代轮廓。", "哪个小节比较埃菲尔铁塔、金字塔和悉尼歌剧院的建筑轮廓？", "检索埃菲尔铁塔、金字塔和悉尼歌剧院三张地标轮廓图片。"),
    Group("functional-sets", "first_aid_set", "急救用品组合", "First Aid Set", ("medical.first_aid_kit.image", "medical.bandage.image", "medical.thermometer.image", "medical.face_mask.image"), ("images/medical/first_aid_kit.png", "images/medical/bandage.png", "images/medical/thermometer.png", "images/medical/face_mask.png"), "这一组表达家庭或现场急救中的常见物品组合。", "急救箱用于集中收纳，绷带用于包扎，体温计用于测温，口罩用于基础防护，四者共同构成应急医疗场景。", "哪个小节描述了急救箱、绷带、体温计和口罩组成的急救组合？", "检索急救箱、绷带、体温计和口罩四张急救用品图片。"),
    Group("functional-sets", "office_desk_set", "办公桌文具组合", "Office Desk Set", ("office.notebook.image", "office.fountain_pen.image", "office.sticky_notes.image", "office.calculator.image"), ("images/office/notebook.png", "images/office/fountain_pen.png", "images/office/sticky_notes.png", "images/office/calculator.png"), "这一组表达办公桌上的记录、提醒和计算工具。", "笔记本承载长文本记录，钢笔用于书写，便签记录短提醒，计算器处理数字统计，组合语义指向办公任务。", "哪个小节介绍笔记本、钢笔、便签和计算器的办公组合？", "检索笔记本、钢笔、便签和计算器四张办公用品图片。"),
    Group("functional-sets", "kitchen_appliance_set", "厨房电器组合", "Kitchen Appliance Set", ("household.refrigerator.image", "household.microwave.image", "household.electric_kettle.image"), ("images/household/refrigerator.png", "images/household/microwave.png", "images/household/electric_kettle.png"), "这一组表达厨房中保存、加热和烧水的电器组合。", "冰箱用于低温保存，微波炉用于快速加热，电水壶用于烧水，三者覆盖厨房常见食物处理流程。", "哪个小节说明冰箱、微波炉和电水壶在厨房中的功能组合？", "检索冰箱、微波炉和电水壶三张厨房电器图片。"),
    Group("functional-sets", "workout_training_set", "健身训练组合", "Workout Training Set", ("sports.dumbbell.image", "sports.yoga_mat.image", "sports.boxing_gloves.image", "sports.swimming_goggles.image"), ("images/sports/dumbbell.png", "images/sports/yoga_mat.png", "images/sports/boxing_gloves.png", "images/sports/swimming_goggles.png"), "这一组表达不同运动训练方式的器材组合。", "哑铃用于力量训练，瑜伽垫用于拉伸和地面训练，拳击手套用于击打保护，游泳镜用于水中视野保护。", "哪个小节把哑铃、瑜伽垫、拳击手套和游泳镜归为训练器材组合？", "检索哑铃、瑜伽垫、拳击手套和游泳镜四张运动器材图片。"),
    Group("functional-sets", "recording_streaming_set", "录音直播设备组合", "Recording and Streaming Set", ("electronics.microphone.image", "electronics.camera.image", "electronics.headphones.image"), ("images/electronics/microphone.png", "images/electronics/camera.png", "images/electronics/headphones.png"), "这一组表达录音、拍摄和监听的创作设备组合。", "麦克风负责语音输入，相机负责影像采集，耳机用于监听音频，三者共同构成直播或录制工作流。", "哪个小节描述麦克风、相机和耳机组成的录音直播设备？", "检索麦克风、相机和耳机三张创作设备图片。"),
    Group("functional-sets", "travel_carry_set", "出行携带组合", "Travel Carry Set", ("clothing.backpack.image", "clothing.running_shoe.image", "clothing.hat.image", "clothing.umbrella.image"), ("images/clothing/backpack.png", "images/clothing/running_shoe.png", "images/clothing/hat.png", "images/clothing/umbrella.png"), "这一组表达日常出行中收纳、步行和天气防护。", "背包用于携带物品，运动鞋适合步行，帽子可遮阳，雨伞应对降雨或强光，组合语义指向户外出行。", "哪个小节介绍背包、运动鞋、帽子和雨伞的出行组合？", "检索背包、运动鞋、帽子和雨伞四张出行用品图片。"),
    Group("functional-sets", "home_cleaning_set", "家庭清洁组合", "Home Cleaning Set", ("household.vacuum_cleaner.image", "tools.brush.image", "tools.shovel.image"), ("images/household/vacuum_cleaner.png", "images/tools/brush.png", "images/tools/shovel.png"), "这一组表达家庭或庭院清洁中的工具组合。", "吸尘器清理地面和缝隙，刷子用于涂刷或表面清理，铲子可搬运或清理材料，三者覆盖不同清洁尺度。", "哪个小节说明吸尘器、刷子和铲子组成的清洁工具组合？", "检索吸尘器、刷子和铲子三张清洁工具图片。"),
    Group("functional-sets", "music_band_set", "乐队演奏组合", "Music Band Set", ("instruments.guitar.image", "instruments.drum_kit.image", "instruments.trumpet.image", "instruments.saxophone.image"), ("images/instruments/guitar.png", "images/instruments/drum_kit.png", "images/instruments/trumpet.png", "images/instruments/saxophone.png"), "这一组表达小型乐队的弦乐、节奏和管乐组合。", "吉他提供和声与旋律，架子鼓负责节奏，小号和萨克斯提供铜管或簧片音色，适合测试多乐器语义聚合。", "哪个小节描述吉他、架子鼓、小号和萨克斯组成的乐队组合？", "检索吉他、架子鼓、小号和萨克斯四张乐器图片。"),
    Group("functional-sets", "repair_tool_set", "维修工具组合", "Repair Tool Set", ("tools.hammer.image", "tools.wrench.image", "tools.screwdriver.image", "tools.drill.image"), ("images/tools/hammer.png", "images/tools/wrench.png", "images/tools/screwdriver.png", "images/tools/drill.png"), "这一组表达装配和维修中常见的工具组合。", "锤子用于敲击，扳手拧动螺母，螺丝刀处理螺丝，电钻用于钻孔或安装，四者共同对应维修任务。", "哪个小节介绍锤子、扳手、螺丝刀和电钻的维修组合？", "检索锤子、扳手、螺丝刀和电钻四张维修工具图片。"),
    Group("functional-sets", "breakfast_food_set", "早餐食物组合", "Breakfast Food Set", ("foods.bread.image", "foods.rice.image", "fruits.banana.image", "fruits.orange.image"), ("images/foods/bread.png", "images/foods/rice.png", "images/fruits/banana.png", "images/fruits/orange.png"), "这一组表达早餐或轻食中的主食与水果组合。", "面包和米饭提供主食语义，香蕉和橙子提供水果语义，组合中既有碳水主食也有鲜食水果。", "哪个小节把面包、米饭、香蕉和橙子作为早餐食物组合介绍？", "检索面包、米饭、香蕉和橙子四张早餐相关图片。"),
    Group("scene-object-groups", "kitchen_scene_appliances", "厨房场景与家电", "Kitchen Scene and Appliances", ("scenes.kitchen.image", "household.refrigerator.image", "household.microwave.image", "household.electric_kettle.image"), ("images/scenes/kitchen.png", "images/household/refrigerator.png", "images/household/microwave.png", "images/household/electric_kettle.png"), "这一组将厨房室内场景和典型厨房电器关联起来。", "厨房图像提供空间背景，冰箱、微波炉和电水壶分别对应保存、加热和烧水功能，适合测试场景与对象联合召回。", "哪个小节把厨房场景与冰箱、微波炉和电水壶关联起来？", "检索厨房、冰箱、微波炉和电水壶组成的场景对象图片组。"),
    Group("scene-object-groups", "library_study_objects", "图书馆与学习用品", "Library and Study Objects", ("scenes.library.image", "office.notebook.image", "office.fountain_pen.image", "office.file_folder.image"), ("images/scenes/library.png", "images/office/notebook.png", "images/office/fountain_pen.png", "images/office/file_folder.png"), "这一组将图书馆室内场景与学习办公用品关联。", "图书馆提供阅读空间背景，笔记本、钢笔和文件夹对应记录、书写和资料整理，组合表达学习研究场景。", "哪个小节把图书馆和笔记本、钢笔、文件夹放在同一学习场景中？", "检索图书馆、笔记本、钢笔和文件夹四张学习场景图片。"),
    Group("scene-object-groups", "rainy_street_protection", "雨天街道与防雨用品", "Rainy Street and Rain Gear", ("scenes.rainy_street.image", "clothing.umbrella.image", "medical.face_mask.image"), ("images/scenes/rainy_street.png", "images/clothing/umbrella.png", "images/medical/face_mask.png"), "这一组将雨天街道与个人防护用品关联。", "雨天街道表现湿润反光路面，雨伞用于遮雨，口罩用于口鼻防护，组合语义覆盖天气和出行防护。", "哪个小节描述雨天街道、雨伞和口罩的出行防护关系？", "检索雨天街道、雨伞和口罩三张防护场景图片。"),
    Group("scene-object-groups", "beach_summer_items", "海滩与夏季物品", "Beach and Summer Items", ("scenes.beach.image", "fruits.watermelon.image", "sports.swimming_goggles.image", "clothing.hat.image"), ("images/scenes/beach.png", "images/fruits/watermelon.png", "images/sports/swimming_goggles.png", "images/clothing/hat.png"), "这一组将海滩场景和夏季休闲物品关联。", "海滩提供海水和沙地背景，西瓜对应夏季水果，游泳镜用于水中活动，帽子用于遮阳。", "哪个小节把海滩、西瓜、游泳镜和帽子组成夏季场景？", "检索海滩、西瓜、游泳镜和帽子四张夏季场景图片。"),
    Group("scene-object-groups", "snowy_mountain_wear", "雪山与保暖穿戴", "Snowy Mountain and Warm Wear", ("scenes.snowy_mountain.image", "clothing.jacket.image", "clothing.scarf.image", "sports.bicycle_helmet.image"), ("images/scenes/snowy_mountain.png", "images/clothing/jacket.png", "images/clothing/scarf.png", "images/sports/bicycle_helmet.png"), "这一组将寒冷自然场景和保暖防护穿戴关联。", "雪山强调寒冷和积雪，夹克与围巾对应保暖，头盔表达户外运动防护。", "哪个小节把雪山、夹克、围巾和头盔关联为寒冷户外装备？", "检索雪山、夹克、围巾和头盔四张寒冷户外图片。"),
    Group("scene-object-groups", "office_meeting_scene", "办公会议场景", "Office Meeting Scene", ("office.whiteboard.image", "office.clipboard.image", "office.desk_calendar.image", "electronics.laptop.image"), ("images/office/whiteboard.png", "images/office/clipboard.png", "images/office/desk_calendar.png", "images/electronics/laptop.png"), "这一组表达会议计划和协作办公场景。", "白板用于讨论展示，剪贴板用于记录，台历用于安排日期，笔记本电脑用于演示或在线协作。", "哪个小节描述白板、剪贴板、台历和笔记本电脑组成的会议场景？", "检索白板、剪贴板、台历和笔记本电脑四张会议办公图片。"),
    Group("scene-object-groups", "farm_crop_scene", "农田与作物", "Farmland and Crops", ("scenes.farmland.image", "plants.rice.image", "plants.sunflower.image"), ("images/scenes/farmland.png", "images/plants/rice.png", "images/plants/sunflower.png"), "这一组将农业场景和作物图像关联。", "农田提供耕作地块和行列背景，稻谷表现粮食作物，向日葵表现观赏和籽用作物。", "哪个小节把农田、稻谷和向日葵作为农业作物场景介绍？", "检索农田、稻谷和向日葵三张农业相关图片。"),
    Group("scene-object-groups", "city_night_media_devices", "城市夜景与影像设备", "City Night and Media Devices", ("scenes.city_night.image", "electronics.camera.image", "electronics.smartphone.image", "electronics.drone.image"), ("images/scenes/city_night.png", "images/electronics/camera.png", "images/electronics/smartphone.png", "images/electronics/drone.png"), "这一组将城市夜景和影像采集设备关联。", "城市夜景提供灯光与天际线，相机、手机和无人机分别对应手持拍摄、移动拍摄和航拍视角。", "哪个小节把城市夜景、相机、手机和无人机联系到影像采集？", "检索城市夜景、相机、手机和无人机四张影像采集图片。"),
    Group("scene-object-groups", "desert_survival_objects", "沙漠与户外补给", "Desert and Outdoor Supplies", ("scenes.desert.image", "clothing.hat.image", "clothing.backpack.image", "household.electric_kettle.image"), ("images/scenes/desert.png", "images/clothing/hat.png", "images/clothing/backpack.png", "images/household/electric_kettle.png"), "这一组将干旱场景和户外补给物品关联。", "沙漠表现干旱和强光，帽子用于遮阳，背包携带物品，电水壶代表补水和热饮准备的生活用品。", "哪个小节把沙漠、帽子、背包和电水壶关联为户外补给场景？", "检索沙漠、帽子、背包和电水壶四张户外补给图片。"),
    Group("scene-object-groups", "living_room_scene", "客厅生活场景", "Living Room Scene", ("household.sofa.image", "household.table_lamp.image", "electronics.router.image", "electronics.game_controller.image"), ("images/household/sofa.png", "images/household/table_lamp.png", "images/electronics/router.png", "images/electronics/game_controller.png"), "这一组表达客厅中的休息、照明、网络和娱乐对象。", "沙发提供休息座位，台灯提供局部照明，路由器提供网络连接，游戏手柄提供娱乐控制。", "哪个小节描述沙发、台灯、路由器和游戏手柄组成的客厅生活场景？", "检索沙发、台灯、路由器和游戏手柄四张客厅对象图片。"),
)


def main() -> int:
    write_documents()
    update_targets()
    update_queries()
    return 0


def write_documents() -> None:
    for doc, title in DOC_TITLES.items():
        groups = [group for group in GROUPS if group.doc == doc]
        lines = [
            "---",
            f"title: {title}",
            "language: zh-CN",
            "source: local-synthetic",
            "modality: image-text",
            f"version: {DATASET}",
            "target_shape: multi-image-chunk",
            "---",
            "",
            f"# {title}",
            "",
            "本文档用于评测一个文本小节同时关联多张图片 asset 的多模态召回能力。",
            "",
        ]
        for group in groups:
            lines.extend(
                [
                    f"## {group.heading}",
                    "",
                    f"Target: {group.anchor}",
                    "",
                ]
            )
            for path in group.image_paths:
                lines.extend([f"![{group.heading}](./{path})", ""])
            lines.extend([group.summary, "", group.detail, ""])
        (CORPUS_DIR / f"{doc}.md").write_text("\n".join(lines), encoding="utf-8")


def update_targets() -> None:
    path = DATASET_DIR / "targets.yaml"
    data = read_yaml(path)
    chunks = [chunk for chunk in data["chunks"] if not str(chunk.get("id", "")).startswith("groups.")]
    for group in GROUPS:
        chunks.append(
            {
                "id": group.chunk_id,
                "doc": group.doc,
                "heading": group.heading,
                "anchor": group.anchor,
                "asset_ids": list(group.assets),
            }
        )
    data["chunks"] = chunks
    write_yaml(path, data)


def update_queries() -> None:
    path = DATASET_DIR / "queries.yaml"
    data = read_yaml(path)
    queries = [query for query in data["queries"] if not str(query.get("id", "")).startswith("groups_")]
    for group in GROUPS:
        queries.append(
            {
                "id": f"groups_{group.slug}_chunk",
                "query_type": "text_chunk",
                "q": group.chunk_query,
                "expect_any": [group.doc],
                "expect_chunk_any": [group.chunk_id],
                "expect_asset_any": list(group.assets),
            }
        )
        queries.append(
            {
                "id": f"groups_{group.slug}_asset_group",
                "query_type": "asset_group",
                "q": group.asset_query,
                "expect_any": [group.doc],
                "expect_chunk_any": [group.chunk_id],
                "expect_asset_any": list(group.assets),
            }
        )
    data["queries"] = queries
    write_yaml(path, data)


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from generate_multimodal_asset_chunk_dataset import (
    CATEGORIES as BASE_CATEGORIES,
)
from generate_multimodal_asset_chunk_dataset import (
    CORPUS_DIR,
    DATASET,
    DATASET_DIR,
    Category,
    Item,
    yaml_scalar,
)

SHEET_DIR = Path.home() / ".codex" / "generated_images" / "019dca28-eaa6-77f0-8a22-0e9235befec2"


@dataclass(frozen=True)
class AugmentCategory:
    category: Category
    sheet_name: str


EXTRA: tuple[AugmentCategory, ...] = (
    AugmentCategory(
        Category(
            key="electronics",
            title="多电子设备图片召回评测",
            old_dataset="",
            image_dir="electronics",
            items=(
                Item("smartphone", "手机", "Smartphone", "手机是便携式电子设备，用于通信、拍摄和移动应用。", "矩形屏幕、黑色边框和小型机身是主要视觉线索。", "适合测试屏幕类设备和便携电子产品召回。", "Find the smartphone with a black rectangular screen.", "手机的小节如何描述屏幕和便携用途？"),
                Item("laptop", "笔记本电脑", "Laptop", "笔记本电脑用于办公、学习和移动计算。", "展开的屏幕、键盘和铰链结构是关键视觉特征。", "适合测试电脑设备、键盘和屏幕组合召回。", "检索带屏幕和键盘的笔记本电脑图片。", "笔记本电脑的小节介绍了哪些计算用途和结构？"),
                Item("camera", "相机", "Camera", "相机用于拍摄照片和视频，是常见影像设备。", "镜头、机身和取景区域构成核心视觉线索。", "适合测试圆形镜头和影像设备召回。", "Find the camera with a prominent round lens.", "相机的小节如何描述镜头和拍摄用途？"),
                Item("headphones", "耳机", "Headphones", "耳机用于收听音频，可覆盖双耳或连接移动设备。", "头梁、左右耳罩和弧形轮廓是主要视觉特征。", "适合测试音频设备和对称耳罩结构召回。", "检索带头梁和双耳罩的耳机图片。", "耳机的小节介绍了哪些音频和结构特征？"),
                Item("smartwatch", "智能手表", "Smartwatch", "智能手表可显示通知、健康数据和运动信息。", "小型方形或圆形屏幕与表带组合明显。", "适合测试腕戴设备、屏幕和表带召回。", "Find the smartwatch with a screen and wrist strap.", "智能手表的小节如何描述屏幕和健康用途？"),
                Item("router", "路由器", "Router", "路由器用于家庭或办公室网络连接。", "扁平机身、天线和指示灯区域是典型线索。", "适合测试网络设备和天线结构召回。", "检索带天线的 Wi-Fi 路由器图片。", "路由器的小节介绍了哪些网络连接特征？"),
                Item("printer", "打印机", "Printer", "打印机用于输出纸质文档或图像。", "方正机身、出纸口和托盘结构是主要视觉线索。", "适合测试办公电子设备和出纸结构召回。", "Find the printer with a paper output tray.", "打印机的小节如何描述出纸口和办公用途？"),
                Item("drone", "无人机", "Drone", "无人机可用于航拍、巡检和娱乐飞行。", "四个旋翼、机身和对称臂架是关键视觉特征。", "适合测试飞行设备和多旋翼结构召回。", "检索四旋翼无人机图片。", "无人机的小节介绍了哪些飞行和旋翼特征？"),
                Item("game_controller", "游戏手柄", "Game Controller", "游戏手柄用于控制电子游戏角色和菜单。", "双握柄、按钮、摇杆和方向键构成典型外观。", "适合测试娱乐电子设备和按钮布局召回。", "Find the game controller with buttons and joysticks.", "游戏手柄的小节如何描述按钮和控制用途？"),
                Item("microphone", "麦克风", "Microphone", "麦克风用于录音、直播和语音输入。", "圆柱形握柄、网格拾音头和支架结构是主要线索。", "适合测试音频输入设备和网格纹理召回。", "检索带网格拾音头的麦克风图片。", "麦克风的小节介绍了哪些录音和结构特征？"),
            ),
        ),
        "ig_017498eff26b4d770169f455c91a388191b80aafaf47731637.png",
    ),
    AugmentCategory(
        Category(
            key="household",
            title="多家居用品图片召回评测",
            old_dataset="",
            image_dir="household",
            items=(
                Item("sofa", "沙发", "Sofa", "沙发是客厅中常见的坐具，供休息和会客使用。", "宽坐垫、靠背和扶手构成柔软家具轮廓。", "适合测试家居家具和软质材质召回。", "Find the sofa with cushions and armrests.", "沙发的小节如何描述坐垫和客厅用途？"),
                Item("table_lamp", "台灯", "Table Lamp", "台灯用于桌面照明，常见于书桌和床头柜。", "灯罩、灯杆和底座形成上下结构。", "适合测试照明用品和灯罩形态召回。", "检索带灯罩和底座的台灯图片。", "台灯的小节介绍了哪些照明和结构特征？"),
                Item("bed", "床", "Bed", "床用于睡眠和休息，是卧室核心家具。", "床垫、枕头、床头板和长方形轮廓是主要线索。", "适合测试卧室家具和软装结构召回。", "Find the bed with pillows and headboard.", "床的小节如何描述睡眠用途和组成？"),
                Item("refrigerator", "冰箱", "Refrigerator", "冰箱用于低温保存食物和饮料。", "高大柜体、门把手和冷藏门轮廓是关键特征。", "适合测试厨房电器和竖直柜体召回。", "检索带门把手的冰箱图片。", "冰箱的小节介绍了哪些低温保存用途？"),
                Item("washing_machine", "洗衣机", "Washing Machine", "洗衣机用于清洗衣物，是常见家用电器。", "圆形舱门、方形机身和控制面板是主要线索。", "适合测试家电和圆形门结构召回。", "Find the washing machine with a round front door.", "洗衣机的小节如何描述清洗用途和舱门？"),
                Item("microwave", "微波炉", "Microwave Oven", "微波炉用于快速加热食物。", "矩形箱体、透明门窗和侧边控制面板是典型外观。", "适合测试厨房小家电和门窗结构召回。", "检索带透明门窗的微波炉图片。", "微波炉的小节介绍了哪些加热和面板特征？"),
                Item("vacuum_cleaner", "吸尘器", "Vacuum Cleaner", "吸尘器用于清洁地面和家具缝隙。", "长管、吸头和机身组合形成清洁工具外观。", "适合测试家居清洁设备和长管结构召回。", "Find the vacuum cleaner with hose and floor head.", "吸尘器的小节如何描述清洁用途和吸头？"),
                Item("electric_kettle", "电水壶", "Electric Kettle", "电水壶用于快速烧水，常见于厨房和办公室。", "壶嘴、把手、壶身和底座是主要视觉线索。", "适合测试小家电、壶形轮廓和把手召回。", "检索带壶嘴和把手的电水壶图片。", "电水壶的小节介绍了哪些烧水和壶体特征？"),
                Item("air_conditioner", "空调", "Air Conditioner", "空调用于调节室内温度和空气流动。", "长条形室内机、出风口和简洁面板是关键特征。", "适合测试白色家电和长条出风口召回。", "Find the wall air conditioner with a long vent.", "空调的小节如何描述温度调节和出风口？"),
                Item("dining_table", "餐桌", "Dining Table", "餐桌用于进餐、摆放餐具和家庭聚会。", "桌面、桌腿和围绕空间构成家具识别线索。", "适合测试桌类家具和用餐场景语义召回。", "检索带桌面和桌腿的餐桌图片。", "餐桌的小节介绍了哪些用餐用途和结构？"),
            ),
        ),
        "ig_017498eff26b4d770169f4560967188191b0374aad0c930e78.png",
    ),
    AugmentCategory(
        Category(
            key="clothing",
            title="多服饰配件图片召回评测",
            old_dataset="",
            image_dir="clothing",
            items=(
                Item("t_shirt", "T 恤", "T-shirt", "T 恤是常见上衣，适合日常休闲穿着。", "短袖、圆领和平整衣身是主要视觉线索。", "适合测试基础服装和衣领袖口召回。", "Find the T-shirt with short sleeves and round neck.", "T 恤的小节如何描述短袖和休闲用途？"),
                Item("jacket", "夹克", "Jacket", "夹克用于保暖或防风，常作为外套穿着。", "前襟、拉链、袖子和较厚面料是关键特征。", "适合测试外套类服装和拉链结构召回。", "检索带拉链的夹克图片。", "夹克的小节介绍了哪些保暖和外套特征？"),
                Item("running_shoe", "运动鞋", "Running Shoe", "运动鞋用于跑步、训练和日常运动穿着。", "鞋面、鞋带、厚鞋底和流线轮廓是主要线索。", "适合测试鞋类、鞋带和运动语义召回。", "Find the running shoe with laces and thick sole.", "运动鞋的小节如何描述鞋底和运动用途？"),
                Item("hat", "帽子", "Hat", "帽子用于遮阳、保暖或搭配服装。", "帽檐、圆顶和可戴在头部的轮廓是典型特征。", "适合测试头部配饰和帽檐召回。", "检索带帽檐的帽子图片。", "帽子的小节介绍了哪些遮阳和配饰用途？"),
                Item("backpack", "背包", "Backpack", "背包用于携带书本、电脑和旅行用品。", "双肩带、主仓、拉链和前袋是主要视觉线索。", "适合测试包袋、肩带和收纳结构召回。", "Find the backpack with shoulder straps and zipper pockets.", "背包的小节如何描述收纳和肩带？"),
                Item("eyeglasses", "眼镜", "Eyeglasses", "眼镜用于矫正视力、保护眼睛或装饰。", "两个镜片、镜框和镜腿构成对称结构。", "适合测试透明材质、细框和面部配件召回。", "检索带两个镜片和镜腿的眼镜图片。", "眼镜的小节介绍了哪些镜片和镜框特征？"),
                Item("wristwatch", "手表", "Wristwatch", "手表用于查看时间，也可作为配饰。", "表盘、指针或屏幕、表带构成腕戴结构。", "适合测试小型配件和圆形表盘召回。", "Find the wristwatch with a round face and strap.", "手表的小节如何描述计时和配饰用途？"),
                Item("umbrella", "雨伞", "Umbrella", "雨伞用于遮雨和遮阳，常可折叠携带。", "弧形伞面、伞骨和手柄是主要视觉线索。", "适合测试展开伞面和天气用品召回。", "检索展开伞面和手柄的雨伞图片。", "雨伞的小节介绍了哪些遮雨和结构特征？"),
                Item("dress", "连衣裙", "Dress", "连衣裙是一体式服装，常用于日常或正式场合。", "上身、裙摆和连续衣身轮廓是关键视觉特征。", "适合测试女装、裙摆和整体服装轮廓召回。", "Find the dress with a flared skirt.", "连衣裙的小节如何描述裙摆和穿着场景？"),
                Item("scarf", "围巾", "Scarf", "围巾用于保暖、装饰或搭配服装。", "长条布料、柔软褶皱和可缠绕形态是主要线索。", "适合测试织物材质和长条配饰召回。", "检索长条柔软围巾图片。", "围巾的小节介绍了哪些保暖和材质特征？"),
            ),
        ),
        "ig_017498eff26b4d770169f4563fb7c881919a6055e0d3ee9fa1.png",
    ),
    AugmentCategory(
        Category(
            key="medical",
            title="多医疗物品图片召回评测",
            old_dataset="",
            image_dir="medical",
            items=(
                Item("stethoscope", "听诊器", "Stethoscope", "听诊器用于听取心肺声音，是临床检查常用工具。", "耳管、软管和圆形听诊头是关键视觉线索。", "适合测试医疗器械和软管结构召回。", "Find the stethoscope with earpieces and round chest piece.", "听诊器的小节如何描述临床检查用途？"),
                Item("syringe", "注射器", "Syringe", "注射器用于抽取或注入液体药物。", "透明针筒、活塞和细针头是主要视觉特征。", "适合测试细长医疗器具和透明材质召回。", "检索透明针筒和细针头的注射器图片。", "注射器的小节介绍了哪些液体注入结构？"),
                Item("thermometer", "体温计", "Digital Thermometer", "体温计用于测量人体温度。", "细长机身、小屏幕和探头端构成典型外观。", "适合测试医疗测量设备和小屏幕召回。", "Find the digital thermometer with a small display.", "体温计的小节如何描述测温用途和探头？"),
                Item("bandage", "绷带", "Bandage Roll", "绷带用于包扎伤口或固定受伤部位。", "卷状白色织物和层叠边缘是主要视觉线索。", "适合测试医疗耗材和卷状纹理召回。", "检索白色卷状绷带图片。", "绷带的小节介绍了哪些包扎用途和形态？"),
                Item("medicine_bottle", "药瓶", "Medicine Bottle", "药瓶用于存放片剂、胶囊或液体药物。", "瓶身、瓶盖和内部药片轮廓是关键线索。", "适合测试药品容器和医疗用品召回。", "Find the medicine bottle with cap and pills.", "药瓶的小节如何描述储存药物用途？"),
                Item("first_aid_kit", "急救箱", "First Aid Kit", "急救箱用于集中存放应急医疗用品。", "箱体、提手和医疗十字标识构成典型图像。", "适合测试急救物品和箱体结构召回。", "检索带医疗十字的急救箱图片。", "急救箱的小节介绍了哪些应急用途？"),
                Item("wheelchair", "轮椅", "Wheelchair", "轮椅帮助行动不便者移动。", "大轮、座椅、扶手和脚踏板是主要视觉结构。", "适合测试辅助设备和大轮结构召回。", "Find the wheelchair with large wheels and seat.", "轮椅的小节如何描述移动辅助功能？"),
                Item("face_mask", "口罩", "Surgical Face Mask", "口罩用于遮盖口鼻，减少飞沫传播和颗粒吸入。", "褶皱面料、耳带和浅色矩形轮廓是主要线索。", "适合测试防护用品和柔性材质召回。", "检索带耳带和褶皱的口罩图片。", "口罩的小节介绍了哪些防护和佩戴结构？"),
                Item("blood_pressure_monitor", "血压计", "Blood Pressure Monitor", "血压计用于测量血压，常包含袖带和显示屏。", "臂带、软管、主机和数字屏幕是关键视觉线索。", "适合测试医疗测量设备和袖带结构召回。", "Find the blood pressure monitor with cuff and display.", "血压计的小节如何描述袖带和测量用途？"),
                Item("microscope", "显微镜", "Microscope", "显微镜用于观察微小样本和细胞结构。", "目镜、物镜、载物台和支架是主要视觉结构。", "适合测试实验室设备和光学结构召回。", "检索带目镜和载物台的显微镜图片。", "显微镜的小节介绍了哪些观察和光学部件？"),
            ),
        ),
        "ig_017498eff26b4d770169f45688a37c8191822b931b174455e9.png",
    ),
    AugmentCategory(
        Category(
            key="sports",
            title="多运动器材图片召回评测",
            old_dataset="",
            image_dir="sports",
            items=(
                Item("soccer_ball", "足球", "Soccer Ball", "足球用于足球运动中的传球、射门和控球。", "黑白拼块或多边形纹理的球体是主要线索。", "适合测试球类、几何纹理和运动语义召回。", "Find the soccer ball with black and white panels.", "足球的小节如何描述拼块纹理和运动用途？"),
                Item("basketball", "篮球", "Basketball", "篮球用于投篮、运球和团队比赛。", "橙色球体、黑色弧线和颗粒纹理是关键特征。", "适合测试橙色球类和线条纹理召回。", "检索橙色篮球和黑色弧线图片。", "篮球的小节介绍了哪些线条和比赛用途？"),
                Item("tennis_racket", "网球拍", "Tennis Racket", "网球拍用于击打网球，包含拍面和握柄。", "椭圆拍框、网线和长握柄是主要视觉线索。", "适合测试球拍结构和网格纹理召回。", "Find the tennis racket with strings and handle.", "网球拍的小节如何描述拍框和网线？"),
                Item("skateboard", "滑板", "Skateboard", "滑板用于街头运动和短距离滑行。", "长板面、四个小轮和弯曲板头是典型外观。", "适合测试板类运动器材和轮子召回。", "检索带四个小轮的滑板图片。", "滑板的小节介绍了哪些板面和滑行用途？"),
                Item("dumbbell", "哑铃", "Dumbbell", "哑铃用于力量训练和健身锻炼。", "中间握柄和两端配重块构成对称结构。", "适合测试健身器材和金属对称结构召回。", "Find the dumbbell with weights on both ends.", "哑铃的小节如何描述力量训练和配重？"),
                Item("yoga_mat", "瑜伽垫", "Yoga Mat", "瑜伽垫用于瑜伽、拉伸和地面训练。", "卷起或展开的长方形软垫是主要视觉线索。", "适合测试柔性运动垫和卷状结构召回。", "检索卷起的瑜伽垫图片。", "瑜伽垫的小节介绍了哪些地面训练用途？"),
                Item("boxing_gloves", "拳击手套", "Boxing Gloves", "拳击手套用于保护手部并缓冲击打。", "成对厚手套、腕带和红色软垫轮廓常见。", "适合测试成对器材和防护垫结构召回。", "Find the pair of red boxing gloves.", "拳击手套的小节如何描述保护和腕带？"),
                Item("swimming_goggles", "游泳镜", "Swimming Goggles", "游泳镜用于保护眼睛并改善水下视野。", "两个透明镜片、鼻桥和弹性带是关键线索。", "适合测试透明镜片和水上运动配件召回。", "检索带透明镜片的游泳镜图片。", "游泳镜的小节介绍了哪些水下视野和结构？"),
                Item("baseball_glove", "棒球手套", "Baseball Glove", "棒球手套用于接球和保护手掌。", "棕色皮革、张开的手掌形状和缝线是主要特征。", "适合测试皮革纹理和手套形态召回。", "Find the brown baseball glove with stitching.", "棒球手套的小节如何描述接球和缝线？"),
                Item("bicycle_helmet", "自行车头盔", "Bicycle Helmet", "自行车头盔用于骑行时保护头部。", "弧形外壳、通风孔和安全带结构是典型线索。", "适合测试防护装备和通风孔召回。", "检索带通风孔的自行车头盔图片。", "自行车头盔的小节介绍了哪些保护结构？"),
            ),
        ),
        "ig_017498eff26b4d770169f456c36c448191a0dfb5edc866bfcc.png",
    ),
    AugmentCategory(
        Category(
            key="instruments",
            title="多乐器图片召回评测",
            old_dataset="",
            image_dir="instruments",
            items=(
                Item("piano", "钢琴", "Piano Keyboard", "钢琴通过键盘敲击琴槌发声，常用于独奏和伴奏。", "黑白琴键、长条键盘和光滑外壳是主要线索。", "适合测试键盘乐器和黑白重复结构召回。", "Find the piano keyboard with black and white keys.", "钢琴的小节如何描述琴键和演奏用途？"),
                Item("guitar", "吉他", "Acoustic Guitar", "吉他通过拨弦或扫弦演奏，常用于流行和民谣音乐。", "木质共鸣箱、圆形音孔、琴颈和弦是关键特征。", "适合测试弦乐器、木纹和音孔召回。", "检索带圆形音孔的木吉他图片。", "吉他的小节介绍了哪些弦和共鸣箱特征？"),
                Item("violin", "小提琴", "Violin", "小提琴是高音乐器，常用于独奏和管弦乐。", "小型木质琴身、琴弓、弦和弯曲腰线是主要线索。", "适合测试弓弦乐器和木质曲线结构召回。", "Find the violin with bow and strings.", "小提琴的小节如何描述琴弓和高音特点？"),
                Item("drum_kit", "架子鼓", "Drum Kit", "架子鼓由多个鼓和镲片组成，用于节奏演奏。", "圆形鼓面、支架和金属镲片组合明显。", "适合测试多部件乐器和圆形鼓面召回。", "检索包含鼓面和镲片的架子鼓图片。", "架子鼓的小节介绍了哪些节奏和组件？"),
                Item("trumpet", "小号", "Trumpet", "小号是铜管乐器，通过吹嘴和活塞演奏。", "金属管身、喇叭口和三个活塞是主要视觉线索。", "适合测试铜管乐器和金色金属材质召回。", "Find the trumpet with bell and valves.", "小号的小节如何描述喇叭口和活塞？"),
                Item("saxophone", "萨克斯", "Saxophone", "萨克斯是簧片管乐器，常用于爵士乐和流行音乐。", "弯曲金属管、按键和大喇叭口是关键特征。", "适合测试弯曲管乐器和金属按键召回。", "检索弯曲金色萨克斯图片。", "萨克斯的小节介绍了哪些弯管和按键特征？"),
                Item("flute", "长笛", "Flute", "长笛是横吹木管乐器，音色清亮。", "细长金属管身和一排按键孔是主要线索。", "适合测试细长乐器和线性按键召回。", "Find the silver flute with a row of keys.", "长笛的小节如何描述横吹和按键？"),
                Item("cello", "大提琴", "Cello", "大提琴是低音乐器，通常坐姿演奏。", "大型木质琴身、长琴颈、弦和尾针是典型外观。", "适合测试大型弦乐器和竖直形态召回。", "检索带长琴颈的大提琴图片。", "大提琴的小节介绍了哪些低音和琴身特征？"),
                Item("harmonica", "口琴", "Harmonica", "口琴是小型吹奏乐器，便于携带。", "长方形金属外壳和成排音孔是关键视觉线索。", "适合测试小型乐器和重复孔洞结构召回。", "Find the harmonica with a row of holes.", "口琴的小节如何描述便携和音孔？"),
                Item("tambourine", "手鼓", "Tambourine", "手鼓通过摇动或拍击发声，常用于节奏伴奏。", "圆形框架、鼓面和周围金属小镲片是主要特征。", "适合测试打击乐器和圆形框架召回。", "检索带金属小镲片的手鼓图片。", "手鼓的小节介绍了哪些节奏和框架特征？"),
            ),
        ),
        "ig_017498eff26b4d770169f456fbe99081919b59acaa79394762.png",
    ),
    AugmentCategory(
        Category(
            key="office",
            title="多办公用品图片召回评测",
            old_dataset="",
            image_dir="office",
            items=(
                Item("notebook", "笔记本", "Notebook", "笔记本用于记录会议、学习笔记和日常计划。", "封面、纸页和装订边构成主要视觉线索。", "适合测试纸质文具和书本形态召回。", "Find the notebook with pages and cover.", "笔记本的小节如何描述记录用途和纸页？"),
                Item("fountain_pen", "钢笔", "Fountain Pen", "钢笔用于书写，常具有笔帽和金属笔尖。", "细长笔身、笔尖和笔帽是关键视觉特征。", "适合测试书写工具和尖端结构召回。", "检索带金属笔尖的钢笔图片。", "钢笔的小节介绍了哪些书写和笔尖特征？"),
                Item("file_folder", "文件夹", "File Folder", "文件夹用于分类保存纸质文件。", "扁平封套、标签页和折页结构是主要线索。", "适合测试办公收纳用品和扁平形态召回。", "Find the file folder with a tab.", "文件夹的小节如何描述文件收纳用途？"),
                Item("stapler", "订书机", "Stapler", "订书机用于把多页纸张装订在一起。", "上压臂、底座和金属出钉口是主要视觉结构。", "适合测试办公工具和机械结构召回。", "检索订书机和金属出钉口图片。", "订书机的小节介绍了哪些装订结构？"),
                Item("paper_clips", "回形针", "Paper Clips", "回形针用于临时固定纸张。", "细金属线弯成椭圆回环结构是典型视觉线索。", "适合测试小型金属文具和重复线条召回。", "Find the paper clips with looped metal wire.", "回形针的小节如何描述固定纸张和线形结构？"),
                Item("calculator", "计算器", "Calculator", "计算器用于数字计算和办公统计。", "矩形机身、显示屏和成排按键是关键特征。", "适合测试数字工具、按键网格和屏幕召回。", "检索带显示屏和按键的计算器图片。", "计算器的小节介绍了哪些显示和计算用途？"),
                Item("whiteboard", "白板", "Whiteboard", "白板用于会议讨论、教学和临时书写。", "大面积白色板面、边框和支架构成主要视觉线索。", "适合测试办公展示工具和矩形白面召回。", "Find the blank whiteboard with frame.", "白板的小节如何描述会议和书写用途？"),
                Item("sticky_notes", "便签", "Sticky Notes", "便签用于快速记录提醒和任务。", "小方纸片、鲜艳颜色和叠放形态是主要特征。", "适合测试彩色纸张和提醒工具召回。", "检索彩色便签纸图片。", "便签的小节介绍了哪些提醒和纸片特征？"),
                Item("clipboard", "剪贴板", "Clipboard", "剪贴板用于夹住纸张，方便站立记录。", "硬板、顶部金属夹和纸张组合明显。", "适合测试夹持文具和板状结构召回。", "Find the clipboard with a metal clip.", "剪贴板的小节如何描述夹纸和记录用途？"),
                Item("desk_calendar", "台历", "Desk Calendar", "台历用于查看日期和安排日程。", "立式支架、翻页纸张和日期页面构成典型外观。", "适合测试日程工具和立式纸页召回。", "检索立式台历图片。", "台历的小节介绍了哪些日期和日程用途？"),
            ),
        ),
        "ig_017498eff26b4d770169f4573c2900819182e0a08ee2e5dad0.png",
    ),
    AugmentCategory(
        Category(
            key="scenes",
            title="多场景天气图片召回评测",
            old_dataset="",
            image_dir="scenes",
            items=(
                Item("beach", "海滩", "Beach", "海滩场景常包含海水、沙滩和开阔天空。", "蓝色海面、浅色沙地和水平海岸线是主要视觉线索。", "适合测试自然场景、水体和沙地召回。", "Find the beach scene with ocean and sand.", "海滩的小节如何描述海水和沙滩？"),
                Item("snowy_mountain", "雪山", "Snowy Mountain", "雪山场景表现高海拔山体和寒冷环境。", "白色积雪、尖峰山体和蓝天背景是关键特征。", "适合测试雪景、山体轮廓和冷色自然场景召回。", "检索白色雪冠和山峰的雪山图片。", "雪山的小节介绍了哪些高海拔和积雪特征？"),
                Item("forest", "森林", "Forest", "森林由密集树木、树冠和阴影环境组成。", "绿色树冠、竖直树干和层叠植被是主要线索。", "适合测试自然植被场景和深绿色纹理召回。", "Find the forest scene with many trees.", "森林的小节如何描述树木和植被层次？"),
                Item("desert", "沙漠", "Desert", "沙漠场景以干旱气候和大片沙地为特征。", "黄色沙丘、开阔天空和稀少植被构成典型图像。", "适合测试干旱场景、沙丘纹理和暖色地貌召回。", "检索黄色沙丘和开阔天空的沙漠图片。", "沙漠的小节介绍了哪些干旱和沙丘特征？"),
                Item("city_night", "城市夜景", "City Night Skyline", "城市夜景展示建筑轮廓、灯光和夜间天际线。", "高楼剪影、窗户灯光和深色天空是关键视觉线索。", "适合测试人工场景、夜间光源和建筑轮廓召回。", "Find the city night skyline with building lights.", "城市夜景的小节如何描述灯光和天际线？"),
                Item("rainy_street", "雨天街道", "Rainy Street", "雨天街道表现湿润路面、降雨和反光环境。", "雨滴、湿地反光、街灯和道路透视是主要特征。", "适合测试天气场景、反射和街道语义召回。", "检索湿润反光路面的雨天街道图片。", "雨天街道的小节介绍了哪些天气和反光特征？"),
                Item("sunset", "日落", "Sunset Landscape", "日落场景表现太阳接近地平线时的暖色天空。", "橙红天空、低位太阳和地平线剪影是主要线索。", "适合测试自然光照、暖色渐变和时间语义召回。", "Find the sunset landscape with orange sky.", "日落的小节如何描述暖色天空和地平线？"),
                Item("farmland", "农田", "Farmland", "农田场景包含耕作地块、作物行列和开阔乡村空间。", "整齐田垄、绿色或金色作物和远处地平线是关键特征。", "适合测试农业场景、行列纹理和乡村地貌召回。", "检索整齐作物行列的农田图片。", "农田的小节介绍了哪些作物行列和农业特征？"),
                Item("library", "图书馆", "Library Interior", "图书馆室内场景包含书架、书本和安静阅读空间。", "成排书架、书脊纹理和室内透视是主要视觉线索。", "适合测试室内公共空间和重复书本结构召回。", "Find the library interior with rows of bookshelves.", "图书馆的小节如何描述书架和阅读空间？"),
                Item("kitchen", "厨房", "Kitchen Interior", "厨房室内场景包含橱柜、台面和烹饪设备。", "操作台、橱柜、水槽或灶具形成典型厨房结构。", "适合测试室内生活场景和厨房设施召回。", "检索带橱柜和台面的厨房图片。", "厨房的小节介绍了哪些烹饪和室内结构？"),
            ),
        ),
        "ig_017498eff26b4d770169f45778a78c8191acd55b3d7e696a65.png",
    ),
)


def square_pad(image: Image.Image) -> Image.Image:
    width, height = image.size
    side = max(width, height)
    out = Image.new("RGB", (side, side), "white")
    out.paste(image.convert("RGB"), ((side - width) // 2, (side - height) // 2))
    return out


def crop_sheet(augment: AugmentCategory) -> None:
    sheet_path = SHEET_DIR / augment.sheet_name
    if not sheet_path.is_file():
        raise FileNotFoundError(sheet_path)
    category = augment.category
    out_dir = CORPUS_DIR / "images" / category.image_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(sheet_path) as sheet:
        width, height = sheet.size
        cell_w = width / 5
        cell_h = height / 2
        for index, item in enumerate(category.items):
            col = index % 5
            row = index // 5
            crop = sheet.crop(
                (
                    round(col * cell_w),
                    round(row * cell_h),
                    round((col + 1) * cell_w),
                    round((row + 1) * cell_h),
                )
            )
            square_pad(crop).resize((512, 512), Image.Resampling.LANCZOS).save(
                out_dir / f"{item.slug}.png",
                optimize=True,
            )


def write_markdown(category: Category) -> None:
    lines = [
        "---",
        f"title: {category.title}",
        "language: zh-CN",
        "source: local-synthetic",
        "modality: image-text",
        f"version: {DATASET}",
        f"category: {category.key}",
        "---",
        "",
        f"# {category.title}",
        "",
        "本文档用于增补多模态召回评测的视觉域，覆盖更广泛的物体、材质、场景和用途。",
        "",
    ]
    for item in category.items:
        anchor = f"{category.key}.{item.slug}"
        lines.extend(
            [
                f"## {item.zh} / {item.en}",
                "",
                f"Target: {anchor}",
                "",
                f"![{item.zh}图片 - {item.en}](./images/{category.image_dir}/{item.slug}.png)",
                "",
                item.desc,
                "",
                item.visual,
                "",
                item.use,
                "",
                f"检索提示：{item.zh}、{item.en}、{category.title}、图片、颜色、形状、材质、局部特征、用途。",
                "",
            ]
        )
    (CORPUS_DIR / f"{category.key}.md").write_text("\n".join(lines), encoding="utf-8")


def write_dataset_yaml() -> None:
    (DATASET_DIR / "dataset.yaml").write_text(
        "\n".join(
            [
                f"name: {DATASET}",
                "description: >",
                "  Synthetic multimodal retrieval dataset with category-level Markdown files,",
                "  local PNG image assets, and explicit asset/chunk recall targets. Expanded",
                "  to cover natural objects, daily objects, tools, scenes, medical items,",
                "  electronics, clothing, sports, instruments, and office supplies.",
                "thresholds: {}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def all_categories() -> tuple[Category, ...]:
    return BASE_CATEGORIES + tuple(augment.category for augment in EXTRA)


def write_targets_yaml() -> None:
    lines = ["assets:"]
    for category in all_categories():
        for item in category.items:
            target = f"{category.key}.{item.slug}"
            lines.extend(
                [
                    f"  - id: {target}.image",
                    f"    doc: {category.key}",
                    f"    path: images/{category.image_dir}/{item.slug}.png",
                    f"    heading: {yaml_scalar(f'{item.zh} / {item.en}')}",
                    f"    anchor: {target}",
                ]
            )
    lines.append("chunks:")
    for category in all_categories():
        for item in category.items:
            target = f"{category.key}.{item.slug}"
            lines.extend(
                [
                    f"  - id: {target}.text",
                    f"    doc: {category.key}",
                    f"    heading: {yaml_scalar(f'{item.zh} / {item.en}')}",
                    f"    anchor: {target}",
                    f"    asset_id: {target}.image",
                ]
            )
    (DATASET_DIR / "targets.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_queries_yaml() -> None:
    lines = ["queries:"]
    for category in all_categories():
        for item in category.items:
            target = f"{category.key}.{item.slug}"
            lines.extend(
                [
                    f"  - id: {category.key}_{item.slug}_asset",
                    "    query_type: asset",
                    f"    q: {yaml_scalar(item.asset_query)}",
                    f"    expect_any: [{category.key}]",
                    f"    expect_asset_any: [{target}.image]",
                    f"  - id: {category.key}_{item.slug}_chunk",
                    "    query_type: text_chunk",
                    f"    q: {yaml_scalar(item.chunk_query)}",
                    f"    expect_any: [{category.key}]",
                    f"    expect_chunk_any: [{target}.text]",
                ]
            )
    (DATASET_DIR / "queries.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    for augment in EXTRA:
        crop_sheet(augment)
        write_markdown(augment.category)
        print(f"added {augment.category.key}")
    write_dataset_yaml()
    write_targets_yaml()
    write_queries_yaml()
    print(f"updated {DATASET_DIR}")


if __name__ == "__main__":
    main()

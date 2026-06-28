from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASET = "synthetic-multimodal-datasets-v1"
DATASET_DIR = ROOT / "datasets" / DATASET
CORPUS_DIR = DATASET_DIR / "corpus"


@dataclass(frozen=True)
class Item:
    slug: str
    zh: str
    en: str
    desc: str
    visual: str
    use: str
    asset_query: str
    chunk_query: str


@dataclass(frozen=True)
class Category:
    key: str
    title: str
    old_dataset: str
    image_dir: str
    items: tuple[Item, ...]


CATEGORIES: tuple[Category, ...] = (
    Category(
        key="fruits",
        title="多水果图片召回评测",
        old_dataset="synthetic-fruits-multimodal-v1",
        image_dir="fruits",
        items=(
            Item("apple", "苹果", "Apple", "苹果是常见水果，通常用于鲜食、烘焙和果汁制作。", "红色圆形果身、短果梗和绿色叶片是图片中的主要视觉线索。", "适合测试红色圆形水果、叶片、果梗和中英文水果名称的跨模态召回。", "哪张图片展示了红色圆形苹果和绿色叶片？", "苹果的小节介绍了哪些视觉特征和常见用途？"),
            Item("banana", "香蕉", "Banana", "香蕉是热带水果，成熟时口感柔软并带有明显甜味。", "弯曲的长条形轮廓、黄色表皮和两端深色蒂部是关键视觉线索。", "适合测试弯月形、黄色水果和英文 banana 查询的图片召回。", "Find the curved yellow banana image.", "香蕉的小节如何描述形状、颜色和食用特点？"),
            Item("orange", "橙子", "Orange", "橙子富含汁液，常用于鲜食、榨汁和甜点调味。", "明亮橙色外皮、近圆形轮廓和表皮纹理是主要视觉特征。", "适合测试橙色圆形目标以及与柠檬等相近颜色目标的区分。", "检索包含橙色圆形橙子的水果图片。", "橙子的小节提到了哪些用途和视觉特征？"),
            Item("strawberry", "草莓", "Strawberry", "草莓是浆果类水果，常用于甜点、果酱和鲜食。", "红色心形或圆锥形果身、浅色籽点和绿色萼片构成强视觉组合。", "适合测试红色小籽、绿色顶部结构和局部纹理召回。", "哪张图片有红色草莓、浅色小籽和绿色萼片？", "草莓的小节如何描述果身、籽点和用途？"),
            Item("grape", "葡萄", "Grape", "葡萄通常成串生长，可鲜食，也可用于酿酒和制作葡萄干。", "紫色小圆果聚集成串，并带有绿色叶片或藤梗。", "适合测试数量聚类、紫色果粒和成串结构的多模态召回。", "Find the purple grape cluster image.", "葡萄的小节介绍了哪些成串结构和用途？"),
            Item("watermelon", "西瓜", "Watermelon", "西瓜是夏季常见水果，果肉多汁，常切片食用。", "绿色瓜皮、浅色内层、红色果肉和黑色籽粒是显著线索。", "适合测试切片结构、红绿颜色对比和籽粒细节召回。", "检索绿色瓜皮、红色果肉和黑籽的西瓜切片。", "西瓜的小节如何描述果皮、果肉和食用方式？"),
            Item("pineapple", "菠萝", "Pineapple", "菠萝有浓郁香气，常用于鲜食、果汁和烹饪。", "金黄色椭圆果身、菱格纹理和绿色冠叶组合明显。", "适合测试纹理、冠叶和黄绿色组合的图片召回。", "Which image has a yellow pineapple body with green crown leaves?", "菠萝的小节说明了哪些纹理和冠叶特征？"),
            Item("kiwi", "猕猴桃", "Kiwi", "猕猴桃常以切面展示，口感酸甜，富含维生素。", "棕色外皮、绿色果肉、白色中心和环形黑籽构成典型切面。", "适合测试切面、环形籽粒和绿色果肉的细粒度召回。", "查找绿色切面、白色中心和黑色环形籽的猕猴桃。", "猕猴桃的小节如何描述切面结构？"),
            Item("mango", "芒果", "Mango", "芒果是热带水果，常用于鲜食、果汁和甜品。", "椭圆果形、黄橙色主体和局部红绿色渐变是主要视觉特征。", "适合测试渐变色、椭圆形和热带水果语义召回。", "Find the orange-yellow mango with red color transition.", "芒果的小节介绍了哪些颜色过渡和用途？"),
            Item("lemon", "柠檬", "Lemon", "柠檬常用于调味、饮品和烘焙，味道酸爽。", "亮黄色椭圆形果身和两端略尖的轮廓有助于区分橙子。", "适合测试相近颜色但形状不同的水果识别。", "检索亮黄色椭圆形、两端略尖的柠檬图片。", "柠檬的小节如何区分它和橙子？"),
        ),
    ),
    Category(
        key="animals",
        title="多动物图片召回评测",
        old_dataset="synthetic-animals-multimodal-v1",
        image_dir="animals",
        items=(
            Item("cat", "猫", "Cat", "猫是常见伴侣动物，行动敏捷，常与家庭生活场景相关。", "三角耳、圆脸、胡须和明亮眼睛是猫图像中的关键线索。", "适合测试宠物类别、脸部轮廓和胡须等细节召回。", "检索有三角耳、胡须和圆脸的猫图片。", "猫的小节说明了哪些面部视觉特征？"),
            Item("dog", "狗", "Dog", "狗是常见伴侣动物，也可承担看护、导盲和搜救等工作。", "下垂耳、短吻部和亲近人类的表情构成主要视觉特征。", "适合测试宠物动物、耳朵形状和英文 dog 查询召回。", "Find the dog image with floppy ears and a short muzzle.", "狗的小节介绍了哪些用途和外形特征？"),
            Item("rabbit", "兔子", "Rabbit", "兔子以跳跃移动和草食性为人熟知，常见于农场和宠物场景。", "长耳朵、浅色皮毛、小鼻子和圆润脸部是关键视觉线索。", "适合测试长耳动物和浅色毛发的图片召回。", "哪张动物图片展示长耳朵和浅色皮毛的兔子？", "兔子的小节如何描述长耳和皮毛？"),
            Item("panda", "熊猫", "Panda", "熊猫是中国代表性动物，以竹子为主要食物来源。", "黑白分明的毛色、黑眼圈和圆形耳朵非常突出。", "适合测试高对比黑白动物和中文熊猫查询召回。", "Find the black-and-white panda with dark eye patches.", "熊猫的小节说明了哪些颜色对比和生态特征？"),
            Item("elephant", "大象", "Elephant", "大象是大型陆生哺乳动物，具有复杂社会行为。", "灰色体色、大耳朵、长鼻子和象牙是典型视觉特征。", "适合测试大型动物、长鼻结构和灰色外观召回。", "检索灰色大耳朵和长鼻子的大象图片。", "大象的小节介绍了哪些局部结构？"),
            Item("lion", "狮子", "Lion", "狮子是大型猫科动物，常被视为草原生态中的顶级捕食者。", "雄狮浓密鬃毛、金棕色面部和强烈径向轮廓是视觉重点。", "适合测试鬃毛纹理、金棕色和猛兽类别召回。", "Which image shows a lion with a brown mane?", "狮子的小节如何描述鬃毛和生态角色？"),
            Item("penguin", "企鹅", "Penguin", "企鹅是不会飞的鸟类，多生活在南半球寒冷或海洋环境。", "黑白身体、橙色喙和直立姿态是典型图像线索。", "适合测试鸟类、黑白身体和姿态召回。", "查找黑白身体和橙色喙的企鹅图片。", "企鹅的小节说明了哪些鸟类和姿态特征？"),
            Item("owl", "猫头鹰", "Owl", "猫头鹰多在夜间活动，以敏锐听觉和视觉捕猎。", "大眼睛、短喙、圆形头部和耳羽轮廓非常突出。", "适合测试眼部区域、夜行鸟类和中文名称召回。", "Find the owl image with large round eyes.", "猫头鹰的小节如何描述眼睛和夜行特征？"),
            Item("fox", "狐狸", "Fox", "狐狸是机敏的小型犬科动物，常出现在森林和草地边缘。", "橙红色毛发、尖耳和白色胸脸区域是主要视觉线索。", "适合测试红棕色动物、尖耳和面部色块召回。", "检索橙红色毛发、尖耳和白色面部的狐狸。", "狐狸的小节介绍了哪些颜色和轮廓特征？"),
            Item("turtle", "乌龟", "Turtle", "乌龟以硬壳和缓慢移动为特点，生活在陆地或水域附近。", "绿色或棕色龟壳、伸出的头部和短足构成典型形象。", "适合测试壳体纹理、爬行动物和局部结构召回。", "Which image shows a turtle with a patterned shell?", "乌龟的小节如何描述龟壳和身体结构？"),
        ),
    ),
    Category(
        key="vehicles",
        title="多交通工具图片召回评测",
        old_dataset="synthetic-vehicles-multimodal-v1",
        image_dir="vehicles",
        items=(
            Item("car", "汽车", "Car", "汽车是道路上常见的私人交通工具，适合短途和城市出行。", "车身、车窗、车灯和四个车轮构成基本视觉结构。", "适合测试蓝色车身、车轮和英文 car 查询召回。", "检索蓝色汽车、车窗和两个可见车轮。", "汽车的小节介绍了哪些道路交通和外形特征？"),
            Item("bus", "公交车", "Bus", "公交车用于城市公共交通，能搭载较多乘客。", "长车身、成排车窗、较高车厢和醒目颜色是主要线索。", "适合测试大型车辆、公共交通和黄色车身召回。", "Find the yellow bus with long body and windows.", "公交车的小节如何描述公共交通用途？"),
            Item("train", "火车", "Train", "火车沿轨道运行，可承担城市通勤和长途运输。", "车头、车厢、轨道和横向延展结构是图像重点。", "适合测试轨道交通、蓝色车体和车厢结构召回。", "检索蓝色火车和轨道。", "火车的小节介绍了哪些轨道和运输特征？"),
            Item("airplane", "飞机", "Airplane", "飞机用于空中交通，适合远距离高速旅行。", "细长机身、机翼、尾翼和流线型轮廓是关键视觉线索。", "适合测试空中交通、机翼和英文 airplane 查询召回。", "Find the airplane with wings and fuselage.", "飞机的小节如何描述机翼和远距离用途？"),
            Item("ship", "轮船", "Ship", "轮船在水面航行，用于客运、货运或海上作业。", "船体、甲板、烟囱和水上轮廓有助于识别。", "适合测试水上交通工具和船体结构召回。", "检索有船体和烟囱的轮船。", "轮船的小节说明了哪些水上交通特征？"),
            Item("bicycle", "自行车", "Bicycle", "自行车依靠人力驱动，是轻便的个人交通工具。", "两个大轮、车架、车把和细长结构是核心视觉线索。", "适合测试双轮、车架和人力交通概念召回。", "Find the bicycle with two wheels and frame.", "自行车的小节如何描述双轮和人力驱动？"),
            Item("motorcycle", "摩托车", "Motorcycle", "摩托车以发动机驱动，比自行车速度更快、结构更厚重。", "两个车轮、车把、车座和发动机区域是主要线索。", "适合测试机动双轮交通工具召回。", "检索摩托车图片。", "摩托车的小节介绍了哪些机动结构？"),
            Item("ambulance", "救护车", "Ambulance", "救护车用于急救运输，常配有医疗标识和警示灯。", "白色车身、红色医疗十字和厢式车体是典型视觉特征。", "适合测试应急车辆和红十字标识召回。", "Find the ambulance with red medical cross.", "救护车的小节如何描述急救用途？"),
            Item("fire_truck", "消防车", "Fire Truck", "消防车用于火灾救援和应急处置，通常携带梯子和设备。", "红色大型车身、梯子和多个车轮是主要视觉线索。", "适合测试红色救援车辆和梯子结构召回。", "检索红色消防车和梯子。", "消防车的小节介绍了哪些救援装备？"),
            Item("subway", "地铁", "Subway", "地铁列车服务城市轨道交通，通常在地下或高架线路运行。", "正面车窗、车灯、轨道和列车头部构成识别重点。", "适合测试城市轨道交通和列车正面召回。", "Find the subway train front with tracks.", "地铁的小节如何描述城市轨道交通？"),
        ),
    ),
    Category(
        key="plants",
        title="多植物图片召回评测",
        old_dataset="synthetic-plants-multimodal-v1",
        image_dir="plants",
        items=(
            Item("rose", "玫瑰", "Rose", "玫瑰是常见观赏花卉，也常用于礼品和香氛。", "层叠红色花瓣、绿色茎和叶片是关键视觉线索。", "适合测试红色花朵、花瓣层次和英文 rose 查询召回。", "检索红色玫瑰和绿色茎叶。", "玫瑰的小节如何描述花瓣和用途？"),
            Item("sunflower", "向日葵", "Sunflower", "向日葵有向光性，种子可食用或榨油。", "黄色放射状花瓣和棕色圆形花盘非常显著。", "适合测试黄花瓣、圆形花盘和放射结构召回。", "Find the sunflower with yellow petals.", "向日葵的小节介绍了哪些花盘和用途？"),
            Item("bamboo", "竹子", "Bamboo", "竹子生长迅速，常用于建筑、器具和园林景观。", "绿色分节茎秆和细长叶片构成重复结构。", "适合测试分节结构、绿色茎秆和中文竹子查询召回。", "检索分节绿色竹子。", "竹子的小节如何描述茎秆和用途？"),
            Item("cactus", "仙人掌", "Cactus", "仙人掌适应干旱环境，能在茎中储存水分。", "厚实绿色茎、侧枝和刺状结构是典型视觉线索。", "适合测试干旱植物、绿色肉质茎和侧枝召回。", "Find the cactus with arms.", "仙人掌的小节说明了哪些干旱适应特征？"),
            Item("pine_tree", "松树", "Pine Tree", "松树是常绿针叶树，常见于山地和寒冷地区。", "层叠三角形树冠、针叶和棕色树干构成主要轮廓。", "适合测试常绿树、三角形树冠和针叶召回。", "检索三角形树冠的松树。", "松树的小节如何描述常绿和树冠？"),
            Item("lotus", "荷花", "Lotus", "荷花生长在水域环境，常与池塘和浮叶一起出现。", "粉色花瓣、黄色花心和宽大绿色浮叶是关键线索。", "适合测试水生植物、粉色花朵和荷叶召回。", "Find the pink lotus flower.", "荷花的小节介绍了哪些水生环境特征？"),
            Item("maple", "枫树", "Maple", "枫树叶片在秋季常呈红色或橙色，观赏价值高。", "掌状分裂叶形、红色叶片和尖裂轮廓非常突出。", "适合测试红色叶片、掌状叶形和英文 maple 查询召回。", "检索红色枫叶。", "枫树的小节如何描述叶片形状和季节？"),
            Item("tulip", "郁金香", "Tulip", "郁金香是球根花卉，常见于花园和切花场景。", "杯状花冠、直立花茎和宽叶是主要视觉特征。", "适合测试杯状花、直立茎和花卉类别召回。", "Find the tulip with cup-shaped petals.", "郁金香的小节介绍了哪些花冠和茎叶特征？"),
            Item("fern", "蕨类", "Fern", "蕨类植物通常不以花繁殖，常见于湿润阴凉环境。", "羽状复叶沿主轴成对展开，叶片细密。", "适合测试叶片重复结构和羽状形态召回。", "检索羽状蕨类叶片。", "蕨类的小节如何描述羽状复叶？"),
            Item("rice", "稻谷", "Rice", "稻谷是重要粮食作物，成熟后形成下垂稻穗。", "细长茎秆、金黄色谷粒和稻穗结构是主要线索。", "适合测试农作物、金色穗状结构和中文稻谷查询召回。", "Find the golden rice panicles.", "稻谷的小节介绍了哪些成熟谷粒特征？"),
        ),
    ),
    Category(
        key="tools",
        title="多工具图片召回评测",
        old_dataset="synthetic-tools-multimodal-v1",
        image_dir="tools",
        items=(
            Item("hammer", "锤子", "Hammer", "锤子用于敲击钉子、调整部件或进行简单拆装。", "金属锤头和长柄构成清晰的 T 形或 L 形轮廓。", "适合测试手工具、金属头部和木柄召回。", "检索锤子、金属锤头和木柄。", "锤子的小节如何描述结构和用途？"),
            Item("wrench", "扳手", "Wrench", "扳手用于拧动螺母和螺栓，是维修场景常见工具。", "开口夹持端、金属柄和弧形头部是主要视觉线索。", "适合测试金属工具、开口钳口和英文 wrench 查询召回。", "Find the wrench with open jaw.", "扳手的小节介绍了哪些夹持结构？"),
            Item("screwdriver", "螺丝刀", "Screwdriver", "螺丝刀用于拧紧或拆卸螺丝，常见于装配和维修。", "手柄、长金属杆和尖端构成细长轮廓。", "适合测试尖端工具、红色手柄和螺丝相关语义召回。", "检索螺丝刀和尖端。", "螺丝刀的小节如何描述手柄和尖端？"),
            Item("pliers", "钳子", "Pliers", "钳子可用于夹紧、弯折或剪切小型材料。", "两个手柄、铰接点和夹持钳口是关键结构。", "适合测试双手柄、铰链和夹持工具召回。", "Find the pliers with two handles.", "钳子的小节介绍了哪些夹持和铰接特征？"),
            Item("scissors", "剪刀", "Scissors", "剪刀用于裁剪纸张、布料或其他薄材料。", "两个圆形握环和交叉刀刃构成典型图像。", "适合测试交叉结构、握环和刀刃召回。", "检索交叉刀刃剪刀。", "剪刀的小节如何描述握环和刀刃？"),
            Item("tape_measure", "卷尺", "Tape Measure", "卷尺用于测量长度，外壳中收纳可伸缩尺带。", "黄色外壳和伸出的金属尺带是主要线索。", "适合测试测量工具、黄色壳体和尺带召回。", "Find the tape measure with metal tape.", "卷尺的小节介绍了哪些测量结构？"),
            Item("drill", "电钻", "Drill", "电钻是电动工具，用于钻孔或安装螺丝。", "机身、手柄、扳机区域和钻头形成明显工具轮廓。", "适合测试电动工具、钻头和蓝色机身召回。", "检索电钻和钻头。", "电钻的小节如何描述电动结构和用途？"),
            Item("brush", "刷子", "Brush", "刷子用于涂刷、清洁或表面处理。", "刷毛、金属箍和长柄是最重要的视觉结构。", "适合测试刷毛细节和手柄工具召回。", "Find the brush with bristles.", "刷子的小节介绍了哪些刷毛和手柄特征？"),
            Item("shovel", "铲子", "Shovel", "铲子用于挖掘、搬运土壤或清理材料。", "长柄和宽铲头形成明显的纵向工具轮廓。", "适合测试园艺工具、宽铲头和长柄召回。", "检索铲子和宽铲头。", "铲子的小节如何描述挖掘用途？"),
            Item("flashlight", "手电筒", "Flashlight", "手电筒用于照明，常在夜间或低光环境使用。", "筒身、发光端和光束方向构成关键视觉线索。", "适合测试照明工具和光束语义召回。", "Find the flashlight beam.", "手电筒的小节介绍了哪些照明结构？"),
        ),
    ),
    Category(
        key="foods",
        title="多食物图片召回评测",
        old_dataset="synthetic-foods-multimodal-v1",
        image_dir="foods",
        items=(
            Item("bread", "面包", "Bread", "面包由面粉烘焙而成，可作为早餐或主食。", "金棕色外皮、柔软内部和圆润烘焙轮廓是主要线索。", "适合测试烘焙食品、棕色外皮和英文 bread 查询召回。", "检索金棕色面包。", "面包的小节介绍了哪些烘焙外观和用途？"),
            Item("pizza", "披萨", "Pizza", "披萨由面饼、酱料、奶酪和配料烘烤而成。", "三角形切片、红色酱料、黄色奶酪和圆形配料是关键视觉线索。", "适合测试西式食物、三角切片和配料召回。", "Find the triangular pizza slice.", "披萨的小节如何描述切片和配料？"),
            Item("sushi", "寿司", "Sushi", "寿司由米饭、海苔和鱼肉或蔬菜等馅料组合而成。", "黑色海苔外圈、白色米饭和中心彩色馅料构成典型切面。", "适合测试日式食物、圆柱切面和英文 sushi 查询召回。", "检索寿司卷。", "寿司的小节介绍了哪些材料和切面特征？"),
            Item("dumpling", "饺子", "Dumpling", "饺子是常见中式食物，由面皮包裹馅料制成。", "半月形轮廓、浅色面皮和褶边是主要视觉线索。", "适合测试中式食物、褶边和中文饺子查询召回。", "Find the dumplings with folded edges.", "饺子的小节如何描述面皮和褶边？"),
            Item("burger", "汉堡", "Burger", "汉堡由面包、肉饼、蔬菜和奶酪等食材层叠组成。", "上下圆面包、多层夹馅和横向分层结构非常明显。", "适合测试分层食物、肉饼和英文 burger 查询召回。", "检索分层汉堡。", "汉堡的小节介绍了哪些分层食材？"),
            Item("salad", "沙拉", "Salad", "沙拉通常由蔬菜、水果或蛋白质食材混合而成。", "绿色叶菜、彩色配料和碗状容器是典型视觉线索。", "适合测试绿色蔬菜、碗中食物和健康食品召回。", "Find the bowl of salad.", "沙拉的小节如何描述配料和容器？"),
            Item("noodles", "面条", "Noodles", "面条是长条状主食，可搭配汤底、酱料或配菜。", "碗中弯曲长条、浅黄色面体和筷子或汤面结构是主要线索。", "适合测试碗装主食和长条形食物召回。", "检索碗中的面条。", "面条的小节介绍了哪些形状和食用方式？"),
            Item("cake", "蛋糕", "Cake", "蛋糕是甜点，常用于生日、庆祝和下午茶场景。", "奶油层、粉色或浅色糕体和蜡烛是关键视觉线索。", "适合测试甜点、蜡烛和庆祝语义召回。", "Find the birthday cake with candles.", "蛋糕的小节如何描述甜点和庆祝场景？"),
            Item("rice", "米饭", "Rice", "米饭由稻米蒸煮而成，是许多地区的主食。", "白色米粒聚集在碗中，形态细小且整体颜色均匀。", "适合测试白色主食、碗装食物和中文米饭查询召回。", "检索白米饭。", "米饭的小节介绍了哪些主食和米粒特征？"),
            Item("soup", "汤", "Soup", "汤由液体和配料组成，可作为正餐、前菜或补充水分的食物。", "碗中液体表面、彩色配料和圆形容器是主要视觉线索。", "适合测试液体食物、碗和配料召回。", "Find the bowl of soup.", "汤的小节如何描述液体和配料？"),
        ),
    ),
    Category(
        key="landmarks",
        title="多地标图片召回评测",
        old_dataset="synthetic-landmarks-multimodal-v1",
        image_dir="landmarks",
        items=(
            Item("great_wall", "长城", "Great Wall", "长城是中国古代防御工程，沿山脊和地形延伸。", "连续城墙、垛口和蜿蜒走势是最明显的视觉线索。", "适合测试中国地标、城墙结构和英文 Great Wall 查询召回。", "检索蜿蜒城墙和垛口。", "长城的小节如何描述城墙和历史地标特征？"),
            Item("eiffel_tower", "埃菲尔铁塔", "Eiffel Tower", "埃菲尔铁塔是法国巴黎代表性建筑，由金属结构组成。", "高耸塔身、金属桁架和宽阔塔脚构成标志性轮廓。", "适合测试欧洲地标、铁塔结构和英文 Eiffel Tower 查询召回。", "Find the Eiffel Tower lattice silhouette.", "埃菲尔铁塔的小节介绍了哪些金属结构？"),
            Item("pyramid", "金字塔", "Pyramid", "埃及金字塔是古代大型陵墓建筑，以几何外形著称。", "沙色石材、巨大三角形侧面和尖顶是主要视觉线索。", "适合测试古代建筑、三角形轮廓和沙漠色彩召回。", "检索沙色金字塔。", "金字塔的小节如何描述几何形状和古代建筑？"),
            Item("statue_of_liberty", "自由女神像", "Statue of Liberty", "自由女神像是美国纽约港的标志性雕像。", "绿色铜像、冠冕和高举火炬的姿态非常突出。", "适合测试雕像、火炬和美国地标语义召回。", "Find the Statue of Liberty with torch.", "自由女神像的小节介绍了哪些姿态和象征物？"),
            Item("taj_mahal", "泰姬陵", "Taj Mahal", "泰姬陵是印度著名陵墓建筑，以对称布局和白色大理石闻名。", "白色穹顶、对称塔楼和纪念性正立面是主要视觉线索。", "适合测试南亚地标、穹顶和对称结构召回。", "检索白色穹顶泰姬陵。", "泰姬陵的小节如何描述穹顶和对称结构？"),
            Item("sydney_opera", "悉尼歌剧院", "Sydney Opera House", "悉尼歌剧院是澳大利亚悉尼港边的表演艺术建筑。", "帆形屋顶、白色壳体和海港边界轮廓是关键视觉线索。", "适合测试现代建筑、帆形结构和英文 Sydney Opera House 查询召回。", "Find the sail-shaped opera house.", "悉尼歌剧院的小节介绍了哪些屋顶形态？"),
            Item("forbidden_city", "故宫", "Forbidden City", "故宫是中国明清皇家宫殿建筑群，具有中轴对称布局。", "红墙、黄色屋顶和宫殿式正立面是主要视觉特征。", "适合测试中国宫殿、红黄配色和中文故宫查询召回。", "检索红墙黄瓦故宫。", "故宫的小节如何描述红墙黄瓦和宫殿结构？"),
            Item("colosseum", "罗马斗兽场", "Colosseum", "罗马斗兽场是古罗马大型圆形竞技场遗迹。", "椭圆形外墙、连续拱门和石质立面构成典型视觉线索。", "适合测试古罗马建筑、拱门和英文 Colosseum 查询召回。", "Find the Colosseum arches.", "罗马斗兽场的小节介绍了哪些拱门和遗迹特征？"),
            Item("tower_bridge", "伦敦塔桥", "Tower Bridge", "伦敦塔桥跨越泰晤士河，是伦敦著名桥梁地标。", "两座塔楼、桥面和连接结构形成对称图像。", "适合测试桥梁、双塔结构和英文 Tower Bridge 查询召回。", "检索双塔桥梁。", "伦敦塔桥的小节如何描述双塔和桥面？"),
            Item("mount_fuji", "富士山", "Mount Fuji", "富士山是日本代表性自然地标，山体轮廓对称。", "锥形山体、雪冠和山脚轮廓是主要视觉线索。", "适合测试自然地标、雪顶山峰和英文 Mount Fuji 查询召回。", "Find Mount Fuji with snow cap.", "富士山的小节介绍了哪些山体和雪冠特征？"),
        ),
    ),
)


def yaml_scalar(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


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
        "本文档用于评测多模态检索系统能否根据文本查询召回对应图片 asset，以及根据语义问题召回对应文本小节 chunk。",
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
                f"检索提示：{item.zh}、{item.en}、{category.title}、图片、颜色、形状、局部特征、用途。",
                "",
            ]
        )
    (CORPUS_DIR / f"{category.key}.md").write_text("\n".join(lines), encoding="utf-8")


def copy_images(category: Category) -> None:
    source_dir = ROOT / "datasets" / category.old_dataset / "corpus" / "images" / category.image_dir
    if not source_dir.is_dir():
        source_dir = ROOT / "generated" / "deprecated-datasets" / "multimodal-gallery-v1" / category.old_dataset / "corpus" / "images" / category.image_dir
    if not source_dir.is_dir():
        raise FileNotFoundError(f"image source missing: {source_dir}")
    dest_dir = CORPUS_DIR / "images" / category.image_dir
    dest_dir.mkdir(parents=True, exist_ok=True)
    for item in category.items:
        src = source_dir / f"{item.slug}.png"
        if not src.is_file():
            raise FileNotFoundError(src)
        shutil.copy2(src, dest_dir / src.name)


def write_dataset_yaml() -> None:
    (DATASET_DIR / "dataset.yaml").write_text(
        "\n".join(
            [
                f"name: {DATASET}",
                "description: >",
                "  Synthetic multimodal retrieval dataset with category-level Markdown files,",
                "  local PNG image assets, and explicit asset/chunk recall targets.",
                "thresholds: {}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_targets_yaml() -> None:
    lines = ["assets:"]
    for category in CATEGORIES:
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
    for category in CATEGORIES:
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
    for category in CATEGORIES:
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


def move_old_datasets() -> None:
    deprecated_root = ROOT / "generated" / "deprecated-datasets" / "multimodal-gallery-v1"
    deprecated_root.mkdir(parents=True, exist_ok=True)
    for category in CATEGORIES:
        src = ROOT / "datasets" / category.old_dataset
        if not src.exists():
            continue
        dst = deprecated_root / category.old_dataset
        if dst.exists():
            suffix = 1
            while (deprecated_root / f"{category.old_dataset}.{suffix}").exists():
                suffix += 1
            dst = deprecated_root / f"{category.old_dataset}.{suffix}"
        shutil.move(str(src), str(dst))


def main() -> None:
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    for category in CATEGORIES:
        copy_images(category)
        write_markdown(category)
    write_dataset_yaml()
    write_targets_yaml()
    write_queries_yaml()
    move_old_datasets()
    print(f"wrote {DATASET_DIR}")


if __name__ == "__main__":
    main()

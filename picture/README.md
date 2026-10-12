# picture/ —— 奶龙梗图素材目录

把符合规范的奶龙梗图丢进这个目录，`card_gen.py` 会**按文件名语义角色**挑底图
（不是随机抽）。目录为空时自动回落到内置占位图，链路不会断。

---

## 〇、当前素材清单

| 文件 | 尺寸 | 语义角色 | 用在哪 |
|---|---|---|---|
| `nailong-01-burger.png` | 1600×900 | `burger` | 兜底 / 通用 |
| `nailong-02-spicy.png` | 1600×900 | `spicy` | 堡格 巨无霸辣王、椒香小钢炮 |
| `nailong-03-gentle.png` | 1600×900 | `gentle` | 堡格 温柔巨塔、云朵轻食家 |
| `nailong-04-feast.png` | 1600×900 | `feast` | 巨胃 / 大餐备选 |
| `nailong-05-lightmeal.png` | 1600×900 | `lightmeal` | 轻食备选 |
| `nailong-06-thrifty.png` | 1600×900 | `thrifty` | 消费等级「节俭度日」(< ¥25) |
| `nailong-07-freedom.png` | 1600×900 | `freedom` | 消费等级「吃堡自由」(¥25–40) |
| `nailong-08-hero.png` | 1600×900 | `hero` | 消费等级「豪情在天」(> ¥40) |
| `nailong-09-coupon.png` | 1600×900 | `coupon` | 每日领券 |
| `nailong-10-number.png` | 1600×900 | `number` | 到号提醒 |

**角色是怎么被识别的**：取文件名（不含扩展名）里出现的关键词。新增素材只要把角色词写进文件名
（如 `nailong-11-spicy-2.png`），就自动进入该角色的候选池——**不需要改代码**。
角色词表见 `scripts/card_gen.py` 的 `ROLE_KEYWORDS`。

**优先级**：`堡格 / 消费等级 → 角色列表`（见 `BOGE_ROLE` / `TIER_ROLE`），
取**第一个有素材的角色**，同角色多张时按名片名做确定性轮换（同一个人格每次抽到同一张）。

自检：

```bash
python scripts/card_gen.py --list-images          # 列出素材 + 识别到的角色
python scripts/fetch_pictures.py --scan           # 检查是否 16:9
python scripts/fetch_pictures.py --manifest       # 刷新 Demo 的素材清单
```

---

## 一、素材硬性规范（很关键）

| 项目 | 要求 | 原因 |
|---|---|---|
| 尺寸 | **1600 × 900**（严格 16:9） | 名片卡就是 1600×900，非 16:9 会被 `slice` 裁切 |
| 格式 | `.jpg` / `.png` / `.webp` | 会被 base64 内嵌进 SVG |
| 文件大小 | 建议 < 1.5 MB | 内嵌后 SVG 会变大，微信转发有体积感知 |
| 命名 | `nailong-01.jpg`、`nailong-saver.png` … | 无强制要求，便于你自己管理 |

### ⚠️ 唯一的构图约束：主体必须在上方 55%

名片底部 **y = 470 ~ 900** 会被浅色信息面板盖住（放名片名、堡格、仓库地址）。
所以梗图的**主体（奶龙）请放在画面上方 0 ~ 470 区域**，底部留出干净的背景。

- ✅ 奶龙在上方 2/3，底部是纯色/虚化背景
- ❌ 奶龙居中且巨大，头部压在 y=470 以下 → 会被面板挡掉

---

## 二、AI 生图提示词（可直接复制）

> 说明：奶龙是他人享有著作权的卡通形象。以下提示词用于**风格自研的原创黄龙角色**用途说明，
> 请自行确认素材来源与使用授权，本仓库不对素材版权负责。

### 通用基础提示词（中文）

```
一只圆润可爱的黄色小恐龙卡通形象，大头小身，白色大眼睛，憨憨的笑容，腮红，
扁平化矢量插画风格，粗描边，高饱和明黄色 #FFD84D + 奶油白背景，
角色位于画面上方三分之二处，底部三分之一为干净纯色留白，
横版 16:9 构图，画面尺寸 1600x900，无文字，无边框
```

### 通用基础提示词（English）

```
a chubby cute yellow baby dinosaur cartoon character, big head small body,
white oversized eyes, goofy smile, pink cheeks, flat vector illustration,
thick clean outlines, saturated yellow #FFD84D on cream background,
character placed in the upper two-thirds of the frame,
clean empty background on the bottom third, 16:9 landscape, 1600x900,
no text, no border
```

### 场景变体（把上面一段 + 下面一句拼起来用）

| 用途 | 追加提示词 |
|---|---|
| 抽卡 · 堡格名片 | `举着一只汉堡开心大笑，周围漂浮星星与闪光` / `holding a big burger, laughing, sparkles around` |
| 抽卡 · 辣党 | `嘴里喷出小火苗，头顶冒热气` / `breathing a tiny flame, steam above its head` |
| 抽卡 · 温柔党 | `抱着小毯子安静发呆，眼神温柔` / `hugging a little blanket, calm gentle eyes` |
| 抽卡 · 巨胃 | `桌上堆满汉堡薯条可乐，抱着大份套餐` / `a table piled with burgers, fries and cola` |
| 抽卡 · 轻食 | `拿着一根小小薯条小口吃，旁边一杯美式` / `nibbling a single fry, an americano beside` |
| 消费 · 节俭度日 | `掏出几枚硬币认真数，表情精打细算` / `counting a few coins seriously` |
| 消费 · 吃堡自由 | `一只手举汉堡，另一只手比耶，很开心` / `one hand with burger, other hand peace sign` |
| 消费 · 豪情在天 | `戴墨镜单手叉腰，气场全开，背景金色光效` / `wearing sunglasses, hands on hips, golden aura` |
| 每日领券 | `手里抓着一把优惠券像撒花一样` / `holding a fistful of coupons like confetti` |
| 到号提醒 | `举着一个发光的取餐号码牌` / `holding a glowing order-number board` |

### 负面提示词（Negative prompt）

```
文字, 水印, logo, 边框, 签名, 多余的手指, 畸形的脸, 真实照片质感, 暗色调, 复杂背景
text, watermark, logo, border, signature, extra fingers, deformed face, photorealistic, dark tone, busy background
```

---

## 三、导入素材

```bash
# 从本地文件夹批量导入（自动校验是否为 16:9）
python scripts/fetch_pictures.py --from-dir "D:/我的奶龙图"

# 从直链下载导入
python scripts/fetch_pictures.py --urls "https://xxx/a.jpg,https://xxx/b.png"

# 体检：列出目录里所有图，标出非 16:9 的
python scripts/fetch_pictures.py --scan

# 生成 Demo 用的素材清单
python scripts/fetch_pictures.py --manifest
```

导入后跑一次验证：

```bash
python scripts/card_gen.py --list-images
python scripts/card_gen.py --name "测试·巨无霸辣王奶龙" --out out/card-test.svg
```

打开 `out/card-test.html`，点「下载 PNG」看看合成效果。

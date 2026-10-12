---
name: mcd-nailong
display_name: 麦麦奶龙
display_name_en: McDonald's Nailong
description: "麦当劳中国 MCP 创意助手「麦麦奶龙」。三大能力：①每日自动领取全部优惠券并播报临期提醒；②「麦麦奶龙」汉堡抽卡——答题或读历史订单生成「堡格」与性格关键词，产出一张可直接发微信/QQ 的 16:9 奶龙名片；③「穷鬼预算锁」——给定预算/口味/就餐方式，在 calculate-price 上做组合试算并给出 Pareto 最优 3 套方案，支持改单、选门店、下单与到号提醒。当用户提到麦当劳、麦麦、点餐、领券、省钱、比价、优惠券、堡格、抽卡、奶龙、预算内吃饱、到号提醒等场景时使用。不适用于非麦当劳的餐饮点单、通用记账或与 MCP 无关的图片生成需求。"
description_zh: "麦当劳中国 MCP 创意助手「麦麦奶龙」。① 每日自动领取全部优惠券并播报临期提醒；② 汉堡抽卡——答题或读历史订单生成「堡格」与性格关键词，产出可直接发微信/QQ 的 16:9 奶龙名片；③ 穷鬼预算锁——给定预算、口味、就餐方式，在 calculate-price 上做组合试算并给出 Pareto 最优 3 套方案，支持改单、选门店、下单与到号提醒。"
description_en: "McDonald's China MCP creative assistant (Nailong). (1) Daily auto-claim of all available coupons with expiry alerts; (2) burger personality draw that turns a 10-question quiz or order history into a Boge archetype plus a shareable 16:9 card; (3) budget lock that solves Pareto-optimal meal bundles under a hard budget cap via calculate-price, with cart editing, store selection, ordering and pickup-ready reminders."
version: 1.0.0
author: Perry233-TianYupeng
category: office
allowed-tools: ["Bash(python *)", "scripts/python"]
user-invocable: true
---

# 麦麦奶龙 · 麦当劳 MCP 创意助手

基于麦当劳中国官方 MCP Server（`https://mcp.mcd.cn`，Streamable HTTP）构建。
**所有价格、券、活动以 MCP 实时查询为准**，本项目不硬编码任何价格。

---

## 一、前置条件

1. **MCP Token**：在 <https://open.mcd.cn/mcp> 手机号登录 → 控制台激活 → 复制 Token。
2. **环境变量**：Token 只允许放环境变量，**绝不要写进代码或提交到仓库**。

   ```bash
   # Windows
   setx MCD_MCP_TOKEN "你的Token"
   # macOS / Linux
   export MCD_MCP_TOKEN="你的Token"
   ```
3. 依赖：**仅需 Python 3.8+ 标准库**，无需 pip 安装任何包。
4. 无 Token 时可加 `--mock` 用内置假数据跑通全流程（用于演示与验证）。

> Token 仅支持中国大陆手机号；服务限流 600 次/分钟/token；不支持 WebSocket。

---

## 二、能力一：每日自动领取全部优惠券

**触发**：用户说「帮我领券」「今天有什么券」「每日领券」「有什么活动」。

```bash
python scripts/daily_coupons.py                 # 领取 + 输出战报
python scripts/daily_coupons.py --dry-run       # 只看有什么券，不实际领
python scripts/daily_coupons.py --json          # 结构化输出，便于二次加工
python scripts/daily_coupons.py --force         # 忽略当日幂等保护
```

调用链：`now-time-info` → `campaign-calendar` → `available-coupons` → `auto-bind-coupons` → `my-coupons`。

输出内容：今日活动、本次领到几张、卡包总览、**3 天内过期提醒**、近期活动预告。

**幂等**：默认当天只跑一次，状态记录在 `scripts/.mcd_state.json`，避免重复请求触发限流。

**做成定时任务**：用 WorkBuddy 的自动化能力挂一个每天早上 9:00 的定时任务，prompt 写
「运行 scripts/daily_coupons.py 并把战报念给我听」，即可实现真正的「每日自动领券」。

---

## 三、能力二：麦麦奶龙 · 汉堡抽卡

**触发**：用户说「抽卡」「测测我的堡格」「我是哪种麦当劳人格」「帮我抽个奶龙」。

### 3.1 两条输入路径

```bash
# 路径 A：答题（10 题 = 麦当劳 5 : 日常 5）
python scripts/quiz_engine.py --answers 1A,2B,3A,4C,5B,6C,7A,8A,9A,10D --out out/quiz.json

# 交互式答题（终端里逐题问用户）
python scripts/quiz_engine.py --interactive --out out/quiz.json

# 路径 B：不想答题，直接读历史订单反推
python scripts/quiz_engine.py --history --out out/quiz.json
```

**Agent 交互规范**：如果用户不想在终端答题，**由你（Agent）直接逐题询问**，收集到
`{题号: 选项}` 后拼成 `--answers` 传入。题目原文见 `scripts/quiz_data.json`。

### 3.2 产出规则（必须严格遵守）

| 字段 | 规则 |
|---|---|
| 四轴 | 辣度（辣党/温柔党）、食量（巨胃/轻食）、决策（果决/纠结）、社交（组队/独食） |
| **堡格** | 基础名（4 选 1）× 修饰后缀（4 选 1）= 16 型，见 `scripts/mcd_naming.py::BOGE_BASE / BOGE_SUFFIX` |
| **性格关键词** | 从日常题得分取 Top-2，词库 12 个（省钱天才／深夜活跃／计划控…） |
| **名片名** | 格式固定为 `{性格}+{堡格}+奶龙`，例如 `省钱天才·巨无霸辣王·单人成军奶龙` |
| 推荐套餐 | 按四轴规则从当店菜单里挑，再用 `calculate-price` 核价 |

### 3.3 生成名片卡

```bash
python scripts/card_gen.py --quiz-result out/quiz.json --out out/card-quiz.svg
```

产出两个文件：
- `out/card-quiz.svg` —— 1600×900（**严格 16:9**）自包含 SVG，梗图以 base64 内嵌，单文件可传。
- `out/card-quiz.html` —— 打开后点「下载 PNG」，在浏览器端用 canvas 导出图片，**微信 / QQ / 朋友圈 / QQ 空间可直接发送**。

**版式约定**：梗图**满幅不裁切**；底部 y=470~900 是浅色信息面板，放名片名 / 堡格 / 推荐套餐；
**页脚用浅色小字写明开源仓库地址**（`--repo-url` 可改）。

**素材**：`picture/` 下的图片按**文件名语义角色**匹配，不是随机抽——

| 名片类型 | 角色优先级 | 对应素材 |
|---|---|---|
| 巨无霸辣王 / 椒香小钢炮 | `spicy` → `feast` | `nailong-02-spicy.png` |
| 温柔巨塔 / 云朵轻食家 | `gentle` → `feast` | `nailong-03-gentle.png` |
| 消费等级 节俭度日 | `thrifty` → `burger` | `nailong-06-thrifty.png` |
| 消费等级 吃堡自由 | `freedom` → `burger` | `nailong-07-freedom.png` |
| 消费等级 豪情在天 | `hero` → `burger` | `nailong-08-hero.png` |

- 取**第一个有素材的角色**，找不到才顺延；同角色多张时按名片名做确定性轮换。
- 可用 `--role spicy` 强制指定，或 `--image <路径>` 直接指定文件。
- `python scripts/card_gen.py --list-images` 会列出每张素材的尺寸与识别到的角色。
- 目录为空时回落内置占位图，链路不会断。素材规范与 AI 生图提示词见 `picture/README.md`。

---

## 四、能力三：穷鬼预算锁 —— “我只有 25 块，吃饱”

**触发**：用户说「25 块能吃什么」「预算内吃饱」「帮我省着点」「凑个最划算的」。

### 4.1 求解

```bash
python scripts/budget_solver.py --budget 25 --taste "辣,鸡"
python scripts/budget_solver.py --budget 40 --taste "牛" --mode delivery --store S002
python scripts/budget_solver.py --budget 25 --taste "辣,鸡" --mock   # 无 Token 离线演示
```

- `--taste`：逗号分隔；`-` 前缀表示**排除**（如 `--taste "-素"`）。支持：辣/不辣/鸡/牛/鱼/素/甜/冷/热/量足
- `--mode`：`dine_in`（到店）/ `take_out`（外带）/ `delivery`（麦乐送）

**算法**（不是简单比价）：
1. 拉菜单 → 主品类按口味严格过滤，配餐只按排除项过滤
2. 生成候选组合（单品 / 汉堡+小食 / 汉堡+饮料 / 汉堡+小食+饮料 / 套餐）
3. 本地启发式打分 = 0.45×口味匹配 + 0.25×单位价格饱腹度 + 0.30×满足度 + 组合丰富度
4. 候选池同时保「高分 / 最低预估实付 / 最高性价比 / **每 5 元价格档代表**」四个方向
5. 只把最有希望的 ≤24 个候选交给 MCP `calculate-price` 复核（控调用量）
6. 在 (实付价 ↑, 满足度 ↑) 上求 **Pareto 前沿**，输出 **3 套方案**：
   **极致省钱 / 性价比之王 / 最满足**；前沿不足 3 点时用次优可行解补齐并标注「备选方案」

### 4.2 消费等级（生成名片用）

| 实付金额 | 等级 | 文案 |
|---|---|---|
| < ¥25 | **节俭度日** | 钱要花在刀刃上，吃饱是唯一 KPI。 |
| ¥25 – 40 | **吃堡自由** | 想加薯条就加薯条，这就是自由的味道。 |
| > ¥40 | **豪情在天** | 点单不看价的快乐，你值得拥有。 |

### 4.3 改单 → 选门店 → 下单 → 支付 → 到号提醒

```bash
# 用户可在推荐方案上自由增删菜品，复核价格
python scripts/budget_solver.py --items B004:1,S001:1,D001:1 --budget 40

# 查附近门店（选店，同时缓存 beCode）
python scripts/order_flow.py stores --keyword 南京东路

# 试算
python scripts/order_flow.py price --store S001 --items B004:1,S001:1

# 创建订单（必须带 --yes 或在交互终端确认）—— 只生成「待支付」订单
python scripts/order_flow.py create --store S001 --items B004:1,S001:1 --yes

# 取支付链接（本工具不会替你付款）
python scripts/order_flow.py pay --order MO12345678 [--open]

# 付款成功后再蹲号
python scripts/order_flow.py watch --order MO12345678 --interval 8 --timeout 300

# 一条龙：下单 +（付款后）蹲号
python scripts/order_flow.py order --store S001 --items B004:1,S001:1 --yes --watch
```

到号提醒机制：轮询 `query-order`，状态变为 `READY`（餐品已就绪）时打印醒目横幅、
播放系统提示音（Windows `winsound`）、打印取餐号。订单会记录到 `scripts/.mcd_orders.json`。
若订单仍是**待支付**，`watch` 会直接提示付款链接与剩余时间——待支付订单永远不会进入制作。

### 4.4 支付说明（务必向用户讲清）

| 问题 | 答案 |
|---|---|
| `create-order` 会扣款吗？ | **不会。** 它只生成一笔「待支付」订单，返回 `payH5Url` 与 `payId` |
| 那什么时候扣钱？ | 用户**自己打开 `payH5Url` 并完成支付**时。本项目不代付、不托管支付凭据 |
| `payH5Url` 长什么样？ | 2026-04 起已改为**扫码支付页**：`https://m.mcd.cn/mcp/scanToPay?orderId=...`，不再提供网页收银台 |
| 不付会怎样？ | 订单在 `leftPaySecond` 倒计时（约 15 分钟）结束后**自动取消**，不会扣款 |
| 能重复下单吗？ | 可以，但会留下多笔待支付订单。请先确认前一单状态，别刷单 |

**Agent 行为规范**：向用户汇报下单结果时，必须同时给出**支付链接**和**"本工具不会扣款、需你自行付款"**这两条信息，不得只报"下单成功"。

### 4.5 官方入参契约（与上层脚本解耦的关键）

`calculate-price` / `create-order` 的官方入参不是 `storeCode + items` 这么简单，必须带：

| 字段 | 取值 | 来源 |
|---|---|---|
| `storeCode` | 门店编码 | `query-nearby-stores` |
| `beCode` | 门店 BE 编码 | **只能来自门店接口**，不可凭空生成；本项目自动缓存到 `scripts/.mcd_stores.json` |
| `orderType` | 到店/外带 = 1，麦乐送 = 2 | 由 `--mode` 推导 |
| `beType` | 1=到店取餐，2=麦乐送，5=得来速，6=团餐 | 由 `--mode` 推导 |
| `takeWayCode` | 取餐方式码 | `calculate-price` 的返回，`create-order`（到店）必填 |
| `addressId` | 配送地址 ID | `delivery-query-addresses`，`create-order`（麦乐送）必填 |
| `items[]` | `[{"productCode": "...", "quantity": 1}]` | 字段名是 **productCode + quantity**，不是 mealCode + qty |

脚本内部统一用 `{mealCode|code|productCode, qty|quantity}` 描述商品，
由 `mcd_schema.build_items()` 转换成官方格式——**改字段只需改这一个函数**。

### 4.6 下单后生成消费名片

```bash
python scripts/card_gen.py --budget-pay 28.0 --burger "双层吉士中套餐" --out out/card-budget.svg
```

名片名格式固定为 `{消费等级}+{汉堡名}+奶龙`，例如 `吃堡自由·双层吉士中套餐奶龙`。
规则与抽卡名片一致（16:9、底部信息面板、页脚浅色仓库地址、可转发微信/QQ）。

---

## 五、输出格式（Agent 必须遵守）

三条能力各有固定的输出契约，**不要自由发挥**：

| 能力 | 必须包含 | 禁止 |
|---|---|---|
| 每日领券 | 今日活动条数、本次领到张数、卡包总数、**临期（3 天内）券清单**、近期活动预告 | 只回一句"已领取" |
| 抽卡 | 四轴文字（辣度/食量/决策/社交）、**性格关键词 Top-2**、**堡格全名**、推荐套餐与实付、**名片名**（`{性格}+{堡格}+奶龙`）、名片文件路径 | 只给堡格不给名片名，或漏掉性格关键词 |
| 预算锁 | 枚举数/可行数/前沿数、**3 套方案**（标签 + 菜品 + 实付 + 满足度 + 每元饱腹 + 消费等级）、改单命令示例 | 只给一套方案，或给出超预算方案 |
| 下单 | 订单号、状态、**支付链接**、**"本工具不会扣款"提示**、下一步命令 | 报"下单成功"却不说支付与不扣款 |
| 报错 | 错误码、可能原因、**下一步怎么修** | 只抛异常堆栈 |

名片的输出格式是**两个文件**：`out/xxx.svg`（自包含）与 `out/xxx.html`（打开可导出 PNG）。
向用户交付时两个路径都要给出，并说明"HTML 里点下载 PNG 即可发微信 / QQ"。

---

## 六、安全与合规（硬性约束）

1. **下单必须确认**：任何写操作（下单、领券）都要用户显式同意。CLI 层用 `--yes` 或交互确认，
   本项目**永远不会静默下单**，也**不会代替用户付款**。
2. **Token 只走环境变量**：`MCD_MCP_TOKEN`。`mcp-config.example.json` 里只有 `${MCD_MCP_TOKEN}` 占位符。
3. **不硬编码价格**：菜单、券、活动全部实时查询。
4. **素材版权**：`picture/` 内的奶龙相关素材由使用者自行确认授权，本仓库不对素材版权负责。
5. **非官方产品**：本项目为大赛参赛作品，非麦当劳官方产品。
6. **文件编码**：所有文本文件一律 UTF-8 **不带 BOM**。
   ⚠️ 不要用 PowerShell 的 `Get-Content` / `Set-Content` 改这些文件——默认 ANSI(GBK) 解码会把中文
   变成不可逆乱码。用 `python tools/fix_bom.py` 体检，`python tests/selfcheck.py` 里也有编码守卫。

---

## 七、文件结构

```
├── SKILL.md                    # 本文件：Skill 定义
├── README.md                   # 项目介绍 / 安装 / 使用示例 / 目标用户
├── MCP_INTEGRATION.md          # MCP 接入说明（用了哪些 tool、调用流程、业务价值）
├── SUBMIT_CHECKLIST.md         # 提交前自检清单
├── mcp-config.example.json     # 脱敏配置示例（只含环境变量占位符）
├── package.json                # 仅用于跑 Demo 冒烟测试
├── CONTEST_DECLARATION.md      # 参赛声明（官方原文，需替换为官方文件）
├── workbuddy.md                # WorkBuddy 专项奖励：完整开发对话记录
├── picture/
│   ├── README.md               # 素材规范 + AI 生图提示词（中英双语 + 负面提示词）
│   └── nailong-01..10-*.png    # 10 张 1600×900 素材，文件名即语义角色
├── scripts/
│   ├── mcd_mcp.py              # MCP 客户端（Streamable HTTP + JSON-RPC，零依赖）
│   ├── mcd_schema.py           # 字段与官方入参契约层
│   ├── mcd_naming.py           # 命名体系：堡格表 / 性格词库 / 消费等级 / 名片命名
│   ├── mock_data.py            # 离线假数据（无 Token 也能跑通全流程）
│   ├── daily_coupons.py        # 能力一
│   ├── quiz_engine.py          # 能力二（抽卡）
│   ├── quiz_data.json          # 10 道题（麦当劳 5 : 日常 5）
│   ├── card_gen.py             # 名片卡生成（SVG + HTML，1600×900）
│   ├── budget_solver.py        # 能力三（Pareto 求解）
│   ├── order_flow.py           # 下单闭环 + 支付指引 + 到号提醒
│   └── fetch_pictures.py       # 素材导入 / 16:9 体检 / 生成 Demo 清单
├── demo/
│   ├── index.html              # 可交互 Demo（离线可跑，三大能力全流程）
│   └── picture-manifest.js     # 素材清单（由 fetch_pictures.py --manifest 生成）
├── docs/                       # README 用的界面预览图（平铺，不能建子目录）
├── tools/                      # 开发/文档工具，不参与技能运行时
│   ├── make_previews.py        #   生成矢量界面预览图
│   ├── make_screenshots.py     #   用本机 Chrome 生成真实截图 PNG
│   └── fix_bom.py              #   编码体检（去 BOM / 查乱码）
└── tests/
    ├── selfcheck.py            # 一键自检：34 项，无需 Token（先跑这个）
    └── demo-smoke.cjs          # Demo 冒烟测试（jsdom）
```

> ⚠️ 平台**只支持两级目录**（`根/一级子目录/文件`）。所以预览图平铺在 `docs/` 下，
> **不能**放 `docs/images/`；打包前还必须清掉 `__pycache__`（它会造成三层嵌套）。

---

## 八、常见问题

| 现象 | 处理 |
|---|---|
| `缺少 MCP Token` | 确认已 `setx MCD_MCP_TOKEN`，并**重开终端** |
| HTTP 401 | Token 无效/过期/未提供，回 <https://open.mcd.cn/mcp> 重新激活 |
| HTTP 429 | 触发限流（600 次/分钟/token），客户端已内置指数退避重试；也可降低候选复核数量 |
| 下单报参数缺失 | 检查 `beCode` / `orderType` / `beType` / `takeWayCode` 是否齐（见 4.5 契约表）；`order_flow.py stores` 可刷新 beCode 缓存 |
| 麦乐送下单失败 | 需要 `addressId`，来自 `delivery-query-addresses`；可用 `--address-id` 手动指定 |
| 下单后一直"待支付" | 正常——**必须用户自己打开 `payH5Url` 付款**，本工具不代付 |
| 门店信息如何获得 | 门店/storeCode/beCode 必须来自 `query-nearby-stores` 或 `delivery-query-addresses`，不可凭空生成 |
| 名片 PNG 导不出来 | 浏览器同源限制，改为长按图片保存或直接截图；或把素材放进 `picture/` 后用 CLI 生成 |
| 中文变成乱码 | 用 PowerShell `Get-Content/Set-Content` 改过文件，**不可逆**。见第六节第 6 条 |
| 菜单字段解析不到 | 只改 `scripts/mcd_schema.py` 的字段映射，上层无需改动 |

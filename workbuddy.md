# WorkBuddy 开发对话记录

> 本项目全程使用 **WorkBuddy** 辅助开发，用于申请大赛的 WorkBuddy 专项奖励。
>
> 说明：本文件是开发过程的**结构化记录**；官方要求的「完整开发对话」原始导出
> （MD 格式）请在本文件末尾 **附加** 后再提交，两份内容合起来即为完整材料。

---

## 一、开发环境

| 项目 | 值 |
|---|---|
| 开发工具 | WorkBuddy（Agent 模式） |
| 操作系统 | Windows |
| Python | 3.13（仅用标准库，零第三方依赖） |
| Node.js | 22（仅用于 Demo 的 jsdom 冒烟测试） |
| 会话起点 | 2026-10-12 |
| 会话主题 | 麦当劳 MCP 创意 Skill 开发（Scene: Skill 开发） |

## 二、开发过程时间线

### 阶段 0 · 赛事调研

1. 检索「WorkBuddy 麦当劳 M-China MCP 创意 skill 活动」，确认赛事信息：
   - 名称：麦当劳程序员创意开发大赛（M-CODE），金拱门（中国）主办，WorkBuddy 为合作伙伴
   - 时间：2026-10-09 10:30 — 10-25 23:59；奖品兑换截止 11-14
   - **排名依据：GitHub 公开 Star 数**（Star=0 不进榜）
   - 提交：个人公开仓库 + 官方活动页 Issue 模板报名
   - 必交材料：`README.md`、`CONTEST_DECLARATION.md`（官方原文不可改）、`MCP_INTEGRATION.md`、`workbuddy.md`
2. 抓取麦当劳 MCP 开放平台（<https://open.mcd.cn/mcp>）与社区已有作品，梳理出 14+ 个可用 Tool
3. 盘点社区已有作品（麦门省钱助手、mcd-cn-assistant、mcdonalds-mcp 等），确认
   **「单纯比价/省钱」赛道已饱和**，据此调整差异化方向

### 阶段 1 · 需求确认与方案设计

需求（用户给定）：

1. 每日自动领取全部优惠券
2. 「麦麦奶龙」汉堡抽卡：答题（麦当劳题 : 日常题 = 5 : 5）或读历史订单 → 生成「堡格」+ 性格关键词 + 随机奶龙卡片，命名为 `{性格}+{堡格}+奶龙`，16:9 梗图，支持微信/QQ 转发，页脚浅色字写仓库地址
3. 穷鬼预算锁：预算 + 口味 + 就餐方式 → `calculate-price` 上做组合试算 → Pareto 最优 3 套方案；下单后生成 `{消费等级}+{汉堡名}+奶龙` 名片；支持改单、选门店、下单、到号提醒

技术方案定稿：

- MCP 客户端手写（标准库 `urllib` + JSON-RPC 2.0 + Streamable HTTP），**零依赖**
- 环境探测：沙箱内 **PyPI 不可达**，Pillow 装不上 → 改为
  **Python 生成自包含 SVG + 浏览器端 canvas 导出 PNG**，彻底去掉二进制依赖
- 图片站反爬（百度图片返回 `Forbid spider access`）→ 改为
  **占位图 + 生图提示词规范 + 一键导入脚本** 方案，保证链路可跑

### 阶段 2 · 增量实现与验证

| # | 交付 | 验证方式 | 结果 |
|---|---|---|---|
| 1 | `scripts/mcd_mcp.py` MCP 客户端 | `--mock` 调 `list` / `ping` | 通过 |
| 2 | `scripts/mock_data.py` 离线假数据（覆盖 14 个 Tool） | 全脚本 `--mock` 跑通 | 通过 |
| 3 | `scripts/mcd_schema.py` 字段兼容层 | 被 1/3/4 调用 | 通过 |
| 4 | `scripts/daily_coupons.py` 每日领券 | `--mock` / `--dry-run` | 输出 6 张券战报，5 次调用 |
| 5 | `scripts/mcd_naming.py` 命名体系 | 被 6/7/8 调用 | 通过 |
| 6 | `scripts/budget_solver.py` Pareto 求解 | 3 组参数回归 | 通过 |
| 7 | `scripts/quiz_data.json` + `quiz_engine.py` 抽卡 | 答题 / 历史订单双路径 | 通过 |
| 8 | `scripts/card_gen.py` 名片卡（SVG + HTML） | 生成并检查版式坐标 | 通过 |
| 9 | `scripts/fetch_pictures.py` 素材导入 / 16:9 体检 / manifest | `--scan` / `--manifest` | 通过 |
| 10 | `scripts/order_flow.py` 下单闭环 | `stores`→`price`→`create`→`watch` | 蹲号 20s 后播报取餐号 |
| 11 | `demo/index.html` 可交互 Demo | jsdom 冒烟测试 | 见下 |
| 12 | `tests/demo-smoke.cjs` 自动化测试 | 6 组断言 | **全部通过** |

### 阶段 3 · 测试驱动的关键 Bug 修复

用 jsdom 真实加载 Demo 跑测试，抓到并修复了 2 个真实缺陷：

**Bug 1｜Pareto 前沿退化成单点**
- 现象：预算 25 元时只输出 1 套方案，`极致省钱` 之外没有备选
- 定位：候选池「按分数取 Top-18」——高分几乎都属于大套餐（满足度权重 0.30），
  便宜的小组合在预筛阶段就被淘汰，导致 `calculate-price` 从未复核它们
- 修复：
  1. 候选池改为**四方向取样**：高分 16 / 每 5 元价格档代表 8 / 最低预估实付 8 / 最高性价比 6，去重后上限 30
  2. 前沿点不足 3 点时，用次优可行解补齐并标注「备选方案」
- 影响文件：`scripts/budget_solver.py`、`demo/index.html`（两端逻辑保持同构）

**Bug 2｜测试断言过严**
- 现象：预算 15 元时数学上前沿只有 1 个点，补齐后标签重复为「备选方案」，断言唯一性失败
- 修复：断言改为「方案数 = 3 且**菜品组合互不重复**且全部满足实付 ≤ 预算」

修复后回归：`demo-smoke.cjs` 6/6 组全部通过，Python 端 `budget_solver.py` 同步验证通过。

### 阶段 3b · 合规闸门 + 下单契约审计（第二轮）

对交付物做了一次「Skill 合规 + 设备鲁棒性 + 支付链路」的专项审计，又抓出 4 个真实缺陷：

**Bug 3｜下单入参契约与官方文档不一致（最严重）**
- 现象：原实现向 `calculate-price` / `create-order` 传的是
  `{"storeCode", "items":[{"mealCode","qty"}], "diningMode"}`
- 定位：查证官方文档（<https://open.mcd.cn/mcp/doc>）后确认官方契约是
  `storeCode + beCode + orderType + beType + items[{"productCode","quantity"}]`，
  且到店 `create-order` 必填 `takeWayCode`（来自算价返回）、麦乐送必填 `addressId`
- 影响：**照原样调用真实服务会直接报参数缺失，整条下单链路走不通**
- 修复：
  1. `mcd_schema.py` 新增官方契约层：`build_items()` / `order_params()` / `MODE_TO_ORDER_TYPE` / `MODE_TO_BE_TYPE`
  2. `mcd_mcp.py` 新增 `store_context()`：自动获取并缓存 `beCode` 到 `scripts/.mcd_stores.json`
  3. `calculate_price` / `create_order` 改为按官方契约组装，支持 `take_way_code` / `address_id` / `remark`
  4. `order_flow.py` 新增 `pay` 子命令与自动 `addressId` 解析
  5. `mock_data.py` 同步为官方字段结构，保证离线可验证

**Bug 4｜支付链路说明缺失，且与现状不符**
- 定位：`create-order` **不会扣款**，只生成「待支付」订单并返回 `payH5Url`；
  2026-04 起支付链接已从网页收银台改为**扫码支付页** `https://m.mcd.cn/mcp/scanToPay?orderId=...`；
  未支付订单在 `leftPaySecond`（约 15 分钟）后自动取消
- 修复：CLI 增加显式「不扣款」提示；`watch` 遇到待支付状态改为**主动提示付款链接与倒计时**
  （此前会一直静默轮询到超时）；README / SKILL / MCP_INTEGRATION 补齐支付说明

**Bug 5｜`__pycache__` 触发「目录层级超限」**
- 现象：合规闸门报 BLOCKER `S7 包内目录层级超限`
- 定位：`python -m compileall scripts` 生成 `scripts/__pycache__/*.pyc`，
  在包内深度为 **2 层**，命中平台「仅支持两级目录」校验；
  **本地文件系统与 PyYAML 都静默不报**
- 修复：打包前清理，并写入 `SUBMIT_CHECKLIST.md` 作为必做步骤

**Bug 6｜SKILL.md frontmatter 字段不全（BLOCKER×5 + MAJOR×1）**
- 现象：闸门报 F1（缺 `description_zh` / `description_en` / `version` / `author`）、
  F7（author 为空占位）、P3（有 `scripts/` 但未声明 `allowed-tools`）
- 修复：补齐 9 个稳定字段（含 `display_name` / `display_name_en` / `category` /
  `allowed-tools` / `user-invocable`），并补写「输出格式」章节

**设备鲁棒性加固**：
- `demo/index.html`：模态框 `position:absolute` → `fixed`（原先在长页面里不会停在视口中间）；
  新增 720px / 400px 两档媒体查询；`navigator.clipboard` 增加 `execCommand` 降级
  （`file://` 与非安全上下文下 clipboard 不可用会直接抛错）
- `card_gen.py` 生成的 HTML：补 `<meta name="viewport">`（原先手机打开会按 980px 渲染导致整页缩放）
- `.gitignore` 放开 `demo/picture-manifest.js`，避免 clone 后 `<script src>` 404

**闸门结果**：`audit.py --profile upload` → **等级 A · 97 分 · BLOCKER 0 · MAJOR 0 · MINOR 1**
（唯一 MINOR 是本地工作区目录名 `McMCP` 与 `name: mcd-nailong` 不一致，线上仓库命名为 `mcd-nailong` 即消除）

### 阶段 4 · 文档与参赛材料

- `SKILL.md`（Skill 定义，Agent 可直接照做）
- `README.md`（项目介绍 / 安装 / 使用示例 / 目标用户）
- `MCP_INTEGRATION.md`（MCP Server、Tool 清单、调用流程、业务价值、工程取舍）
- `mcp-config.example.json`（脱敏，仅 `${MCD_MCP_TOKEN}` 占位符）
- `.gitignore`（凭据与运行时状态不入库）
- `SUBMIT_CHECKLIST.md`（提交前自检清单）

## 三、WorkBuddy 在本项目中的具体作用

| 环节 | WorkBuddy 做了什么 |
|---|---|
| 赛事调研 | 检索并交叉核对赛事规则、时间、评奖方式与必交材料清单 |
| 平台能力盘点 | 抓取 MCP 开放平台与社区作品，整理出 14+ 个可用 Tool 与字段形态 |
| 竞品差异化 | 识别出「比价/省钱」赛道已饱和，推动方案转向「时间维度运营 + 人格化传播」 |
| 环境排障 | 探测出 PyPI 不可达、图片站反爬，据此改掉两处技术选型，避免后期返工 |
| 编码 | 生成全部 12 个脚本与 Demo，保持两端求解逻辑同构 |
| 测试 | 编写并运行 jsdom 冒烟测试，**发现并修复 2 个真实缺陷** |
| 文档 | 产出 5 份参赛材料 |

## 四、关键决策记录（含被否决的方案）

| 决策 | 采纳 | 否决的替代方案与原因 |
|---|---|---|
| 名片卡渲染 | Python 出 SVG + 浏览器 canvas 导出 PNG | Pillow 出 PNG —— 沙箱 PyPI 不可达，且会给评委增加安装成本 |
| 名片版式 | 梗图**满幅 16:9 不裁切** + 底部信息面板 | 左图右文 —— 16:9 梗图会被裁成约 1:1，破坏梗图本体 |
| 素材方案 | 占位图 + 提示词规范 + 导入脚本 | 爬取网络奶龙图 —— 站点反爬，且版权归属不清 |
| 候选池取样 | 四方向（高分/分档/低价/性价比） | 单一按分数 Top-N —— 实测会让前沿退化成单点 |
| 订阅消息推送 | 本地轮询 + 声音提醒 | 微信模板消息 —— 需公众号资质与用户 openid，超出 MCP 能力边界 |
| 下单入参 | 严格按官方契约（beCode/orderType/beType/productCode+quantity） | 只传 storeCode + items —— 实测会报参数缺失，链路走不通 |
| 支付实现 | 只生成待支付订单 + 展示官方支付链接 | 任何形式的代付 / 托管支付凭据 —— 违反平台规则且有资金风险 |
| `beCode` 来源 | 运行时从 `query-nearby-stores` 取并缓存 | 写死常量 —— 不同门店 beCode 不同，且属于服务端数据不可臆造 |

---

## 五、附：完整开发对话原始导出

> 请在此处粘贴 WorkBuddy 导出的完整对话记录（Markdown 格式）。
> 导出方式：WorkBuddy 会话右上角菜单 → 导出对话 / 复制为 Markdown。

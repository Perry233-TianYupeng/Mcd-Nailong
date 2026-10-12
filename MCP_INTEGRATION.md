# MCP 接入说明

## 一、接入的 MCP Server

| 项目 | 值 |
|---|---|
| 名称 | 麦当劳中国 MCP Server（mcd-cn） |
| 地址 | `https://mcp.mcd.cn` |
| 传输 | Streamable HTTP（不支持 WebSocket） |
| 协议版本 | `2025-06-18` |
| 鉴权 | `Authorization: Bearer ${MCD_MCP_TOKEN}` |
| Token 获取 | <https://open.mcd.cn/mcp> 手机号登录 → 控制台激活 → 复制 |
| 限流 | 600 请求 / 分钟 / Token |
| 客户端实现 | `scripts/mcd_mcp.py`（纯标准库，无第三方依赖） |
| 配置示例 | `mcp-config.example.json`（仅含环境变量占位符） |

> Token 等同麦当劳会员身份，**只允许通过环境变量传入**，仓库内不存在任何真实凭据。

## 二、实际使用的 MCP Tool

| Tool | 用在本项目的哪里 | 说明 |
|---|---|---|
| `now-time-info` | 能力一 | 取服务器时间，用于判断「今日活动」与券的有效期 |
| `campaign-calendar` | 能力一 | 拉当月营销活动日历，播报今日活动与近期预告 |
| `available-coupons` | 能力一 | 查询当前可领取的券列表 |
| `auto-bind-coupons` | 能力一 | **一键领取全部可用券**（核心写操作） |
| `my-coupons` | 能力一、三 | 同步我的卡包，做临期提醒；同时为算价提供可用券 |
| `query-nearby-stores` | 能力三 | 选门店（输出 storeCode 供后续调用） |
| `query-meals` | 能力二、三 | 拉门店在售菜单，作为组合枚举的输入 |
| `query-meal-detail` | 能力二（可选） | 查单品详情，用于展示餐品构成 |
| `calculate-price` | 能力二、三 | **算价权威来源**：复核候选组合的真实实付金额（含券、税、配送费）；返回的 `takeWayCode` 是到店下单的必需入参 |
| `create-order` | 能力三 | 创建订单，返回 `payH5Url` + `payId`，状态为**待支付**（**不扣款**） |
| `query-order` | 能力三 | **到号提醒**：轮询订单状态与取餐号；同时识别「待支付」以便引导用户付款 |
| `delivery-query-addresses` | 能力三 | 麦乐送下单必需的 `addressId` 来源 |
| `query-store-coupons` | 能力三（可选） | 查询当前门店可用券 |
| `list-nutrition-foods` | 能力二（可选） | 营养成分，用于「热量搭子」类扩展 |
| `query-my-orders` | 能力二 | 读历史订单，反推四轴人格（不想答题时走这条路径） |

未使用到的 Tool（积分商城系列等）已在 `scripts/mock_data.py` 中预留 mock，便于后续扩展。

## 二之二、下单入参契约（关键）

`calculate-price` / `create-order` 的官方入参**不是** `storeCode + items` 这么简单，实现中已按官方文档对齐：

| 字段 | 取值 | 来源 | 必填场景 |
|---|---|---|---|
| `storeCode` | 门店编码 | `query-nearby-stores` | 全部 |
| `beCode` | 门店 BE 编码 | **只能来自门店接口**，不可生成；本项目自动缓存到 `scripts/.mcd_stores.json` | 全部 |
| `orderType` | 到店/外带 = 1，麦乐送 = 2 | 由 `--mode` 推导 | 全部 |
| `beType` | 1=到店取餐，2=麦乐送，5=得来速，6=企业团餐 | 由 `--mode` 推导 | 全部 |
| `takeWayCode` | 取餐方式码 | `calculate-price` 的返回 | `create-order`（到店） |
| `addressId` | 配送地址 ID | `delivery-query-addresses` | `create-order`（麦乐送） |
| `remark` | 订单备注（≤50 字） | 用户输入 | 选填 |
| `items[]` | `[{"productCode": "...", "quantity": 1}]` | 菜单 `query-meals` | 全部 |

> 字段名是 **`productCode` + `quantity`**，不是 `mealCode` + `qty`——这是早期实现里最容易踩的坑。
> 上层脚本统一用 `{mealCode|code|productCode, qty|quantity}` 描述商品，
> 由 `mcd_schema.build_items()` / `order_params()` 统一转换，**改契约只改这一个文件**。

## 二之三、支付链路（明确说明）

```
calculate-price ──► create-order ──► 返回 payH5Url（待支付） ──► 用户自行打开并支付 ──► query-order 轮询到 READY
      算价            生成待支付订单        扫码支付页                钱在这一步才扣        到号提醒
```

| 问题 | 结论 |
|---|---|
| `create-order` 会扣款吗 | **不会**，只生成「待支付」订单，`orderStatusTitle = 待支付`，附 `leftPaySecond` 倒计时 |
| 扣款发生在哪一步 | 用户打开 `payH5Url` 并在官方页面确认支付时 |
| 支付链接形态 | 2026-04 起为扫码支付页 `https://m.mcd.cn/mcp/scanToPay?orderId=...`，网页收银台已下线 |
| 未支付后果 | 倒计时结束订单自动取消，不产生扣款 |
| 第三方能否代付 | **不能**，支付必须走麦当劳官方渠道；本项目不接触任何支付凭据 |
| 本地实现 | `order_flow.py create` 明确提示不扣款；新增 `pay` 子命令只展示/打开链接，不代替付款；`watch` 遇到待支付状态会直接提示付款链接与剩余时间 |

## 三、调用流程

### 能力一 · 每日自动领券（5 次调用）

```
now-time-info ──► campaign-calendar ──► available-coupons ──► auto-bind-coupons ──► my-coupons
     │                   │                     │                      │                  │
  今日日期           今日/近期活动         可领券清单           一键领取（写）      卡包 + 临期核算
```

- 默认当天只跑一次（幂等，状态存 `scripts/.mcd_state.json`）
- `--dry-run` 会在 `auto-bind-coupons` 前停住，只读不写

### 能力二 · 抽卡（2 ~ 3 次调用）

```
(answers / query-my-orders) ──► 本地打分：四轴 + 性格关键词 ──► 堡格 + 名片名
                                              │
                                              ├─► query-meals        按四轴挑推荐套餐
                                              └─► calculate-price    给推荐套餐核价
```

抽卡本身**不依赖 MCP 也能出结果**（人格模型是本地算的），MCP 只用来把"推荐套餐"接上真实菜单与真实价格。

### 能力三 · 预算锁（1 + N + 1 次调用）

```
available-coupons + my-coupons ──► query-meals ──► 本地组合枚举（≈30~150 个候选）
                                                        │
                                     本地预估优惠预筛 + 四方向候选池（≤24 个）◄── 控调用量
                                                        │
                                              calculate-price × N（逐一复核真实实付）
                                                        │
                                          Pareto 前沿（实付 ↑ / 满足度 ↑）→ 3 套方案
```

下单闭环：

```
query-nearby-stores ──►（用户改单）──► calculate-price ──► create-order ──► query-order（轮询）
     选门店                  复核              确认后下单           支付链接        到号提醒
```

## 四、业务价值

| 价值点 | 说明 |
|---|---|
| **把只读能力变成日常习惯** | `auto-bind-coupons` 是纯写操作，本项目给它套上「每日自动 + 幂等 + 临期提醒」，把一次性接口变成持续价值 |
| **算价能力的产品化** | `calculate-price` 只是 API，本项目把它当成**约束求解器的目标函数**，产出可解释的三档决策，而不是一个数字 |
| **降低决策成本** | 抽卡把"今天吃什么"变成"我是什么人格"，用低门槛的娱乐形式解决高频决策疲劳 |
| **闭环到交易** | 不止于推荐：改单 → 选店 → 下单 → 支付链接 → 取餐号提醒，是完整的消费链路 |
| **可迁移** | 三个能力共享同一套 MCP 客户端与字段兼容层，新增场景只需加一个业务脚本 |

## 五、关键工程取舍

| 取舍 | 原因 |
|---|---|
| 手写 JSON-RPC 客户端而非引入 SDK | 零依赖，评委与用户 `git clone` 即可运行，不需要 pip/npm |
| 独立的 `mcd_schema.py` 字段兼容层 | 真实服务字段与文档可能存在出入，把不确定性收敛到一个文件 |
| 候选复核上限 24 次 | 限流 600/min 虽宽裕，但无意义调用会拖慢响应；本地预估优惠先行预筛 |
| 候选池四方向取样 | 只按分数取 Top-N 会让高价大套餐挤掉所有便宜组合，Pareto 前沿退化成单点（这是实测踩到的坑） |
| 前沿不足 3 点时补「备选方案」 | 预算很紧时数学上只有 1~2 个前沿点，与其只给用户 1 个选择，不如补上次优可行解并明确标注 |
| 写操作强制确认 | `--yes` 或交互确认，避免 Agent 场景下静默下单 |

## 六、无 Token 也能验收

`scripts/mock_data.py` 内置了一套与真实服务**同构**的假数据（30 项菜单、6 张券、3 家门店、5 条活动、6 条历史订单），
覆盖全部 14 个 Tool。任一脚本加 `--mock` 即可离线跑通全流程：

```bash
python scripts/daily_coupons.py --mock
python scripts/quiz_engine.py --history --mock
python scripts/budget_solver.py --budget 25 --taste "辣,鸡" --mock
python scripts/order_flow.py order --store S001 --items B004:1,S001:1 --yes --watch --mock
```

`demo/index.html` 是完全离线可跑的交互版本，不依赖任何网络请求。

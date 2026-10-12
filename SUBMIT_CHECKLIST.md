# 提交前自检清单

> 逐条打勾后再提交。任何一项未完成都可能导致作品被判为材料不合规。

## 一、必交材料（官方要求）

- [x] **`README.md`** —— 项目介绍、安装方法、使用示例、目标用户，含界面预览图
- [ ] **`CONTEST_DECLARATION.md`** —— ⚠️ **必须替换为官方原文，一个字都不能改**
      （当前是占位符！从官方 GitHub 账号 McDonald's China (M-China) 下载后覆盖，
      并用 `md5sum` / `md5` 校验与官方一致）
- [x] **`MCP_INTEGRATION.md`** —— 说明使用的 MCP Server / Tool / 调用流程 / 业务价值
- [x] **`mcp-config.example.json`** —— 脱敏配置，只允许环境变量占位符（仅含 `${MCD_MCP_TOKEN}`）
- [ ] **`workbuddy.md`** —— WorkBuddy 专项奖励需要，需附完整开发对话（MD 格式）
      ⚠️ 结构化记录已完成，**原始对话导出需自行粘贴到文件末尾**
- [x] **源代码** —— 项目主体代码（`scripts/` + `demo/`）

## 二、提交前必须确认的内容

- [ ] 确认 `CONTEST_DECLARATION.md` 已替换为官方文件
- [x] **名片素材已就位**：`picture/` 下 10 张 1600×900 PNG，文件名即语义角色
      （`python scripts/card_gen.py --list-images` 可核对识别结果）
- [x] **`.gitignore` 已放开 `picture/*.png`** —— 素材是作品组成部分，必须一起提交
- [x] **README 界面预览图已生成**：`docs/01-daily-coupons.svg`、`docs/02-nailong-card.svg`、
      `docs/03-budget-lock.svg`、`docs/04-namecard.svg`
      （想换成真实浏览器截图：本机跑 `python tools/make_screenshots.py`）
- [x] 全局 `your-name` 占位符已替换为 `Perry233-TianYupeng`
      （`scripts/card_gen.py`、`demo/index.html` ×2、`package.json`、`CONTEST_DECLARATION.md`）
- [ ] 确认 GitHub 仓库名与 `SKILL.md` 的 `name` 字段一致（建议 `mcd-nailong`），
      避免调用名与路径混淆

## 三、真实环境验证（拿到 MCD_MCP_TOKEN 后）

```bash
setx MCD_MCP_TOKEN "你的Token"     # 重开终端生效

python scripts/mcd_mcp.py list                    # 应列出真实工具清单
python scripts/daily_coupons.py --dry-run         # 先只看不领
python scripts/daily_coupons.py                   # 确认无误后真领
python scripts/order_flow.py stores               # 拿到真实 storeCode / beCode
python scripts/budget_solver.py --budget 25 --taste "辣"
python scripts/quiz_engine.py --interactive --out out/quiz.json
python scripts/card_gen.py --quiz-result out/quiz.json --out out/card-quiz.svg
```

- [ ] 若真实字段与预期不符，**只改 `scripts/mcd_schema.py` 的映射**，不要改上层脚本
- [ ] 记录下真实调用截图 / 输出，可替换 `docs/` 下的预览图

> ⚠️ 调试期间请一律加 `--mock`。不带 `--mock` 的 `create` 会在麦当劳侧**真实创建待支付订单**
> （不扣款，但会占用门店订单位，反复刷可能触发风控）。

## 三之二、打包前必须清缓存（否则会被平台判「目录层级超限」）

两类文件会在包内造成**两层以上嵌套**，平台只允许「根/一级子目录/文件」：

1. `scripts/__pycache__/*.pyc` —— 任何一次运行脚本都会生成；
2. `docs/` 下**不能再建子目录**（例如 `docs/images/` 就会三层嵌套被拦）。

**这是个静默陷阱：本地文件系统与 PyYAML 都不会报错**，只有上传闸门会拦。

```bash
# 打包前务必执行
find . -name "__pycache__" -type d -exec rm -rf {} +     # macOS / Linux / Git Bash
Get-ChildItem -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force   # PowerShell
```

- [ ] 打包前已清理 `__pycache__`、`.pyc`、`.bak`、`.DS_Store`
- [ ] 打包前已清理 `scripts/.mcd_state.json`、`scripts/.mcd_orders.json`、
      `scripts/.mcd_stores.json`、`scripts/.mcd_mock_orders.json`、`out/`
- [ ] 清理后重跑一次 `audit.py <目录> --profile upload`，确认 **UPLOAD GATE: PASS**

> 最近一次闸门结果：**等级 A · 94 分 · BLOCKER 0 · MAJOR 0 · MINOR 2 · UPLOAD GATE PASS**
> 两个 MINOR 分别是 `D2 description 触发场景提示`（描述里已写明「当用户提到…时使用」，
> 属判据口径差异）与 `F5 name(mcd-nailong) 与目录名(McMCP) 不一致`
> （本地工作区目录名造成，线上仓库命名即消除）。

## 四、文件编码（踩过坑，务必检查）

- [ ] 所有文本文件为 **UTF-8 不带 BOM**：`python tools/fix_bom.py --check`
- [ ] 无中文乱码：`python tests/selfcheck.py` 的编码守卫应通过
- [ ] **不要用 PowerShell 的 `Get-Content` / `Set-Content` 改这些文件** ——
      默认 ANSI(GBK) 解码会把 UTF-8 中文变成**不可逆**乱码（本项目已被坑过一次，
      重写了 README.md / SKILL.md / SUBMIT_CHECKLIST.md 三个文件）

## 五、安全自查（不能有例外）

- [ ] 仓库里不存在任何真实 Token（搜 `MCD_MCP_TOKEN=` 应只有占位符与文档说明）
- [ ] `.gitignore` 已包含 `.env`、`mcp.json`、`scripts/.mcd_*.json`、`out/`
- [ ] `scripts/.mcd_*.json`、`out/` 未被提交
- [ ] `git log -p | grep -i "bearer"` 无命中

## 六、质量自查

- [ ] **`python tests/selfcheck.py` → 34/34 通过**（无需 Token，一条命令跑完全部能力 + 结构自查）
- [ ] `python -m compileall scripts` 无语法错误（**跑完记得清 `__pycache__`**，selfcheck 会自动清）
- [ ] `node tests/demo-smoke.cjs` 全部通过（需 `npm install jsdom`）
- [ ] 用手机浏览器打开 `demo/index.html`，确认三条流程可点、弹窗居中、无横向溢出
- [ ] 确认 `SKILL.md` 的 `allowed-tools` 与 `user-invocable` 写法全仓统一（连字符风格）

## 七、拉星策略（排名按 GitHub Star 计）

- [x] README 顶部已有**界面预览图**（4 张，含真实素材生成的名片）
- [ ] 建议再补一段 15 秒 GIF：答题 → 出名片 → 下载（比静态图有效 10 倍）
- [ ] 仓库 Description 写清一句话：
      `麦当劳 MCP 创意 Skill｜每日自动领券 · 奶龙抽卡名片 · 预算锁点餐`
- [ ] 打上 Topics：`mcp` `mcdonalds` `workbuddy` `skill` `agent`
- [ ] 在官方活动页用指定 Issue 模板提交：项目名称 + 项目地址 + 项目简介
- [ ] 提交后把链接发到技术社群 / 朋友圈拉星（Star=0 不进排行榜）

## 八、时间节点

| 节点 | 时间 |
|---|---|
| 报名与排名截止 | **2026-10-25 23:59**（北京时间） |
| 奖品兑换与信息提交截止 | 2026-11-14 |

> 具体规则以官方活动页面说明为准。

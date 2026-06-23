# AGENTS.md — AI 项目落地研究 仓库约定

> 本文件是给任何 AI Agent / 自动化脚本读取的项目级规范。
> 优先级：仓库 AGENTS.md > 用户单次指令。

## 项目性质

个人 AI 落地追踪仓库。**核心交付物是 Markdown**，不是代码。

8 大行业：金融 / 医疗 / 零售 / 教育 / 制造 / 政务 / 文娱 / 物流。
研究资产分 4 类：01_行业地图 / 02_重点行业深度报告 / 03_场景落地剧本 / 04_甲方决策评估 / 06_案例库 / 07_红队质询 / 08_销售BattleCard。

### 双轨定位（2026-06-23 与用户确认）

**Pages 对外 = 纯智库**，目标读者是「业务 leader + 想用 AI 转型的企业家」。**绝对不出现求职字眼**（姓名 / 邮箱 / LinkedIn / 手机 / 求 AI PM 岗 / 候选人视角 / 「我能为你做什么」）。所有上 Pages 的文档按智库口吻写。

仓库内部双轨：
- 🥇 **对外智库（Pages 展示）**：业务 leader 视角的「行业判断 + 案例 + ROI 数据 + 方法论」
- 🥇 **对内求职弹药（仓库 `09_求职信号/`，不上 Pages）**：公司招聘动向 / 岗位需求变化 / 新兴职位类型 / 技能栈要求
- 🥇 **创业机会**（双轨共享）：细分赛道机会 / 未被满足的需求 / 可复制商业模式 / 上下游缺口
- 🥉 **聊天谈资**：爆款案例 / 行业大佬观点 / 故事性强的成败案例（智库副产物，不主动优化）

**信号抓取优先级**：求职信号进 `09_求职信号/`，创业机会进 `01_行业地图` 和 `06_案例库`，**两轨物理隔离**。周更 cron 汇报时**只汇报智库相关**（行业洞察 + 案例），求职信号走单独通道，不主动 push。

> 信息源 / 分类 prompt / 评分模板若出现冲突，以「智库（业务 leader 视角）+ 求职（候选人视角）」双轨为准，互不污染。

## 文件组织原则

### 不许动
- `04_甲方决策评估/老板战略路线图_v2.md` —— 老板拍板文档，单独 review。
- `08_销售BattleCard/BattleCard_v2.md` —— 销售一线弹药，每次改动要复盘。
- `01_行业地图/AI落地行业地图_v2.md` —— 18 行业全量评分基线，改动影响接单判断。

### 周更自动入库的目录（脚本会写）
- `06_案例库/成功案例_v2/` —— 成功案例，自动写
- `06_案例库/失败案例_v2/` —— 失败案例，自动写
- `01_行业地图/` —— LLM 判断为「行业洞察」时写
- `09_求职信号/本周信号/` —— 周更信号（招聘动向 / 创业机会 / 行业趋势），自动写；PORTFOLIO.md 的「本周信号」三节也由 build_index 注入

### 人工 review 才改的目录
- `02_重点行业深度报告/` —— 深度报告，人类写
- `03_场景落地剧本/` —— 落地剧本，人类写
- `04_甲方决策评估/` —— 路线图，人类拍
- `07_红队质询/` —— 红队质疑，人类写
- `08_销售BattleCard/` —— BattleCard，人类写

## 自动化流水线规范

### 周更 cron
- 触发时间：每周一 01:00 UTC = 09:00 UTC+8
- 入口工作流：`.github/workflows/weekly-update.yml`
- 流程：fetch → classify → build_index → 开 PR → 等人工 review → merge → Pages 重部署

### 信息源维护
- **位置**：`automation/sources.yaml`
- **用户可加**：直接编辑 + 开 PR，下个 cron 自动生效
- **三种 type**：`web` / `github_repo` / `rss`（见 sources.yaml 顶部注释）

### LLM 配置
- **CI（GitHub Actions cron）**：通过 GitHub Secrets 注入：`LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`
- **本地试跑**：在仓库根写 `.env`（已被 `.gitignore` 排除），格式 `LLM_API_KEY=sk-xxx`；automation 脚本用 `python-dotenv` 自动加载（如未装，需 `pip install python-dotenv`）
- 默认本地 Ollama `qwen2.5:7b`，生产建议换 OpenAI / DeepSeek / MiniMax
- 分类标准、JSON schema 见 `automation/classify.py` 顶部 PROMPT

### 去重与幂等
- 用 `title + url` 的 SHA1 前 16 位做指纹
- 指纹存 `automation/output/seen.json`，跨周累计
- 重跑同一周不会产生重复条目

## Git 约定

- 主分支：`main`
- 周更工作分支：`auto/weekly-update-YYYYMMDD`
- 周更 PR 标签：`weekly-update` + `auto`
- 重要 PR 必须先 review 再 merge

## 不要做的事

1. **不要直接 push main** —— 周更内容通过 PR merge 进入
2. **不要修改 4 类资产目录的 v2 现有文档**（除非走单独 review）
3. **不要在 PR 里改 secrets / token / workflow 配置**
4. **不要新增未在 sources.yaml 列出的信息源** —— 想加先开 PR 改 sources.yaml
5. **不要在自动化脚本里写死任何密钥 / URL / 模型名** —— 全走 env / config

## 用户偏好（从历次对话沉淀）

- 输出语言：中文优先
- 文档风格：结构化、表格、可量化
- 不需要 A/B/C 备选 —— 直接交付最终版
- 完成后清理过程文件（automation/output/ 是中间产物，留着便于排查，不用删）
- 推送到 GitHub 时中文文件名 + 中文内容必须 UTF-8 干净（已在历次 push 验证）
- **追新节奏：每周一次**（周一 09:00 UTC+8 的周更 cron 节奏已与用户确认匹配）
- **抓取目标场景：求职 + 创业 并重**（2026-06-22 用户原话："求职、创业、聊天谈资"，已确认 A+B 并列优先）

## 相关文档

- `README.md` —— 仓库门面 + 7+8 节完整索引
- `automation/sources.yaml` —— 信息源清单
- `.github/workflows/` —— GitHub Actions 工作流
- `docs/` —— GitHub Pages 站点源
- `01_行业地图/第三轮研究方法论_v1.md` —— 研究方法论（4 步法 + 5 评分模板）
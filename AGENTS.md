# AGENTS.md — AI 项目落地研究 仓库约定

> 本文件是给任何 AI Agent / 自动化脚本读取的项目级规范。
> 优先级：仓库 AGENTS.md > 用户单次指令。

## 项目性质

AI 落地赋能咨询公司的研究资产仓库。**核心交付物是 Markdown**，不是代码。

8 大行业：金融 / 医疗 / 零售 / 教育 / 制造 / 政务 / 文娱 / 物流。
研究资产分 4 类：01_行业地图 / 02_重点行业深度报告 / 03_场景落地剧本 / 04_甲方决策评估 / 06_案例库 / 07_红队质询 / 08_销售BattleCard。

## 文件组织原则

### 不许动
- `04_甲方决策评估/老板战略路线图_v2.md` —— 老板拍板文档，单独 review。
- `08_销售BattleCard/BattleCard_v2.md` —— 销售一线弹药，每次改动要复盘。
- `01_行业地图/AI落地行业地图_v2.md` —— 18 行业全量评分基线，改动影响接单判断。

### 周更自动入库的目录（脚本会写）
- `06_案例库/成功案例_v2/` —— 成功案例，自动写
- `06_案例库/失败案例_v2/` —— 失败案例，自动写
- `01_行业地图/` —— LLM 判断为「行业洞察」时写

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
- 通过 GitHub Secrets 注入：`LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`
- 默认本地 Ollama `qwen2.5:7b`，生产建议换 OpenAI / DeepSeek
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

## 相关文档

- `README.md` —— 仓库门面 + 7+8 节完整索引
- `automation/sources.yaml` —— 信息源清单
- `.github/workflows/` —— GitHub Actions 工作流
- `docs/` —— GitHub Pages 站点源
- `01_行业地图/第三轮研究方法论_v1.md` —— 研究方法论（4 步法 + 5 评分模板）
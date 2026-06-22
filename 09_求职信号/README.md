# 09_求职信号 · 索引说明

> 本目录由**周更 cron 自动写入**，人工 review 即可。
> 触发节奏：每周一 09:00 (UTC+8) 与现有周更同跑一次。

## 目录结构

```
09_求职信号/
├── README.md                  ← 本文件（人工维护）
└── 本周信号/                  ← 自动写入，每周一个文件
    └── 本周信号_YYYYMMDD.md
```

## 三类信号

每条信号由 LLM 分类为以下三类之一（见 `automation/classify.py` 的 `PROMPT_SIGNAL_SYSTEM`）：

| 信号类型 | 含义 | 典型来源 |
|---|---|---|
| `job_market` | 招聘动向（岗位、行业、薪资、地点） | 拉勾 / 猎聘 / 公司招聘官博 / V2EX 招聘贴 |
| `startup_opportunity` | 创业机会（融资、PMF、上下游缺口） | 36 氪 / IT 桔子 / YC Demo Day / 创业访谈视频 |
| `industry_trend` | 行业趋势（监管、模型、行业格局变化） | 36 氪 / InfoQ / 雷锋网 / HuggingFace / OpenAI Blog |

每条信号带 `signal_strength` 评分（1-5），5 分最高。PORTFOLIO.md 周更节只取 Top 3。

## 信号强度评分标准

- **5**：直接相关 + 强时效 + 高信号密度（如：大厂 AI 产品岗批量招聘、明星 AI 创业公司融资公开）
- **4**：相关 + 中等时效（如：某行业 AI 落地新案例）
- **3**：间接相关（如：通用 AI 模型能力提升）
- **2**：弱相关
- **1**：几乎无关（兜底）

## 与现有流水线的关系

- **完全复用**：抓取（fetch.py）→ 分类（classify.py）→ PR 流程 → merge 后部署
- **新增部分**：
  - sources.yaml 新增 `job_signal` / `startup_signal` 两条 type（不污染原有案例抓取）
  - classify.py 新增 signal 分类 prompt（后向兼容，不影响原有 8 行业入库）
  - build_index.py 新增 PORTFOLIO.md 自动注入（用标记块保护人工编辑内容）
- **不去重方式变化**：seen.json 仍按 `title + url` SHA1 指纹去重

## Review Checklist（人工 review 周更 PR 时）

- [ ] 本周信号文件存在且非空
- [ ] 信号类型分布合理（job / startup / trend 不应全是同一类）
- [ ] PORTFOLIO.md 自动注入的 Top 3 是否仍准确（人工可手动调整）
- [ ] 没有招聘骗局 / 营销软文混入

## 维护规则

- **本 README.md**：人工 review 才改，AGENTS.md 中已记录
- **本周信号_YYYYMMDD.md**：自动写入，人工不直接编辑（要改请改 sources.yaml 或 PROMPT）
- **不要在本目录手写 v2 文档**：信号是时序数据，不是 v1/v2 沉淀物

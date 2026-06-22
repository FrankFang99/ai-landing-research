/* docs/assets/data.js
 * 自动由 automation/build_index.py 生成，请勿手动编辑
 * 格式：window.SITE_DATA = { generated_at, industries, latest, stats }
 */
window.SITE_DATA = {
  "generated_at": "2026-06-22T14:27:27+08:00",
  "stats": {
    "total_cases": 11,
    "industries_covered": 8,
    "last_update": "2026-06-22"
  },
  "industries": [
    {
      "rank": 1,
      "name": "金融",
      "priority": "★★★★★",
      "tag": "高 ROI",
      "desc": "风控 / 投顾 / 客服 三条主线，决策链路短、付费意愿强。"
    },
    {
      "rank": 2,
      "name": "医疗",
      "priority": "★★★★★",
      "tag": "高壁垒",
      "desc": "影像 / 病历 / 科研，合规与数据壁垒高，先发优势难撼动。"
    },
    {
      "rank": 3,
      "name": "零售",
      "priority": "★★★★",
      "tag": "高频",
      "desc": "选品 / 营销 / 供应链，场景标准化、复用度高。"
    },
    {
      "rank": 4,
      "name": "教育",
      "priority": "★★★★",
      "tag": "高 ARR",
      "desc": "K12 双减后向素质 + 高校 + 职教转移，付费意愿分层。"
    },
    {
      "rank": 5,
      "name": "制造",
      "priority": "★★★",
      "tag": "重交付",
      "desc": "工业视觉 / 工艺优化，POC 周期长、客单价高。"
    },
    {
      "rank": 6,
      "name": "政务",
      "priority": "★★★",
      "tag": "慢热",
      "desc": "城市治理 / 政务热线，采购周期长但项目稳。"
    },
    {
      "rank": 7,
      "name": "文娱",
      "priority": "★★",
      "tag": "高曝光",
      "desc": "内容生成 / 个性化推荐，付费转化弱但用户增长快。"
    },
    {
      "rank": 8,
      "name": "物流",
      "priority": "★★",
      "tag": "高效率",
      "desc": "调度 / 路径优化，场景集中、ROI 量化清晰。"
    }
  ],
  "latest": [
    {
      "title": "大模型公司的“收入幻觉”",
      "url": "https://36kr.com/p/3862676976712582",
      "industry": "文娱",
      "summary": "文章分析当前大模型公司面临的商业化挑战，讨论AI公司收入增长的真实性与可持续性问题，涉及行业竞争格局、商业模式验证等关键议题",
      "source": "36氪 AI 频道",
      "date": "2026-06-22",
      "fingerprint": "be053ae31beb229a"
    },
    {
      "title": "Is it agentic enough? Benchmarking open models on your own tooling",
      "url": "https://huggingface.co/blog/is-it-agentic-enough",
      "industry": "未分类",
      "summary": "Hugging Face 博客介绍了一套用于评估开源大语言模型作为 AI Agent 时使用工具能力的基准测试方法，指导开发者在自有工具链上测试模型的 agentic 程度，提供了具体的评估框架和实践建议。",
      "source": "Hugging Face Blog",
      "date": "2026-06-22",
      "fingerprint": "2a21974e76466268"
    },
    {
      "title": "From the Hugging Face Hub to robot hardware with Strands Agents and LeRobot",
      "url": "https://huggingface.co/blog/amazon/strands-lerobot-hub-to-hardware",
      "industry": "制造",
      "summary": "Hugging Face 发布博客介绍 Strands Agents 与 LeRobot 的集成方案，演示如何将 Hugging Face Hub 上的 AI 模型和代理无缝部署到机器人硬件，实现从模型中心到实体机器人的端到端工作流，支持 AWS 等云平台协同。",
      "source": "Hugging Face Blog",
      "date": "2026-06-22",
      "fingerprint": "18919aebf74805fa"
    },
    {
      "title": "Samsung Electronics brings ChatGPT and Codex to employees",
      "url": "https://openai.com/index/samsung-electronics-chatgpt-codex-deployment",
      "industry": "制造",
      "summary": "Samsung Electronics 向全球员工部署 ChatGPT Enterprise 和 Codex，成为 OpenAI 最大规模的企业级 AI 部署之一，覆盖多个业务部门，旨在提升员工生产力与工作效率。",
      "source": "OpenAI Blog",
      "date": "2026-06-22",
      "fingerprint": "8f1f766367d241a6"
    },
    {
      "title": "New usage analytics and updated spend controls for enterprises",
      "url": "https://openai.com/index/chatgpt-enterprise-spend-controls",
      "industry": "金融",
      "summary": "OpenAI 为 ChatGPT Enterprise 推出新的使用分析仪表板和支出控制功能，允许组织设置团队级别的使用限制、追踪消费趋势、导出明细报告，帮助企业在规模化部署 AI 时有效控制成本和管理预算。",
      "source": "OpenAI Blog",
      "date": "2026-06-22",
      "fingerprint": "5063c8e0431b411e"
    },
    {
      "title": "Improving health intelligence in ChatGPT",
      "url": "https://openai.com/index/improving-health-intelligence-in-chatgpt",
      "industry": "医疗",
      "summary": "OpenAI 发布 GPT-5.5 Instant 模型的健康响应能力改进，包括更强推理能力、更好上下文理解、更清晰沟通，以及引入 physician-informed 评估机制提升 ChatGPT 在健康和 wellness 领域的回答质量。",
      "source": "OpenAI Blog",
      "date": "2026-06-22",
      "fingerprint": "f3b1868c3fb27afc"
    },
    {
      "title": "Using AI to help physicians diagnose rare genetic diseases affecting children",
      "url": "https://openai.com/index/diagnose-rare-childhood-diseases",
      "industry": "医疗",
      "summary": "OpenAI研究团队使用推理模型辅助诊断儿童罕见遗传疾病，在此前未解决的病例中成功识别出18个新诊断，展示了AI在罕见病诊断领域的实际应用价值。",
      "source": "OpenAI Blog",
      "date": "2026-06-22",
      "fingerprint": "1593126ce382e218"
    },
    {
      "title": "A near-autonomous AI chemist improves a challenging reaction in medicinal chemistry",
      "url": "https://openai.com/index/ai-chemist-improves-reaction",
      "industry": "医疗",
      "summary": "OpenAI与Molecule.one合作，利用GPT-5.4驱动的近自主AI化学家，成功优化了药物化学中一项具有挑战性的反应，为药物研发提供高效解决方案。",
      "source": "OpenAI Blog",
      "date": "2026-06-22",
      "fingerprint": "6e5914a74913af7a"
    },
    {
      "title": "Predicting model behavior before release by simulating deployment",
      "url": "https://openai.com/index/deployment-simulation",
      "industry": "未分类",
      "summary": "OpenAI 推出 Deployment Simulation 方法，通过真实对话数据在模型部署前预测其行为，旨在提升 AI 安全性和评估准确性，为开发者提供模型发布前的验证手段。",
      "source": "OpenAI Blog",
      "date": "2026-06-22",
      "fingerprint": "996dcb2156d22c83"
    },
    {
      "title": "Unlocking UK house-building with AI-accelerated planning",
      "url": "https://deepmind.google/blog/unlocking-uk-house-building-with-ai-accelerated-planning/",
      "industry": "政务",
      "summary": "英国政府与Google DeepMind合作，构建AI原型系统，旨在加速住房规划审批决策，提升政府规划效率。",
      "source": "Google DeepMind Blog",
      "date": "2026-06-22",
      "fingerprint": "e071f35190e95350"
    },
    {
      "title": "Securing the future of AI agents",
      "url": "https://deepmind.google/blog/securing-the-future-of-ai-agents/",
      "industry": "政务",
      "summary": "Google DeepMind 提出 AI Control Roadmap 方案，通过结合传统安全防护措施与实时监控系统来保护 AI agents 的内部运行安全，探讨如何在推进 AI 能力的同时确保安全可控。",
      "source": "Google DeepMind Blog",
      "date": "2026-06-22",
      "fingerprint": "f0034043ca9b27b6"
    }
  ]
};

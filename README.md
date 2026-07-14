# 公文写作智能体 V2.2 (Premium Workspace Edition)

基于 Agentic Design Patterns 的多智能体协作公文写作系统。本项目致力于提供专业、高效、合规的公文及校园/政务新闻撰写体验。

![UI Preview](https://img.shields.io/badge/UI-Gradio_Premium-blue.svg)
![Version](https://img.shields.io/badge/Version-2.2-success.svg)

---

## 🌟 核心特性

- **四维模式路由系统**：自动识别并分发“党政规范”、“校园新闻”、“日常行政”、“新媒体”四大核心写作模式，避免单一模板的生搬硬套。
- **五轮多智能体协作审查 (Reflection Pattern)**：通过 WriterAgent 和 ReviewerAgent 的迭代递进审查（自我反思机制），全方位覆盖格式、事实、逻辑、战略性等指标，自动修复问题。
- **HITL (Human-in-the-loop) 审查循环**：引入用户反馈机制，允许人工干预审查流，用户可手动选择修改项，深度定制最终文稿。
- **多维度风格混合技术**：支持根据不同受众（领导、媒体、普通读者）自动生成混合风格（如“正文70%人民日报 + 导语30%新华社”），并支持 0.0-1.0 的强度调节。
- **高端极简 UI 体验**：使用 Gradio 定制开发的“星月夜”高端动态背景与 iOS 卡片式磨砂玻璃 UI（Premium minimalist iOS card aesthetics）。
- **纯本地数据持久化**：Finder式侧边栏目录管理与自动 JSON 持久化存储机制，保护所有草稿与项目数据安全。

---

## 🚀 快速开始

### 环境依赖安装

```bash
# 克隆仓库
git clone <your-repo-url>
cd official_writer_agent

# 安装依赖
pip install -r requirements.txt # 或手动安装依赖
pip install gradio  # Web 界面必要依赖
```

### 启动 Web 交互台

强烈推荐使用全新设计的 Web 交互台体验完整流程：

```bash
python gradio_app.py
```
> **提示**：启动后，将自动打开游览器访问本地服务。您可以在侧边栏新建项目，体验沉浸式写作。

### 启动命令行交互 (CLI)

```bash
python -m official_writer_agent.cli
```

### 程序化调用 (QuickAPI)

```python
from official_writer_agent.cli import QuickAPI

api = QuickAPI()

# 生成写作简报
brief = api.generate_brief(
    purpose="让领导觉得这次交流活动组织得很好，值得继续支持",
    primary_audience="分管学生工作的张副校长",
    secondary_audiences=["上级学工处", "学生家长"],
    deep_meaning="这次北大交流证明了我们的培养质量获得了顶尖平台认可",
    strategic_anchor="对应培养方案中'全球视野'模块",
    opportunity_context="教育部正在推'基础学科拔尖人才培养计划2.0'",
    key_materials="李同学说'这次交流让我看到了差距，也更有动力'",
    differentiator="我们的学生不是被动听，而是主动提问与讨论"
)

# 获取写作与审查 Prompts
style_profile = api.select_style(media="人民日报")
doc_type_profile = api.select_doc_type(doc_type="通讯")
prompts = api.get_writing_prompts(
    brief=brief, style_profile=style_profile, 
    doc_type_profile=doc_type_profile, materials="..."
)
```

---

## 📚 知识库与规范支持

本项目内置了涵盖多种法定公文和新闻采编的规则：
- **党政机关法定规范**：《党政机关公文处理工作条例》(中办发〔2012〕14号)、《党政机关公文格式》(GB/T 9704-2012)
- **主流媒体体例**：人民日报、新华社、央视新闻、光明日报等媒体范式。
- **高校与机构采编标准**：兼容北大、南大、北师大、武大等顶尖高校新闻网审核标准的定制规则库。

---

## 🗂 进阶阅读

| 文档名称 | 说明 |
|------|------|
| [PROJECT_DESIGN.md](./PROJECT_DESIGN.md) | 完整项目设计文档（推荐，包含V2.2重构说明） |

---

## 🛠 开发与测试

运行本地所有单元测试：
```bash
python -m official_writer_agent.tests.test_all
```

接入您喜欢的 LLM（如 OpenAI、Claude、通义千问、文心一言等）的 API 密钥即可正式投入生产环境使用！

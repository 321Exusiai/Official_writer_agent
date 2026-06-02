# 公文写作智能体

基于 Agentic Design Patterns 的多智能体协作公文写作系统。

---

## 快速开始

### 运行测试

```bash
python -m official_writer_agent.tests.test_all
```

### 启动交互式 CLI

```bash
python -m official_writer_agent.cli
```

### 程序化调用（QuickAPI）

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

# 选择风格与文种
style_profile = api.select_style(media="人民日报")
doc_type_profile = api.select_doc_type(doc_type="通讯")

# 获取写作 Prompt
prompts = api.get_writing_prompts(
    brief=brief,
    style_profile=style_profile,
    doc_type_profile=doc_type_profile,
    materials="李同学的感言、与北大老师的讨论记录、行程照片"
)

print(prompts["system_prompt"])  # 系统提示词
print(prompts["user_prompt"])    # 用户提示词

# 获取审查 Prompt
review_prompt = api.get_review_prompt(
    draft="这是你的初稿...",
    round_index=1,
    brief=brief
)
```

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [PROJECT_DESIGN.md](./PROJECT_DESIGN.md) | 完整项目设计文档（推荐阅读） |
| 本 README | 快速开始指南 |

---

## 项目特点

1. **8 道"灵魂拷问"**：写作前倒逼思考，避免流水账
2. **4 种央媒风格**：人民日报/新华社/央视新闻/光明日报
3. **5 种文种识别**：消息/通讯/侧记/调研报告/简报
4. **五轮结构化审查**：主体性/赋能性/借势性/成长性/战略性
5. **7 种错误自动诊断**：流水账/主体缺失/空泛表态/...
6. **内置知识库**：4 篇范文 + 术语库 + 过渡句库

---

## 完整流程

1. **规划**：回答 8 道问题，生成 WritingBrief
2. **确认**：用户查看、修改、确认简报（HITL）
3. **配置**：选择媒体风格 + 文种
4. **写作**：WriterAgent 基于 Prompt 生成初稿
5. **审查**：ReviewerAgent 五轮审查 + 错误诊断
6. **终稿确认**：用户查看反馈，可选择修改或确认（HITL）
7. **输出**：输出终稿 + 写作简报 + 审查报告

---

## 下一步

接入 LLM（OpenAI/Claude/通义千问/文心一言）即可投入实际使用！

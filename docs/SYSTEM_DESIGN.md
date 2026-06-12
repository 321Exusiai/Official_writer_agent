# 公文写作智能体系统（official_writer_agent）设计文档

> **版本**：V3.0  
> **核心心法**：公文写作不是记录"发生了什么"，而是回答三个问题——这件事证明了我们是谁？我们正走向何方？这件事对组织有什么价值？

---

## 目录

1. [设计哲学](#一设计哲学)
2. [版本演进历程](#二版本演进历程)
3. [系统架构总览](#三系统架构总览)
4. [核心概念体系](#四核心概念体系)
5. [模块详解](#五模块详解)
6. [数据流与工作流](#六数据流与工作流)
7. [智能体协作机制](#七智能体协作机制)
8. [创新亮点](#八创新亮点)
9. [API 参考速查](#九api-参考速查)
10. [注意事项与常见陷阱](#十注意事项与常见陷阱)

---

## 一、设计哲学

### 1.1 核心理念

本系统面向**学生与基层公文写作者**，针对四大痛点而设计：

| 痛点 | 表现 | 解决方案 |
|------|------|----------|
| **流水账** | 按时间顺序记录，缺乏中心思想 | 战略叙事五大原则 + 模式分流 |
| **模式错配** | 用写通知的思路写通讯 | 决策树路由 + 四模式分流 |
| **风格混乱** | 同一篇文章多种媒体风格混杂 | 风格强度参数 + 风格混合引擎 |
| **无审稿** | 写完直接交，无第二双眼睛 | 迭代式审查 + HITL 人工介入 |

### 1.2 设计原则

1. **模式感知（Mode-aware）**：先判断文章性质，再应用对应方法论
2. **一党执政，民主协商**：Orchestrator 保留最终决策权，但决策前广泛咨询
3. **迭代优于并行**：审查采用"审 → 改 → 审 → 改"的迭代模式
4. **教学-生产一体**：每个环节既产出内容，也传递写作方法论
5. **Token 经济学**：从知识库存储到智能体通信，全链路优化 Token 消耗
6. **规范为本**：严格遵循党政公文国家标准和高校新闻规范

### 1.3 遵循的规范体系

| 梯队 | 来源 | 内容 |
|------|------|------|
| 第一梯队 | 党政机关法定规范 | GB/T 9704-2012、中办发〔2012〕14号 |
| 第二梯队 | 985/211 高校新闻采编规范 | 北大/南大/北师大/武大/中大/华科等9所 |
| 第三梯队 | 通用新闻规范 | 5W1H、倒金字塔结构 |
| 第四梯队 | 其他行业规范 | 其他高校与行业标准 |

---

## 二、版本演进历程

| 版本 | 关键变化 | 核心改进 |
|------|----------|----------|
| **V1** | 五大原则全局硬约束 | 建立战略叙事方法论 |
| **V2** | 引入 WritingMode + 决策树路由 | 解决模式错配问题 |
| **V2.1** | 迭代式审查（Reflection Pattern） | 修复"多轮并行审同一稿"的 bug |
| **V2.2** | HITL 审查循环 + 风格混合 + 强度参数 | 人机协作 + 风格精细控制 |
| **V3.0** | 多智能体协作 + 知识库压缩 + 个性化数据库 + Token 优化器 + URL 导入 + API 配置 | 完整生产级框架 |

---

## 三、系统架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        用户层 (CLI / Gradio)                         │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Questionnaire  问卷系统                          │
│         决策树路由 → 模式问题 → WritingBrief 生成                    │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ WritingBrief
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Orchestrator  工作流协调器                       │
│                                                                     │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│   │  StyleAdapter │  │DocTypeIdent. │  │AgentCoord.   │            │
│   │  风格选择/混合 │  │  文种识别    │  │  多智能体协商 │            │
│   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘            │
│          │                 │                 │                     │
│          ▼                 ▼                 ▼                     │
│   ┌──────────────────────────────────────────────────┐            │
│   │               WriterAgent  写作智能体              │            │
│   │     模式原则 + 风格注入 + 文种规范 + 范文参考      │            │
│   └──────────────────────┬───────────────────────────┘            │
│                          │ LLM                                     │
│                          ▼                                         │
│   ┌──────────────────────────────────────────────────┐            │
│   │             ReviewerAgent  审查智能体              │            │
│   │       iterate_review() → 审→改→审→改 迭代        │            │
│   └──────────────────────┬───────────────────────────┘            │
│                          │ HITL                                    │
│                          ▼                                         │
│   ┌──────────────────────────────────────────────────┐            │
│   │          MultiDocGenerator  一文多体生成器         │            │
│   │       先生长版 → EXTRACTION_PROMPTS 提取短版      │            │
│   └──────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      PersonalizedDB  个性化数据库                    │
│             用户 → 项目 → 问卷/文章/偏好/反 bias 分析               │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     横向支撑模块                                    │
│  ┌─────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ KnowledgeBase│ │ Token    │ │ Prompt   │ │ URL      │          │
│  │  知识库     │ │Optimizer │ │ Cache    │ │ Importer │          │
│  └─────────────┘ └──────────┘ └──────────┘ └──────────┘          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 四、核心概念体系

### 4.1 四大写作模式（WritingMode）

系统通过决策树将写作任务路由到四种模式之一：

| 模式 | 枚举值 | 适用文档 | 激活原则 | 对标 |
|------|--------|----------|----------|------|
| **战略叙事** | `STRATEGIC_NARRATIVE` | 新闻通讯、研学报道、典型人物 | 主体性/赋能性/借势性/成长性/战略性 | 人民日报、央视通讯 |
| **客观陈述** | `OBJECTIVE_REPORT` | 事故通报、调研报告、审计报告 | 事实准确性/逻辑一致性/表述客观性/问题导向性/结论可验证性 | 新华社 |
| **行政行为** | `ADMINISTRATIVE` | 通知、请示、批复、函、纪要 | 格式规范性/用词准确性/合规性/简洁性/无冗余性 | GB/T 9704-2012 |
| **信息传达** | `INFORMATIONAL` | 简报、消息、活动稿 | 信息完整性/结构清晰性/重点突出性/不渲染/受众适配性 | 新华社消息 |

**决策路由**：从 `writing_mode.py` 中的 `DECISION_TREE` 出发，`navigate_tree(path)` 导航到叶子节点，匹配对应模式。

### 4.2 五种文种（DocumentType）

| 文种 | 枚举值 | 建议篇幅 | 用途 |
|------|--------|----------|------|
| **消息** | `NEWS_BRIEF` | 500-1000 字 | 快速报道事件 |
| **通讯** | `FEATURE` | 1500-3000 字 | 深度报道 |
| **侧记/特写** | `SIDELIGHT` | 800-1500 字 | 场景化描写 |
| **调研报告** | `RESEARCH_REPORT` | 2000-5000 字 | 系统性分析 |
| **简报** | `BULLETIN` | 300-800 字 | 简讯/快报 |

### 4.3 五种媒体风格（MediaStyle）

每种风格在 5 个维度上量化，附词汇池和示例开头/结尾：

| 风格 | 叙事视角 | 情感基调 | 数据密度 | 文学性 | 政策关联度 |
|------|----------|----------|----------|--------|------------|
| **人民日报** | 第三人称 | 正面积极,有温度 | ★★☆ | ★★★ | ★★★ |
| **新华社** | 第三人称 | 客观,中性偏正面 | ★★★ | ★★☆ | ★★☆ |
| **央视新闻** | 第一/三人称 | 感染力强 | ★★☆ | ★★★ | ★★☆ |
| **光明日报** | 第三人称 | 典雅,有思想性 | ★★☆ | ★★★★ | ★★☆ |
| **党政机关行文** | 第三人称 | 正式,庄重 | ★★☆ | ★☆☆ | ★★★★★ |

### 4.4 WritingBrief 数据载体

问卷系统的最终产出，也是所有模块的输入数据：

| 字段 | 类型 | 说明 |
|------|------|------|
| `writing_mode` | `WritingMode` | 决策树路由确定的模式 |
| `mode_display_name` | `str` | 模式中文名 |
| `subtype` | `str` | 文种子类型（如 `feature`、`notice`）|
| `purpose` | `str` | 核心写作目的 |
| `primary_audience` | `str` | 主要读者（具体到人） |
| `secondary_audiences` | `List[str]` | 次要读者列表 |
| `deep_meaning` | `str` | 事件深层含义 |
| `strategic_anchor` | `str` | 战略锚点（与组织长期战略的关联）|
| `opportunity_context` | `str` | 借势机会 |
| `key_materials` | `str` | 不可替代的素材 |
| `differentiator` | `str` | 独特视角/差异化卖点 |
| `length_hint` | `Optional[int]` | 期望篇幅 |
| `style_intensity` | `float` | 风格强度（0.0-1.0） |
| `target_doc_types` | `List[str]` | 目标文种列表 |
| `raw_answers` | `Dict[str, str]` | 原始问答 |

---

## 五、模块详解

### 5.1 问卷系统 [questionnaire.py](file:///c:/Users/王为韬/OneDrive/桌面/项目/python/official_writer_agent/src/questionnaire/questionnaire.py)

**职责**：通过交互式问卷引导用户明确写作需求，产出 WritingBrief。

**核心类**：
- `Questionnaire` — 问卷控制器，管理 `ROUTING → MODE_QUESTIONS → COMPLETE` 三阶段
- `WritingBrief` — 写作简报数据类

**关键方法**：

| 方法 | 说明 |
|------|------|
| `get_routing_question()` | 获取路由选择题（4选1） |
| `submit_routing_choice(i)` | 提交路由选择 |
| `get_current_mode_question()` | 获取当前模式适配的问题 |
| `submit_mode_answer(answer)` | 提交答案，含 `why_ask`（教学说明）和 `hint`（示例） |
| `go_back()` / `skip_current()` | 回退/跳过 |
| `finish()` | 完成问卷 → 产出 `WritingBrief` |
| `get_teaching_note()` | 每道题附带的教学提示 |

**设计要点**：每道题附带 `why_ask`（为什么这么问）和 `hint`（示例回答），实现"教学-生产一体化"。

---

### 5.2 工作流协调器 [orchestrator.py](file:///c:/Users/王为韬/OneDrive/桌面/项目/python/official_writer_agent/src/core/orchestrator.py)

**职责**：核心状态机，控制完整写作流程的调度。

**状态流转**：
```
IDLE → ROUTING → MODE_QUESTIONING → PLANNING → WRITING → REVIEWING → COMPLETED
```

**核心类**：
- `Orchestrator` — 主协调器
- `WritingPlan` — 写作计划数据类
- `OrchestratorState` — 状态枚举

**关键方法**：

| 方法 | 说明 |
|------|------|
| `start_routing()` | 开始路由选择 |
| `submit_routing_choice(i)` | 提交路由选择 |
| `get_current_mode_question()` | 获取当前模式问题 |
| `submit_mode_answer(answer)` | 提交模式问题答案 |
| `generate_plan()` | 根据 Brief 生成写作计划（含智能体协商） |
| `write()` | 执行写作（调用 WriterAgent） |
| `review()` | 初审（调用 ReviewerAgent.iterate_review） |
| `re_review()` | 复审（用户手动修复后） |
| `finalize()` | 终稿确认 + 多版本生成 |
| `get_workflow_summary()` | 获取完整工作流摘要 |

**集成点**：
- 在 `generate_plan()` 中调用 `AgentCoordinator.consult_before_decision()` 进行民主协商
- 在 `write()` 前/后调用 `AgentCoordinator.collect_proactive_reports()` 收集主动预警
- 在 `finalize()` 中调用 `MultiDocGenerator.generate_multi_doc()` 生成多版本

---

### 5.3 写作智能体 [writer_agent.py](file:///c:/Users/王为韬/OneDrive/桌面/项目/python/official_writer_agent/src/core/writer_agent.py)

**职责**：根据模式、风格、文种生成公文初稿。

**核心类**：`WriterAgent`、`WriterConfig`

**关键方法**：

| 方法 | 说明 |
|------|------|
| `configure(brief, writing_mode, style, doc_type)` | 配置写作参数 |
| `build_system_prompt()` | 构建系统提示词（注入模式原则 + 风格 + 范文） |
| `build_user_prompt(materials)` | 构建用户提示词 |
| `generate_outline()` | 生成写作大纲 |
| `get_full_prompt()` | 获取完整提示词 |

**模式感知**：
- 从 `get_mode_profile()` 动态获取：`principles`、`must_write`、`must_skip`、`forbidden_patterns`、`language_guidelines`
- 从 `KnowledgeBase.get_exemplars_for_prompt()` 获取精悍范文参考

---

### 5.4 审查智能体 [reviewer_agent.py](file:///c:/Users/王为韬/OneDrive/桌面/项目/python/official_writer_agent/src/core/reviewer_agent.py)

**职责**：对初稿进行多维度审查并迭代修复。

**核心类**：`ReviewerAgent`、`ReviewFinding`、`ReviewResult`、`ReviewSeverity`

**五大错误库**（按模式分类）：

| 错误库 | 适用模式 |
|--------|----------|
| `UNIVERSAL_ERROR_DB` | 所有模式通用 |
| `STRATEGIC_ERROR_DB` | 战略叙事 |
| `ADMIN_ERROR_DB` | 行政行为 |
| `OBJECTIVE_ERROR_DB` | 客观陈述 |
| `INFO_ERROR_DB` | 信息传达 |

**关键方法**：

| 方法 | 说明 |
|------|------|
| `set_mode(mode)` | 设置审查模式 |
| `build_review_prompt()` | 构建审查提示词 |
| `diagnose_errors(text, mode)` | 诊断错误（含 `check_subject_ratio` 主语比例检查） |
| `check_format_compliance(text)` | 格式合规检查（标题三要素、日期格式等） |
| `iterate_review(text, max_iterations)` | **核心**：审→改→审→改 迭代循环 |
| `apply_fixes(text, findings)` | 批量应用修复 |
| `run_full_review(text, mode)` | 全维度审查 |

---

### 5.5 风格适配器 [style_adapter.py](file:///c:/Users/王为韬/OneDrive/桌面/项目/python/official_writer_agent/src/core/style_adapter.py)

**职责**：选择、混合媒体风格，生成风格注入信息。

**核心类**：`StyleAdapter`、`StyleProfile`、`StyleBlend`、`MediaStyle`

**风格维度**：
- `narrative_perspective`（叙事视角）
- `emotional_tone`（情感基调）
- `data_density`（数据密度）
- `literary_level`（文学性）
- `policy_linkage`（政策关联度）

**关键方法**：

| 方法 | 说明 |
|------|------|
| `select_style(style, intensity)` | 选择风格并设置强度 |
| `auto_select_style(mode, purpose)` | 根据模式和目的自动推荐风格 |
| `suggest_blend(audiences)` | 根据受众推荐风格混合方案 |
| `get_system_prompt_injection(mode)` | 获取系统提示词中的风格注入片段 |

**风格混合**（V2.2+）：当有多个受众群体时，可生成混合风格（如"正文 70% 人民日报 + 导语 30% 新华社"）。

---

### 5.6 文种识别器 [document_type.py](file:///c:/Users/王为韬/OneDrive/桌面/项目/python/official_writer_agent/src/core/document_type.py)

**职责**：根据写作简报自动推荐最匹配的文种。

**核心类**：`DocumentTypeIdentifier`、`DocTypeProfile`

**识别机制**：按 `purpose`、`audience`、`key_materials` 三个维度加权打分。

**关键方法**：

| 方法 | 说明 |
|------|------|
| `identify(brief)` | 根据 Brief 加权打分推荐文种 |
| `analyze_materials(materials)` | 分析素材类型 |
| `get_profile(doc_type)` | 获取文种配置 |
| `generate_template_prompt(doc_type, style)` | 生成文种格式模板提示 |

---

### 5.7 一文多体生成器 [multi_doc_generator.py](file:///c:/Users/王为韬/OneDrive/桌面/项目/python/official_writer_agent/src/core/multi_doc_generator.py)

**职责**：从同一份素材生成多种文种的版本。

**核心类**：`MultiDocGenerator`、`DocVersion`、`MultiDocOutput`

**核心方法**：

```python
generate_multi_doc(brief, materials, target_types, primary_style, llm_callable=None) -> MultiDocOutput
```

**提取策略**：
1. 先生成**最长版本**（通常是 FEATURE）
2. 再用 `EXTRACTION_PROMPTS` 从中**提取**生成短版本（NEWS_BRIEF / BULLETIN / SIDELIGHT）

> **优势**：保证内容一致性，同时显著节省 Token（不需要为每个文种从头生成）。

---

### 5.8 智能体协调器 [agent_coordinator.py](file:///c:/Users/王为韬/OneDrive/桌面/项目/python/official_writer_agent/src/core/agent_coordinator.py)

**职责**：实现"一党执政，民主协商"的多智能体协作模式。

**七种智能体角色**：

| 角色 | 枚举值 | 职责 |
|------|--------|------|
| 协调者 | `COORDINATOR` | 决策仲裁（由 Orchestrator 扮演）|
| 写作者 | `WRITER` | 关注风格、素材使用 |
| 审查者 | `REVIEWER` | 关注质量把控 |
| 风格顾问 | `STYLE_ADVISOR` | 关注风格强度和混合方案 |
| 知识管理员 | `KNOWLEDGE_KEEPER` | 推送范文和术语 |
| 用户代理 | `USER_PROXY` | 代表用户立场 |
| 文种分析师 | `DOC_TYPE_ANALYST` | 推荐文种选择 |

**核心类**：`AgentCoordinator`、`AgentMessage`、`MessageBus`、`DebateResult`

**关键方法**：

| 方法 | 说明 |
|------|------|
| `consult_before_decision(topic, context)` | **决策前咨询**：向各智能体征询意见 |
| `collect_proactive_reports()` | **主动预警**：收集智能体的自发警告 |
| `run_debate(topic, viewpoints)` | **辩论**：观点冲突时启动辩论达成共识 |
| `make_decision(topic, context)` | 综合所有意见做出决策 |

**通信协议**：智能体间消息使用 JSON 字段缩写（`t`/`p`/`c`/`a`），相比自然语言可节省约 80% 通信 Token。

---

### 5.9 知识库 [knowledge_base.py](file:///c:/Users/王为韬/OneDrive/桌面/项目/python/official_writer_agent/src/knowledge/knowledge_base.py)

**职责**：提供范文参考、格式用语、术语解释、错误模式。

**核心类**：`KnowledgeBase`、`CompactExemplar`、`KnowledgeCategory`

**数据资产**：

| 资产 | 数量 | 说明 |
|------|------|------|
| `COMPACT_EXEMPLARS` | ~18篇 | 压缩范文（只存骨架/句式/可复用模式） |
| `FORMULAIC_EXPRESSIONS` | 按文种分类 | 格式化用语库 |
| `FORMAT_ERRORS_DB` | 8类 | 格式错误模式 |
| `ERROR_PATTERNS_DB` | 通用 | 常见写作错误模式 |
| `TERMINOLOGY_DB` | ~30+条 | 多领域术语 |
| `TRANSITION_PHRASES` | 按风格分类 | 过渡句式 |

**压缩范文设计**：范文不存原文全文，只保留**骨架结构**、**关键句式**、**可复用模式**和**语言标签**，Token 消耗节省 90%+，同时保留高保真指导价值。

---

### 5.10 个性化数据库 [personalized_db.py](file:///c:/Users/王为韬/OneDrive/桌面/项目/python/official_writer_agent/src/core/personalized_db.py)

**职责**：三层存储模型，提供反 bias 分析和长期写作跟踪。

**核心类**：`PersonalizedDB`、`UserProfile`、`Project`、`AntiBiasAnalysis`、`WritingHistory`

**三层存储**：

```
用户层 (UserProfile)
  ├── 项目1 (Project)
  │   ├── QuestionnairesResults (问卷结果)
  │   ├── ReferenceArticles (参考文章)
  │   ├── VocabularyCorpus (词汇语料)
  │   └── UserRequirement (用户要求)
  ├── 项目2 (Project)
  │   └── ...
  └── ...
```

**关键方法**：

| 方法 | 说明 |
|------|------|
| `create_user(name)` / `get_user(name)` | 用户管理 |
| `create_project(username, title)` | 项目管理 |
| `add_url_reference(username, project, url)` | 添加 URL 参考 |
| `add_batch_urls(username, project, urls)` | 批量导入 URL |
| `analyze_weaknesses(username)` | 分析用户写作弱点 |
| `_analyze_anti_bias()` | 反 bias 分析（发现写作偏好导致的盲区）|

---

### 5.11 LLM API 配置 [api_config.py](file:///c:/Users/王为韬/OneDrive/桌面/项目/python/official_writer_agent/src/config/api_config.py)

**职责**：管理多个 LLM 提供商的 API 配置。

**支持的提供商**：

| 提供商 | 默认模型 | 配置方式 |
|--------|----------|----------|
| OpenAI | gpt-4o | API Key + Base URL |
| 通义千问 | qwen-turbo | API Key + dashscope |
| DeepSeek | deepseek-chat | API Key |
| 智谱 | glm-4-plus | API Key |
| Claude | claude-3-opus | API Key |
| Ollama（本地） | qwen2.5:7b | Base URL |

**关键方法**：

| 方法 | 说明 |
|------|------|
| `apply_provider_template(provider)` | 应用提供商默认模板 |
| `update(**kwargs)` | 更新配置 |
| `test_connection()` | 测试连接（实际发送一次 Chat 请求）|
| `is_enabled()` | 检查是否已启用 |
| `save()` | 持久化到 `api_config.json` |

---

### 5.12 工具模块

#### URL 导入器 [url_importer.py](file:///c:/Users/王为韬/OneDrive/桌面/项目/python/official_writer_agent/src/utils/url_importer.py)

| 方法 | 说明 |
|------|------|
| `import_from_url(url)` | 从 URL 导入文档 |
| `batch_import(urls)` | 批量导入 |
| `import_from_text(text)` | 从粘贴文本导入 |
| `_detect_format(text)` | 自动检测文档格式（新闻/公文/调研/政策/博客）|
| `_extract_style_patterns(text)` | 提取风格特征（句长/句式/引语密度）|

> **注意**：使用 `requests` + 正则去噪（移除 script/style/nav/footer/ad 等），不依赖 BeautifulSoup。

#### Token 优化器 [token_optimizer.py](file:///c:/Users/王为韬/OneDrive/桌面/项目/python/official_writer_agent/src/utils/token_optimizer.py)

集成六大策略，来源综合自 11 个权威资料：

| 策略 | 效果 | 来源 |
|------|------|------|
| **A. Prompt 文本压缩** | 去礼貌词/符号化/缩写 | TokenOps, CSDN |
| **B. 结构化输出协议** | JSON schema 通信 | IETF ADOL, CodeAgents |
| **C. 分层上下文管理** | 省 90%+ 上下文 | Particula Tech |
| **D. 缓存对齐** | 静态+动态缓存 | OpenAI, DeepSeek |
| **E. 隐式推理** | 省 70% 推理 Token | 阿里云 |
| **F. 模型分级路由** | 差价 100× | 各模型定价 |

#### 文本安全化 [text_sanitizer.py](file:///c:/Users/王为韬/OneDrive/桌面/项目/python/official_writer_agent/src/utils/text_sanitizer.py)

解决中文引号（""''）在 Python 源码中的兼容性问题。关键函数：

- `sanitize_text()` / `safe_quotes()` / `safe_dict_value()`
- `safe_writing_for_python()` / `batch_replace()`

#### 响应缓存 [response_cache.py](file:///c:/Users/王为韬/OneDrive/桌面/项目/python/official_writer_agent/src/utils/response_cache.py)

手写 LRU 缓存（maxsize=128），避免重复构建相同 Prompt：

- `make_cache_key(category, *args)` — 生成缓存键
- `cached_prompt(category, *args)` — 缓存装饰器
- `prompt_cache` — 全局实例

---

## 六、数据流与工作流

### 6.1 完整工作流

```
 用户输入
    │
    ▼
 ┌──────────────────┐
 │    问卷系统       │   ← 教学引导 + 需求收集
 │  决策树路由选择    │
 │  模式问题回答     │
 └────────┬─────────┘
          │ WritingBrief
          ▼
 ┌──────────────────┐
 │  智能体协商阶段   │   ← 一党执政，民主协商
 │  Coordinator      │
 │  consult_before_  │
 │  decision()       │
 └────────┬─────────┘
          │ WritingPlan
          ▼
 ┌──────────────────┐
 │    写作阶段       │   ← 风格注入 + 文种规范 + 范文参考
 │  WriterAgent      │
 │  build_system_    │
 │  prompt()         │
 │  → LLM 调用       │
 └────────┬─────────┘
          │ draft
          ▼
 ┌──────────────────┐
 │    审查阶段       │   ← 迭代式 Reflection Pattern
 │  ReviewerAgent    │
 │  iterate_review() │
 │  Round1: 审→改    │
 │  Round2: 审→改    │
 └────────┬─────────┘
          │ reviewed_draft
          ▼
 ┌──────────────────┐
 │   HITL 人工介入   │   ← 用户选择：接受/修复/重审
 │  查看审查报告     │
 │  手动修复/重新审查 │
 └────────┬─────────┘
          │ final_draft
          ▼
 ┌──────────────────┐
 │  多版本生成      │   ← 一文多体
 │  MultiDocGenerator│
 │  generate_multi_  │
 │  doc()            │
 └────────┬─────────┘
          │ versions
          ▼
 ┌──────────────────┐
 │  个性化保存      │
 │  PersonalizedDB  │
 │  保存历史+反bias │
 └──────────────────┘
```

### 6.2 横向贯穿的支撑服务

```
                     LLM 调用
                        │
              ┌─────────┼─────────┐
              │         │         │
              ▼         ▼         ▼
         TokenOptimizer  │   PromptCache
         prompt 压缩     │   缓存命中
                        │
              ┌─────────┘
              ▼
         KnowledgeBase
         范文/术语/格式
```

---

## 七、智能体协作机制

### 7.1 "一党执政，民主协商"模式

```
┌──────────────────────────────────────────┐
│           Orchestrator (执政党)           │
│           保留最终决策权                   │
└────┬──────┬──────┬──────┬──────┬──────┬──┘
     │      │      │      │      │      │
     ▼      ▼      ▼      ▼      ▼      ▼
  Writer Reviewer Style  Knowl. DocType PDB
                  Advisor Base   Analyst
     └──────┬──────┴──────┬──────┘
            │              │
            ▼              ▼
     consult_before_   collect_proactive_
     decision()        reports()
     (决策前咨询)       (决策后预警)

     观点冲突时 → run_debate() → 达成共识
```

### 7.2 协商流程

1. **制定写作计划前**：`consult_before_decision("写作方案评审", brief_context)`
   - 6 个智能体分别返回 `{"concerns": [], "suggestions": []}`
   - Orchestrator 综合所有意见后制定写作方案

2. **写作过程中**：`collect_proactive_reports()`
   - 各智能体主动上报潜在问题
   - 如素材不足、风格不匹配、格式风险等

3. **观点冲突时**：`run_debate(topic, viewpoints)`
   - 如 Writer 和 Style Advisor 在风格强度上有分歧
   - 辩论后达成共识

### 7.3 通信协议

智能体间消息格式（字段缩短以节省 Token）：

```json
{
  "t": "consult",           // type: 消息类型
  "p": "high",              // priority: 优先级
  "from": "writer",         // 来源角色
  "to": "coordinator",      // 目标角色
  "c": ["需要确认素材来源"],  // concerns: 关切点
  "a": ["优先使用直接引语"],  // suggestions: 建议
  "ctx": {}                 // context: 上下文
}
```

---

## 八、创新亮点

### 8.1 架构创新

| 创新点 | 说明 |
|--------|------|
| **模式感知架构** | 先识别文章类型，再激活对应方法论，避免方法论错配 |
| **一党执政民主协商** | 保留决策权威性同时获得多智能体协同价值 |
| **迭代式 Reflection** | 真正的"审→改→审→改"循环，而非多轮并行审同一稿 |
| **HITL 审查循环** | 用户可在审查环节介入：接受/选问题修复/直接编辑/重审 |

### 8.2 数据创新

| 创新点 | 说明 |
|--------|------|
| **压缩格式知识库** | 范文只存骨架不存原文，Token 消耗省 90%+ |
| **一文多体提取策略** | 先写长版本再提取短版本，保证一致性且省 Token |
| **三层个性化存储** | 用户→项目→项目内，配合反 bias 分析 |
| **反 bias 分析** | 自动发现用户写作偏好导致的盲区 |
| **五大错误库** | 按模式分类的错误知识体系 |

### 8.3 工程创新

| 创新点 | 说明 |
|--------|------|
| **Token 六大优化策略** | 综合 11 个权威来源的全链路优化 |
| **JSON 通信协议** | 字段缩短，省约 80% 通信 Token |
| **教学-生产一体** | 每道题提供教学说明和示例，边写边学 |
| **Prompt 缓存** | LRU 缓存避免重复构建相同 Prompt |
| **URL 智能导入** | 自动识别文档格式并提取风格特征 |

---

## 九、API 参考速查

### 9.1 核心模块实例化顺序

```python
# 标准初始化流程
from src.core.orchestrator import Orchestrator
from src.core.agent_coordinator import AgentCoordinator
from src.core.personalized_db import PersonalizedDB
from src.core.multi_doc_generator import MultiDocGenerator
from src.core.writer_agent import WriterAgent
from src.core.reviewer_agent import ReviewerAgent
from src.core.style_adapter import StyleAdapter
from src.core.document_type import DocumentTypeIdentifier
from src.knowledge.knowledge_base import KnowledgeBase
from src.questionnaire.questionnaire import Questionnaire, WritingBrief

# 1. 问卷系统
questionnaire = Questionnaire()

# 2. 核心组件
db = PersonalizedDB()
knowledge = KnowledgeBase()
style_adapter = StyleAdapter()
doc_type_identifier = DocumentTypeIdentifier()
coordinator = AgentCoordinator()
writer = WriterAgent(knowledge_base=knowledge, style_adapter=style_adapter)
reviewer = ReviewerAgent(knowledge_base=knowledge)
multi_doc_gen = MultiDocGenerator(
    doc_type_identifier=doc_type_identifier,
    style_adapter=style_adapter,
    coordinator=coordinator,
)

# 3. 协调器
orchestrator = Orchestrator(
    writer_agent=writer,
    reviewer_agent=reviewer,
    style_adapter=style_adapter,
    doc_type_identifier=doc_type_identifier,
    knowledge_base=knowledge,
    coordinator=coordinator,
    db=db,
    multi_doc_gen=multi_doc_gen,
)
```

### 9.2 命令行入口

```bash
# 启动 CLI
python cli.py
# 启动 Gradio Web 界面（功能实现中）
python gradio_app.py
```

### 9.3 快捷 api_config.json 配置位置

配置文件位于：
```
src/api_config.json
```

---

## 十、注意事项与常见陷阱

### 10.1 属性名陷阱

> **WritingBrief** 没有 `title`、`event_time`、`location`、`current_content` 等传统字段。正确字段见 [4.4 WritingBrief](#44-writingbrief-数据载体)。
> 
> 从旧数据兼容创建请使用 `WritingBrief.create_brief_from_legacy_data()`。

### 10.2 多版本生成方法名

> **重要**：`MultiDocGenerator` 的正确方法是 `generate_multi_doc()`，**不是** `generate_all()`。
> 
> ```
> ✅ output = multi_doc_gen.generate_multi_doc(brief=brief)
> ❌ output = multi_doc_gen.generate_all(...)
> ```

### 10.3 审查返回值解包

> `iterate_review(text, max_iterations)` 返回 `(final_draft, iteration_results)`，其中 `iteration_results` 是迭代过程日志，**不是** `review_summaries`。

### 10.4 智能体预警键名

> `collect_proactive_reports()` 返回的字典中，预警文本的键是 `"alert"`，**不是** `"warning"`。
> 
> ```python
> warning_text = report.get("alert", "")  # ✅
> warning_text = report.get("warning", "")  # ❌ 返回空
> ```

### 10.5 `apply_manual_fix` 调用方式

> `ReviewerAgent._apply_fix()` 是实例方法，应使用实例调用：
> 
> ```python
> fix = self.reviewer._apply_fix(text, finding)  # ✅
> fix = ReviewerAgent._apply_fix(text, finding)  # ❌ 类方法调用
> ```

### 10.6 知识库使用

> `KnowledgeBase.get_exemplars_for_prompt(mode, max_exemplars)` 会自动限制 Token 消耗，按模式筛选范文。不需要手动管理知识库内容的长度。

### 10.7 风格强度的边界行为

> 当 `style_intensity < 0.5` 时，系统会**禁用**该风格独有的词汇；当 `intensity ≥ 0.5` 时，开启风格独有词汇池。强度为 0 时仅保留最通用的写作规范。

### 10.8 缓存注意事项

> `PromptCache` 是手写 LRU 缓存（maxsize=128），使用 `pickle` 序列化键。如果要缓存的对象包含不可 pickle 的字段（如 lambda 函数），需要自定义 `__reduce__` 或调整缓存键生成方式。

### 10.9 Gradio 界面（当前状态）

> Gradio Web 界面 (`gradio_app.py`) 目前处于**接口实现中**的状态，部分步骤（如智能体协商日志显示、多版本对比查看）可能不完全。
> 完整的业务逻辑以 CLI (`cli.py`) 和底层 Python 模块为准。

### 10.10 调试建议

| 问题 | 排查方向 |
|------|----------|
| 智能体协商显示"无意见" | 检查 `agent_coordinator.py` 中各 `_xxx_consultation()` 方法的**关键词匹配**逻辑 |
| 生成内容为空 | 检查 LLM 是否连接成功（`test_connection()`），以及 `WriterAgent` 的 `build_system_prompt` 输出 |
| 多版本生成失败 | 确认 `MultiDocGenerator.generate_multi_doc()` 的参数是否正确传入 brief |
| 审查报告为空 | 确认 `ReviewerAgent.set_mode()` 已调用，错误库与当前模式匹配 |
| 用户/项目保存失败 | 检查 `PersonalizedDB` 的 JSON 序列化是否包含不可序列化的类型 |

---

> **总结**：这是一个将公文写作方法论、Agentic Design Patterns、多智能体协作、党政公文规范、Token 经济学和教学陪伴感做了系统级融合的项目。V3.0 已具备完整框架，接入真实 LLM 后可投入实际使用。
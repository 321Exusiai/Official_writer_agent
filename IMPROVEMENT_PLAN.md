# 公文写作智能体 -- 改进计划文档

> 基于两轮深度审查发现的问题，供日后修改参考。
> 审查日期：2026-07-27

---

## 目录

- [第一部分：参考资料库前后端不匹配](#第一部分参考资料库前后端不匹配)
- [第二部分：五上下文组件缺失分析](#第二部分五上下文组件缺失分析)
- [第三部分：其他前后端不匹配问题](#第三部分其他前后端不匹配问题)
- [改进路线图与优先级](#改进路线图与优先级)

---

## 第一部分：参考资料库前后端不匹配

### 1.1 问题概述

参考资料库（侧边栏"参考资料库"折叠面板）的后端数据结构采集了 13 个维度的信息，但前端 UI 只展示了 2 个维度（主题 + 标题），导致大量信息被浪费，交互体验极差。

### 1.2 后端数据结构（ImportedDocument）

文件：`src/utils/url_importer.py`

```python
@dataclass
class ImportedDocument:
    id: str = ""                    # 文档ID
    url: str = ""                   # 原始URL
    title: str = ""                 # 标题
    author: str = ""                # 作者
    publish_date: str = ""          # 发布日期
    source_site: str = ""           # 来源网站
    content: str = ""               # 正文
    raw_html: str = ""              # 原始HTML
    word_count: int = 0             # 字数
    format: DocumentFormat = ...    # 格式（新闻/公文/报告/博客/政策/未知）
    keywords: List[str] = ...       # 关键词列表
    extracted_at: str = ""          # 导入时间
    import_notes: str = ""          # 导入备注
    style_patterns: List[str] = ... # 语言特征列表
```

存储方式：`self.url_topics: Dict[str, List[ImportedDocument]]`（按主题分类的内存字典，持久化到 JSON 文件）

### 1.3 前端展示现状

文件：`gradio_app_v1.py` 第 2240-2263 行

当前 UI 组件：
- `gr.Dropdown` topic_selector -- 主题分类下拉框
- `gr.Dropdown` ref_doc_selector -- 参考文档下拉框（只显示标题）
- `gr.Button` url_import_trigger -- "导入新网页"按钮
- `gr.Button` ref_doc_delete_btn -- "移出素材"按钮
- URL 导入表单（隐藏）：URL 输入框 + 主题输入框 + 导入/取消按钮

### 1.4 前后端落差分析

| 后端已有的字段/能力 | 前端是否展示 | 浪费程度 | 改进价值 |
|---|---|---|---|
| `format`（新闻/公文/报告/政策/博客） | 否 | 严重浪费 | 可做多维度筛选 |
| `keywords`（关键词列表） | 否 | 严重浪费 | 可做搜索和标签展示 |
| `author`（作者） | 否 | 浪费 | 详情面板展示 |
| `publish_date`（发布日期） | 否 | 浪费 | 可做排序和时间线 |
| `source_site`（来源网站） | 否 | 浪费 | 可按来源筛选 |
| `word_count`（字数） | 否 | 浪费 | 可做排序 |
| `style_patterns`（语言特征） | 仅选中后显示 | 严重浪费 | 可做风格匹配推荐 |
| `content`（正文） | 选中后显示但无分页 | 体验差 | 需分页/滚动/搜索 |
| `url`（原始链接） | 否 | 浪费 | 可"打开原网页" |
| 主题分类 | 有下拉框 | -- | 但不能新建/重命名/删除 |
| URL 导入 | 有 | -- | 但导入后无自动分类建议 |
| 文档删除 | 有 | -- | 但不能批量删除 |
| 注入到写作素材 | 有 | -- | 但交互不直观 |

### 1.5 改造方案

#### P0 -- 核心痛点（必须改）

| 编号 | 改进项 | 说明 |
|---|---|---|
| P0-1 | 文档列表表格化 | 把下拉框替换为 `gr.Dataframe`，展示标题/格式/字数/日期/来源 |
| P0-2 | 多维度筛选 | 增加按格式（新闻/公文/报告）、按来源网站的筛选下拉框 |
| P0-3 | 搜索框 | 按标题/关键词/内容搜索文档 |
| P0-4 | 文档详情面板 | 选中文档后显示完整元数据 + 正文预览（带分页或滚动） |

#### P1 -- 体验提升（建议改）

| 编号 | 改进项 | 说明 |
|---|---|---|
| P1-1 | 主题管理 | 新建/重命名/删除主题 |
| P1-2 | 排序 | 按导入时间/字数/标题排序 |
| P1-3 | 批量操作 | 多选 + 批量删除/批量注入到写作素材 |
| P1-4 | 导入体验优化 | 导入后自动识别格式，建议主题分类 |

#### P2 -- 锦上添花（可选）

| 编号 | 改进项 | 说明 |
|---|---|---|
| P2-1 | 标签系统 | 给文档打自定义标签 |
| P2-2 | 文档对比 | 选两篇文档并排对比 |
| P2-3 | 收藏/置顶 | 常用文档置顶 |
| P2-4 | 导入历史 | 记录导入时间线 |

### 1.6 UI 布局设计

```
┌─ 参考资料库 ──────────────────────────────────────────────┐
│                                                            │
│  ┌─ 搜索栏 ─────────────────────────────────────────────┐  │
│  │ [搜索标题/关键词/内容...        ]  [搜索]            │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌─ 筛选栏 ─────────────────────────────────────────────┐  │
│  │ 主题: [全部v]  格式: [全部v]  来源: [全部v]  排序: [最新v] │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌─ 文档列表（Dataframe）──────────────────────────────┐  │
│  │ 选择 │ 标题              │ 格式 │ 字数 │ 日期       │ 来源    │  │
│  │------|--------------------|------|------|------------|---------|  │
│  │ [ ]  │ 关于深化教育改革.. │ 公文 │ 3200 │ 2025-07-15 │ 人民日报 │  │
│  │ [ ]  │ 新质生产力实践..   │ 新闻 │ 1800 │ 2025-07-20 │ 新华社   │  │
│  │ [ ]  │ 社会实践调研报告.. │ 报告 │ 5500 │ 2025-07-10 │ 学校官网 │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌─ 批量操作栏 ────────────────────────────────────────┐  │
│  │ [全选] [清空选择]  已选: 0 篇                        │  │
│  │ [批量删除] [批量注入到写作素材]                      │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌─ 文档详情面板（选中后展开）─────────────────────────┐  │
│  │ 标题: 关于深化教育改革的意见                          │  │
│  │ 作者: 张三 | 发布: 2025-07-15 | 来源: 人民日报        │  │
│  │ 格式: 公文 | 字数: 3,200 | 导入: 2025-07-20          │  │
│  │ 关键词: 教育改革, 新质生产力, 人才培养                 │  │
│  │ 语言特征: 多用短句, 善用数据支撑, 结构严谨             │  │
│  │ ────────────────────────────────────────────────    │  │
│  │ 正文预览:                                           │  │
│  │ 各省、自治区、直辖市人民政府...                      │  │
│  │ （滚动查看全文，或点击"展开全文"）                    │  │
│  │                                                     │  │
│  │ [编辑] [删除] [注入到写作素材] [打开原网页]          │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                            │
│  ┌─ 导入区（折叠）─────────────────────────────────────┐  │
│  │ [导入新网页]  [批量导入]  [管理主题]                 │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

### 1.7 Gradio 组件清单

| 区域 | 组件类型 | 变量名 | 功能 |
|---|---|---|---|
| 搜索 | `gr.Textbox` | `ref_search_box` | 输入关键词搜索标题/关键词/内容 |
| 主题筛选 | `gr.Dropdown` | `ref_filter_topic` | 按主题筛选（含"全部"选项） |
| 格式筛选 | `gr.Dropdown` | `ref_filter_format` | 按格式筛选（新闻/公文/报告/政策/博客/全部） |
| 来源筛选 | `gr.Dropdown` | `ref_filter_source` | 按来源网站筛选（动态生成选项） |
| 排序 | `gr.Dropdown` | `ref_sort_by` | 最新导入/最早导入/字数最多/标题排序 |
| 文档列表 | `gr.Dataframe` | `ref_doc_table` | 表格展示文档列表，支持点击选中行 |
| 全选/清空 | `gr.Checkbox` | `ref_select_all` | 全选/清空选择 |
| 批量删除 | `gr.Button` | `ref_batch_delete_btn` | 批量删除选中文档 |
| 批量注入 | `gr.Button` | `ref_batch_inject_btn` | 批量注入到写作素材区 |
| 详情面板 | `gr.Markdown` | `ref_doc_detail` | 显示选中文档的完整元数据+正文预览 |
| 展开全文 | `gr.Button` | `ref_expand_btn` | 切换预览/全文模式 |
| 编辑按钮 | `gr.Button` | `ref_edit_btn` | 进入编辑模式 |
| 删除按钮 | `gr.Button` | `ref_delete_btn` | 删除单篇文档 |
| 注入按钮 | `gr.Button` | `ref_inject_btn` | 注入到写作素材区 |
| 打开原网页 | `gr.Button` | `ref_open_url_btn` | 新窗口打开原始URL |
| 导入新网页 | `gr.Button` | `ref_import_btn` | 展开URL导入表单 |
| 管理主题 | `gr.Button` | `ref_manage_topics_btn` | 展开主题管理面板 |

### 1.8 需要新增的后端方法

```python
# 1. 搜索+筛选+排序文档
def search_ref_docs(self, query: str, topic: str, fmt: str, source: str, sort_by: str) -> List[Dict]:
    """搜索+筛选+排序，返回表格数据"""

# 2. 获取所有来源网站列表（动态生成）
def get_sources_list(self) -> List[str]:
    """从所有文档中提取不重复的 source_site"""

# 3. 获取所有格式列表
def get_formats_list(self) -> List[str]:
    """从所有文档中提取不重复的 DocumentFormat"""

# 4. 批量删除
def batch_delete_ref_docs(self, topic: str, titles: List[str]) -> Tuple[str, List]:
    """批量删除文档"""

# 5. 主题管理
def create_topic(self, name: str) -> str:
def rename_topic(self, old_name: str, new_name: str) -> str:
def delete_topic(self, name: str) -> str:

# 6. 获取文档详情（完整元数据）
def get_doc_detail(self, topic: str, title: str) -> str:
    """返回格式化的Markdown，包含所有元数据+正文预览"""
```

### 1.9 实现步骤

| 步骤 | 内容 | 难度 | 估计代码量 |
|---|---|---|---|
| 1 | 把 ref_doc_selector 下拉框替换为 gr.Dataframe | 中 | ~80行 |
| 2 | 添加搜索框+筛选下拉框+排序下拉框 | 低 | ~40行 |
| 3 | 实现搜索+筛选+排序的后端方法 | 中 | ~60行 |
| 4 | 添加文档详情面板（Markdown展示元数据+预览） | 低 | ~50行 |
| 5 | 添加批量选择+批量删除/注入功能 | 中 | ~50行 |
| 6 | 添加主题管理面板 | 低 | ~40行 |
| 7 | 绑定所有事件回调 | 中 | ~60行 |
| 合计 | | | ~380行 |

### 1.10 关键技术要点

1. **Dataframe 选择行**：Gradio 的 `gr.Dataframe` 支持 `on_select` 事件，点击行时触发回调
2. **搜索实时过滤**：搜索框用 `.change` 事件，输入时实时过滤
3. **来源网站动态选项**：每次列表更新时从所有文档中提取不重复的 `source_site`
4. **Dataframe 数据格式**：
   ```python
   headers = ["选择", "标题", "格式", "字数", "日期", "来源", "主题"]
   row_data = [
       [False, "关于深化教育改革...", "公文", 3200, "2025-07-15", "人民日报", "教育改革"],
   ]
   ```
5. **正文预览**：默认显示前500字 + "展开全文"按钮
6. **持久化**：所有增删改操作后调用 `self._save_persistent_data()`

---

## 第二部分：五上下文组件缺失分析

> 参照《深入理解 AI Agent》第1章：Agent = LLM + 上下文 + 工具
> 上下文由五个部分构成：系统提示词、工具定义、用户消息、模型回复、工具执行结果

### 2.1 组件一：系统提示词（System Prompt）-- 评分 3/10

#### 书中定义
由开发者编写，在整个对话过程中保持不变，相当于Agent的"岗位说明书"。包含：角色身份、行为准则、用户记忆（跨会话）、动态环境状态。

#### 项目现状

**设计层面（6分）**：有一个设计非常完善的 `src/config/system_prompt.py`（327行），包含：
- 静态核心（165行）：角色身份、核心理念、能力矩阵（5模式+5文种+5风格）、工作流程状态机、行为准则（6类）、规范体系（4梯队）、红线（7条禁止行为）
- 动态注入：用户记忆模板 + EnvState 环境状态（模式/文种/风格/阶段/目的/读者/篇幅等10个字段）
- 构建函数：`build_system_prompt(user_memory, env_state) -> str`

**落地层面（0分）**：这个模块在实际写作流程中 **没有被调用**。
- `src/core/writer_agent.py` 第106行有自己的 `build_system_prompt()` 方法
- writer_agent 构建了一套完全不同的简化版 prompt（角色定义+原则+简报+文种+风格）
- 完全绕过了 `system_prompt.py` 中精心设计的完善版本
- `system_prompt.py` 实际上是死代码

#### 问题清单

| 问题编号 | 问题描述 | 影响 |
|---|---|---|
| SP-1 | system_prompt.py 未被 writer_agent 调用 | 165行精心设计的静态核心提示词被浪费 |
| SP-2 | 两套 system prompt 并存，职责混乱 | 维护困难，行为不一致 |
| SP-3 | writer_agent 版本缺少用户记忆注入 | 跨会话个性化能力丢失 |
| SP-4 | writer_agent 版本缺少环境状态注入 | LLM不知道当前工作流阶段 |
| SP-5 | system_prompt.py 的 EnvState 未与 orchestrator 状态机联动 | 环境状态数据来源未接通 |

#### 修复方案

1. **统一 system prompt 来源**：让 writer_agent 调用 `system_prompt.py` 的 `build_system_prompt()`，删除 writer_agent 自己的简化版
2. **接通 EnvState 数据源**：从 orchestrator 的当前状态（writing_mode / stage / doc_type / media_style 等）自动构建 EnvState
3. **接通用户记忆数据源**：从 `personalized_db.py` 的用户画像（偏好/历史/常见错误）自动构建 user_memory 文本

### 2.2 组件二：工具定义（Tool Definitions）-- 评分 0/10

#### 书中定义
声明Agent可用工具的名称、功能描述和参数格式。没有工具定义，Agent就无法识别和调用任何工具。

#### 项目现状

**完全缺失**。项目有7个专用工具，但没有任何地方向LLM声明这些工具的存在：

| 已有工具 | 功能 | LLM是否知道 |
|---|---|---|
| 知识库（knowledge_base.py） | 错误诊断、范文推荐、术语查询 | 否 |
| 个性化数据库（personalized_db.py） | 用户画像、风格推荐、记忆管理 | 否 |
| 风格适配器（style_adapter.py） | 风格选择、混合风格、强度调节 | 否 |
| 文种识别器（document_type.py） | 文种推荐、模板生成 | 否 |
| URL导入器（url_importer.py） | 网页抓取、格式识别 | 否 |
| 写作Agent（writer_agent.py） | prompt构建、初稿生成 | 否 |
| 审稿Agent（reviewer_agent.py） | 错误诊断、自动修复、迭代审查 | 否 |

所有工具调用都是Python代码在固定流程中写死执行的。LLM只是一个"收到prompt然后生成文本"的模型。

#### 问题清单

| 问题编号 | 问题描述 | 影响 |
|---|---|---|
| TD-1 | 没有工具定义声明 | LLM无法自主选择调用工具 |
| TD-2 | 没有使用 function calling / tool calling API | 无法实现ReAct循环 |
| TD-3 | 工具调用结果被被动拼接进prompt | LLM不知道结果是"工具返回的" |
| TD-4 | 没有工具调用的错误处理和重试机制 | 工具失败时LLM无法感知 |

#### 修复方案

**短期（不改变架构）**：
- 在 system prompt 中声明可用工具的名称和功能描述
- 让LLM在输出中可以"建议"使用某个工具（由代码执行）
- 例如：LLM输出 `[建议调用：知识库诊断]`，代码解析后执行

**中期（引入 function calling）**：
- 使用 OpenAI/DeepSeek 等模型的 function calling API
- 将7个工具注册为 functions，LLM可自主决定调用
- 实现 Thought -> Action -> Observation 循环

**长期（完整 ReAct）**：
- 参照《深入理解 AI Agent》第4章实现完整的工具调用循环
- 支持 MCP 协议
- 实现主动工具发现

### 2.3 组件三：用户消息（User Messages）-- 评分 7/10

#### 书中定义
来自用户的输入，可能包含通过RAG动态检索引入的外部知识。

#### 项目现状

**做得好的**：
- 问卷系统收集7个维度的用户输入 -> WritingBrief（purpose / primary_audience / deep_meaning / strategic_anchor / opportunity_context / key_materials / differentiator）
- 素材区允许用户粘贴额外材料
- URL导入的参考文档可注入素材区
- 多智能体协商时把用户立场（UserProxy角色）纳入

**缺失的**：
- 没有 RAG（检索增强生成）
- 知识库范文是按写作模式选择注入的（`get_exemplars_for_prompt(mode)`），不是按语义相关性检索的
- 用户说"我想参考关于教育改革的文章"，系统无法从已导入文档中语义检索
- 搜索是精确匹配，不是语义匹配

#### 问题清单

| 问题编号 | 问题描述 | 影响 |
|---|---|---|
| UM-1 | 没有RAG语义检索 | 参考资料无法按相关性推荐 |
| UM-2 | 范文注入按模式固定选择 | 同一模式的用户看到相同范文，无法个性化 |
| UM-3 | 用户消息没有多轮对话历史 | 每次写作是独立的，无法"上次你帮我改的那篇" |

#### 修复方案

1. **引入向量检索**：对已导入文档和知识库范文建立向量索引，按语义相关性检索
2. **个性化范文推荐**：结合用户画像（常用风格/常见弱点）推荐最相关的范文
3. **对话历史**：保存用户的写作历史和交互记录，支持跨会话引用

### 2.4 组件四：模型回复（Assistant Messages）-- 评分 4/10

#### 书中定义
模型之前生成的回复，包含三部分：reasoning（思考过程）、content（文本内容）、tool_calls（工具调用请求）。

#### 项目现状

| 部分 | 实现情况 | 状态 |
|---|---|---|
| content（文本内容） | writer_agent生成的草稿、reviewer_agent的审查意见 | 有 |
| reasoning（思考过程） | 没有保存 | 缺失 |
| tool_calls（工具调用） | 不存在 | 不适用 |

**其他问题**：
- 多轮审查的历史草稿没有完整保存（只存最终版）
- 无法回溯"上一版为什么被改""改了什么"
- 审查意见（ReviewResult）保存了但未与草稿版本关联

#### 问题清单

| 问题编号 | 问题描述 | 影响 |
|---|---|---|
| AM-1 | 没有保存LLM的reasoning | 思考链丢失，无法调试和教学 |
| AM-2 | 多轮审查历史不完整 | 无法回溯修改过程 |
| AM-3 | 审查意见与草稿版本未关联 | 不知道哪个意见对应哪版草稿 |

#### 修复方案

1. **保存reasoning**：如果使用支持reasoning的模型（如DeepSeek-R1），保存思考链
2. **完整保存审查历史**：每轮审查的草稿、发现的问题、修复记录、评分都保存
3. **版本关联**：审查意见与草稿版本建立关联，支持版本回溯

### 2.5 组件五：工具执行结果（Tool Results）-- 评分 3/10

#### 书中定义
Agent框架执行工具后返回的结果，是Agent下一步思考的直接依据。

#### 项目现状

有工具执行结果，但 **不是LLM主动调用工具获得的**，而是Python代码在固定流程中调用后被动拼接进prompt的。

LLM视角：
```
收到一段超长prompt（里面已经混入了知识库诊断结果、范文参考、风格指导）
-> 生成一篇文章
```

Agent视角（缺失的）：
```
LLM思考：我需要检查这篇文章有没有常见错误
LLM调用工具：diagnose_errors(draft)
工具返回：发现3个错误
LLM思考：我修复这3个错误
LLM调用工具：apply_fixes(draft, findings)
工具返回：修复后的文本
LLM思考：再检查一遍
LLM调用工具：diagnose_errors(fixed_draft)
工具返回：没有错误了
LLM输出：最终稿
```

#### 问题清单

| 问题编号 | 问题描述 | 影响 |
|---|---|---|
| TR-1 | 工具结果被被动拼接而非主动获取 | LLM无法决定是否需要工具 |
| TR-2 | 没有工具调用的交互闭环 | 无法实现"调用->观察->决策"循环 |
| TR-3 | 工具失败时LLM无法感知 | 工具出错时LLM继续基于错误数据生成 |

#### 修复方案

1. **短期**：工具执行结果以结构化格式注入prompt，让LLM知道"这是工具返回的结果"
2. **中期**：实现 function calling，LLM主动调用工具
3. **长期**：实现完整的 ReAct 循环（Thought -> Action -> Observation）

---

## 第三部分：其他前后端不匹配问题

> 系统审查发现，除参考资料库外还有7处"后端数据丰富、前端展示不足"的问题。
> 审查方式：对每个后端模块的公开方法在 gradio_app_v1.py 中搜索调用情况。

### 汇总表

| 序号 | 模块 | 后端能力 | 前端展示 | 浪费程度 | 编号 |
|---|---|---|---|---|---|
| 1 | 词汇语料库 | 4个方法 | 0% | 严重 | VB-1 |
| 2 | 文种识别器 | 4个方法+16种文种模板 | 0% | 严重 | DT-1 |
| 3 | 多智能体协商 | 5个方法+消息总线 | 0% | 严重 | AC-1 |
| 4 | Token优化器/成本 | 3个方法+统计 | 0% | 严重 | TO-1 |
| 5 | 知识库诊断查询 | 8个方法 | 间接使用，结果不可见 | 中等 | KB-1 |
| 6 | 风格适配器 | 4个方法+5大风格 | 间接使用，无用户控制 | 中等 | SA-1 |
| 7 | 审查迭代历史 | iteration_results | 最终结果有，过程缺失 | 轻微 | RH-1 |

---

### 3.1 词汇语料库（VB-1）-- 完全未使用

**后端**（`src/core/personalized_db.py`）：

| 方法 | 功能 |
|---|---|
| `create_vocabulary_corpus(project_id)` | 为项目创建词汇语料库 |
| `add_custom_term(project_id, term, ...)` | 添加自定义术语 |
| `add_forbidden_word(project_id, word, ...)` | 添加禁用词 |
| `add_required_keyword(project_id, keyword)` | 添加必含关键词 |

**前端现状**：完全没有调用。搜索 `vocabulary`、`forbidden_word`、`required_keyword`、`custom_term` -- 零匹配。

**用户影响**：用户无法为项目设置"必须包含的关键词"（如领导姓名、会议名称）、"禁止使用的词"（如过时表述）、"自定义术语表"（如单位内部简称）。这些对公文写作非常实用。

**修复建议**：在项目设置面板增加"词汇管理"区域：
- 必含关键词列表（可增删）
- 禁用词列表（可增删）
- 自定义术语表（术语+定义，可增删）
- 写作时自动注入到 prompt，审查时自动检查是否包含/避免

---

### 3.2 文种识别器（DT-1）-- 完全未在前端使用

**后端**（`src/core/document_type.py`）：

| 方法 | 功能 |
|---|---|
| `analyze_materials(key_materials)` | 分析素材与各文种的匹配度 |
| `identify(brief) -> List[(profile, score)]` | 文种推荐（带置信度排序） |
| `get_all_profiles()` | 获取全部16种文种的完整模板 |
| `generate_template_prompt(profile)` | 生成文种的结构模板prompt |

**前端现状**：搜索 `DocumentTypeIdentifier`、`analyze_materials`、`identify`、`get_all_profiles`、`generate_template_prompt` -- 零匹配。

**用户影响**：
- 用户写完问卷后不知道系统推荐了什么文种、为什么推荐
- 用户看不到16种文种的结构模板（开篇/正文/结尾模板）
- 用户无法手动选择或切换文种

**修复建议**：在写作简报确认面板增加"文种推荐"区域：
- 展示Top 3推荐文种及置信度（如：通讯 85%、侧记 72%、消息 61%）
- 展示选中文种的结构模板（开篇/正文/结尾）
- 允许用户手动覆盖推荐结果

---

### 3.3 多智能体协商过程（AC-1）-- 完全未展示

**后端**（`src/core/agent_coordinator.py`）：

| 方法/类 | 功能 |
|---|---|
| `consult_before_decision(...)` | 多智能体协商（6角色并行） |
| `run_debate(...)` | 辩论机制（冲突时达成共识） |
| `MessageBus` | 消息总线（订阅/发布） |
| `get_communication_stats()` | 通信统计 |
| `_history` | 完整协商历史记录 |

**前端现状**：搜索 `agent_coordinator`、`consult_before`、`run_debate`、`MessageBus`、`communication_stats` -- 零匹配。前端有 `coord_agent_logs` 组件，但展示的是 orchestrator 生成的文本摘要，不是原始协商数据。

**用户影响**：多智能体协商是项目核心卖点之一，但用户完全看不到：
- 各角色（Writer/Reviewer/StyleAdvisor/KnowledgeKeeper/DocTypeAnalyst/UserProxy）分别提了什么意见
- 意见冲突时的辩论过程
- 最终决策是如何达成的

**修复建议**：在规划阶段增加"协商过程"展开面板：
- 按角色展示各方意见（卡片式布局）
- 标注冲突点和辩论结果
- 展示通信统计（总消息数、辩论轮数等）

---

### 3.4 Token优化器与成本统计（TO-1）-- 完全未展示

**后端**（`src/utils/token_optimizer.py` + `src/core/orchestrator.py`）：

| 方法/属性 | 功能 |
|---|---|
| `optimize_prompt(...) -> (sys, user, TokenStats)` | 优化prompt并返回统计 |
| `estimate_cost(input, output, ...) -> Dict` | 成本估算 |
| `get_optimization_report() -> str` | 优化报告 |
| `orchestrator._api_call_count` | API调用次数 |
| `orchestrator._total_tokens_saved` | 缓存节省的token数 |
| `orchestrator._api_fail_count` | API失败次数 |

**前端现状**：搜索 `token_optim`、`estimate_cost`、`optimization_report`、`token_stats`、`api_call_count`、`tokens_saved` -- 零匹配。

**用户影响**：
- 用户不知道每次写作消耗了多少token、花了多少钱
- 用户不知道缓存节省了多少成本
- 用户不知道API调用了几次、失败了几次

**修复建议**：在写作完成面板增加"本次写作统计"区域：
- Token消耗：输入X / 输出Y / 共Z
- 预估成本：约￥X.XX
- 缓存节省：节省了N个token（约￥X.XX）
- API调用：成功N次 / 失败M次

---

### 3.5 知识库诊断与查询（KB-1）-- 间接使用但结果不可见

**后端**（`src/knowledge/knowledge_base.py`）：

| 方法 | 功能 | 前端是否可见 |
|---|---|---|
| `diagnose_text(text)` | 错误诊断 | 间接（通过reviewer_agent） |
| `diagnose_format(text)` | 格式诊断 | 间接（通过reviewer_agent） |
| `lookup_term(term)` | 术语查询 | 不可见 |
| `get_transitions(style, count)` | 过渡词获取 | 不可见 |
| `get_writing_tips(doc_type, style)` | 写作提示 | 不可见 |
| `get_formulaic_for_prompt(doc_type)` | 格式化用语 | 间接（通过writer_agent） |
| `get_style_exemplar_summary(style)` | 风格范文摘要 | 不可见 |
| `search_exemplars(...)` | 范文搜索 | 不可见 |

**前端现状**：这些方法在 reviewer_agent / writer_agent 内部被调用了，但诊断过程和查询结果没有直接展示给用户。

**用户影响**：
- 用户只看到审查总结文本，不知道知识库诊断了哪些具体错误
- 用户看不到推荐了哪些过渡词和格式化用语
- 用户查不到术语解释
- 用户看不到写作提示

**修复建议**：
- 审查面板增加"知识库诊断详情"展开区（展示diagnose_text的完整结果）
- 写作面板增加"写作提示"侧栏（展示get_writing_tips的结果）
- 增加术语查询入口（用户输入术语 -> lookup_term -> 展示解释）

---

### 3.6 风格适配器（SA-1）-- 前端交互缺失

**后端**（`src/core/style_adapter.py`）：

| 方法 | 功能 | 前端是否可交互 |
|---|---|---|
| `list_styles()` | 列出5大媒体风格及特征 | 否 |
| `auto_select_style(audience, purpose)` | 自动选择风格 | 否（后台自动） |
| `get_system_prompt_injection_with_intensity(profile, 0.8)` | 带强度调节的注入 | 否 |
| `suggest_blend(...)` | 混合风格建议 | 否（后台自动） |

**前端现状**：只通过 orchestrator 间接调用了 `suggest_blend()`。用户无法：
- 看到所有可选的5大媒体风格及其特征描述
- 手动选择/切换风格
- 调节风格强度（0.0-1.0）
- 看到混合风格建议（如"70%人民日报+30%新华社"）

**修复建议**：在写作简报确认面板增加"风格选择"区域：
- 风格下拉框（5大风格+自动选择）
- 风格强度滑块（0.0-1.0）
- 混合风格建议展示（如适用）
- 各风格的特征描述（情感基调/数据密度/文学性/政策关联度）

---

### 3.7 审查迭代历史（RH-1）-- 部分缺失

**后端**（`src/core/reviewer_agent.py`）：

| 数据 | 前端是否展示 |
|---|---|
| `review_summary_text`（审查得分与总结） | 是 |
| `review_issues_list`（问题列表） | 是 |
| `review_heatmap_html`（热力图） | 是 |
| `iteration_results`（每轮迭代的详细记录） | **否** |

**前端现状**：展示了审查的最终结果，但 **每轮迭代的详细过程没有展示**。用户只看到最终版，不知道：
- 审查了几轮
- 每轮发现了什么问题
- 每轮修复了什么
- 修复前的版本是什么样的

**修复建议**：在审查面板增加"迭代历史"时间线：
- 第1轮：发现3个问题（主体性不足/流水账/AI味）-> 修复2个 -> 得分65
- 第2轮：发现1个问题（格式不规范）-> 修复 -> 得分82
- 第3轮：无新问题 -> 通过 -> 得分91
- 每轮可点击展开查看修改前后的对比

---

## 改进路线图与优先级

### 优先级矩阵

```
紧急且重要（立即做）          重要但不紧急（计划做）
┌─────────────────────┐    ┌─────────────────────┐
│ SP-1: 接入           │    │ TD-2: 引入function   │
│ system_prompt.py     │    │ calling API          │
│                      │    │                      │
│ SP-2: 统一prompt来源  │    │ UM-1: 引入RAG向量检索│
│                      │    │                      │
│ P0-1~P0-4: 参考资料库 │    │ AM-1: 保存reasoning  │
│ 核心改造              │    │                      │
│                      │    │ AC-1: 多智能体协商    │
│ DT-1: 文种推荐展示    │    │ 过程展示              │
│                      │    │                      │
│ SA-1: 风格选择交互    │    │ KB-1: 知识库诊断结果  │
│                      │    │ 可见化                │
└─────────────────────┘    └─────────────────────┘

紧急但不重要（快速做）       不紧急不重要（暂缓）
┌─────────────────────┐    ┌─────────────────────┐
│ AM-2: 保存审查历史    │    │ P2-1~P2-4: 参考资料库│
│                      │    │ 高级功能              │
│ TR-1: 结构化工具结果   │    │                      │
│                      │    │ TD-3: MCP协议         │
│ SP-3: 接通用户记忆     │    │                      │
│                      │    │ VB-1: 词汇语料库      │
│ TO-1: 成本统计展示    │    │                      │
│                      │    │                      │
│ RH-1: 审查迭代历史    │    │                      │
└─────────────────────┘    └─────────────────────┘
```

### 实施路线

#### 第一阶段：修复死代码 + 前端核心缺失（投入小，收益大）

| 任务 | 涉及文件 | 估计工作量 |
|---|---|---|
| SP-1: 让 writer_agent 调用 system_prompt.py | writer_agent.py | 小（改1处调用） |
| SP-4: 接通 EnvState 数据源 | orchestrator.py + system_prompt.py | 中（构建EnvState） |
| SP-3: 接通用户记忆数据源 | orchestrator.py + personalized_db.py | 中（构建user_memory） |
| AM-2: 保存多轮审查历史 | reviewer_agent.py + orchestrator.py | 中（增加历史记录） |
| DT-1: 文种推荐展示 | gradio_app_v1.py | 小（~40行） |
| SA-1: 风格选择交互 | gradio_app_v1.py | 小（~50行） |

#### 第二阶段：参考资料库改造 + 其他前端补全

| 任务 | 涉及文件 | 估计工作量 |
|---|---|---|
| P0-1: Dataframe替换下拉框 | gradio_app_v1.py | 中（~80行） |
| P0-2: 多维度筛选 | gradio_app_v1.py | 小（~40行） |
| P0-3: 搜索框 | gradio_app_v1.py | 小（~40行） |
| P0-4: 文档详情面板 | gradio_app_v1.py | 中（~50行） |
| P1-1~P1-4: 体验提升 | gradio_app_v1.py | 中（~150行） |
| TO-1: 成本统计展示 | gradio_app_v1.py + orchestrator.py | 小（~30行） |
| RH-1: 审查迭代历史时间线 | gradio_app_v1.py | 中（~60行） |
| KB-1: 知识库诊断详情展示 | gradio_app_v1.py | 中（~50行） |
| AC-1: 多智能体协商过程展示 | gradio_app_v1.py + orchestrator.py | 中（~80行） |

#### 第三阶段：向Agent进化（需要学习新知识）

| 任务 | 前置知识 | 估计工作量 |
|---|---|---|
| TD-1: 在prompt中声明工具 | 无 | 小 |
| TD-2: 引入function calling | OpenAI/DeepSeek function calling API | 大 |
| TR-2: 实现工具调用闭环 | ReAct循环原理 | 大 |
| UM-1: 引入RAG | 向量数据库 + embedding | 大 |

### 推荐学习资源

- 《深入理解 AI Agent》第1章：Agent基础知识（Agent = LLM + 上下文 + 工具）
- 《深入理解 AI Agent》第2章：上下文工程（KV Cache、提示工程、上下文压缩）
- 《深入理解 AI Agent》第3章：用户记忆和知识库（RAG、结构化索引）
- 《深入理解 AI Agent》第4章：工具（MCP协议、工具定义、事件驱动）

---

## 附录：相关文件索引

| 文件 | 路径 | 角色 |
|---|---|---|
| 系统提示词 | `src/config/system_prompt.py` | 静态核心+动态注入（当前是死代码） |
| 写作Agent | `src/core/writer_agent.py` | 实际使用的简化版system prompt |
| 编排器 | `src/core/orchestrator.py` | 状态机+流程编排 |
| 审稿Agent | `src/core/reviewer_agent.py` | 多轮审查+自动修复 |
| 知识库 | `src/knowledge/knowledge_base.py` | 范文+错误诊断+术语 |
| 个性化数据库 | `src/core/personalized_db.py` | 用户画像+项目管理+记忆 |
| 风格适配器 | `src/core/style_adapter.py` | 5大媒体风格模板 |
| 文种识别器 | `src/core/document_type.py` | 16种文种推荐 |
| URL导入器 | `src/utils/url_importer.py` | 网页抓取+格式识别 |
| 响应缓存 | `src/utils/response_cache.py` | LRU缓存（已加锁） |
| Token优化器 | `src/utils/token_optimizer.py` | 压缩+路由+成本估算 |
| Gradio前端 | `gradio_app_v1.py` | 主入口（3200+行） |
| 问卷系统 | `src/questionnaire/questionnaire.py` | 决策树+模式问题 |
| 写作模式 | `src/core/writing_mode.py` | 5模式+决策树+审查维度 |

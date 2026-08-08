# 公文写作智能体 · 五上下文组件审查报告

> 审查日期：2026-08-02
> 审查标准：以"真正 Agent"的五个上下文组件为基准（系统提示词、工具定义、用户消息、模型回复、工具执行结果）
> 审查方法：逐一读取 7 个核心文件，交叉验证 token_optimizer.py、questionnaire.py 等关联模块

---

## 评分总览

| 组件 | 上轮评分 | 本轮评分 | 变化 |
|------|---------|---------|------|
| 1. 系统提示词 | 6/10 | **6/10** | 持平（EnvState 修复被新发现问题抵消） |
| 2. 工具定义 | 7/10 | **5/10** | ↓（发现参数名 Bug + 正则脆弱 + 无权限模型） |
| 3. 用户消息 | 7/10 | **4/10** | ↓（发现单轮无状态是核心架构缺陷） |
| 4. 模型回复 | 8/10 | **5/10** | ↓（发现 assistant 消息不存历史 + 解析脆弱） |
| 5. 工具执行结果 | 8/10 | **4/10** | ↓（发现结果不回传 LLM 是核心架构缺陷） |

**平均分：7.2 → 4.8**

评分下降不是因为退步了，而是上一轮评分标准不够深。这次用了"真正 Agent"标准（多轮对话、原生 function calling、tool 角色消息回传），发现了贯穿性的架构缺陷。

---

## 组件一：系统提示词（6/10）

### 当前实现

| 文件 | 做了什么 |
|------|----------|
| `system_prompt.py` | 定义 `_CORE_SYSTEM_PROMPT` 静态核心提示词（角色/理念/能力/流程/准则/规范/红线），提供 `EnvState` 数据类和 `render()` 方法 |
| `writer_agent.py` | `build_system_prompt()` 拼接核心提示词 + 模式配置 + EnvState + 用户记忆 + 写作简报 + 文种规范 + 风格要求 + 工具清单 |
| `orchestrator.py` | `write()` 构建 `EnvState` 并注入 `WriterConfig`；`_run_llm_deep_review()` 自行拼接审查员系统提示词 |

### 不足

**1. EnvState 渲染逻辑重复，存在漂移风险**
- 位置：`writer_agent.py:193-214`
- `system_prompt.py` 第 235-257 行定义了 `EnvState.render()` 方法，但 `writer_agent.py` 没有调用它，而是手动重新拼装了同样的字段（writing_mode/subtype/stage/media_style/extra）。两处逻辑独立维护，一旦 EnvState 增加字段，writer_agent 的手动渲染不会自动同步。

**2. 审查员系统提示词缺失 EnvState 和 user_memory**
- 位置：`orchestrator.py:1150-1166`
- `_run_llm_deep_review()` 构建审查员系统提示词时，直接拼接 `get_core_prompt()` + ad-hoc 审查指令 + 工具定义。完全没有注入 EnvState（审查员不知道当前处于哪个工作流阶段、什么模式），也没有注入 user_memory（审查员不知道用户的常见错误模式）。

**3. 用户记忆注入缺乏结构化格式**
- 位置：`writer_agent.py:217-223`
- `user_memory` 作为纯文本字符串注入，LLM 无法区分"偏好"、"历史错误"、"禁用词"等不同类型的记忆。

**4. EnvState 缺少迭代上下文维度**
- 位置：`system_prompt.py:219-233`
- EnvState 包含 writing_mode/stage/doc_type 等，但没有 `iteration_count`（当前审查轮次）、`previous_issues`（上一轮发现的问题）、`draft_version`（草稿版本号）。审查员在多轮迭代审查时，无法感知"这是第几轮、上一轮修了什么"。

**5. ContextManager.build_context() 已实现但从未接入 LLM 调用**
- 位置：`token_optimizer.py:288-297` / `orchestrator.py:691-693`
- `ContextManager` 实现了 `build_context()` 方法用于构建多轮消息列表，但 `_call_llm` 从未调用它。多轮记忆的基础设施存在，但完全断线。

### 与"真正 Agent"的差距

| 标准 | 当前状态 |
|------|----------|
| 系统提示词包含用户记忆 | 有，但为非结构化纯文本 |
| 系统提示词包含动态环境状态 | Writer 有，Reviewer 无 |
| 系统提示词包含历史摘要 | 基础设施存在但未接入 |
| 所有 Agent 角色共享一致的环境感知 | 否，Writer 和 Reviewer 的 prompt 组装逻辑割裂 |

---

## 组件二：工具定义（5/10）

### 当前实现

`tool_definitions.py` 定义了 17 个工具（知识库 7 个 / 文种识别 2 个 / 风格适配 3 个 / 个性化 3 个 / 导入 2 个），通过 `get_tool_definitions_for_prompt()` 渲染为文本注入系统提示词，通过 `parse_tool_call()` 用正则解析 `[TOOL_CALL: ...]` 标记。

### 不足

**1. 未使用原生 Function Calling API（头号差距）**
- 位置：`tool_definitions.py:7-9`
- 全局搜索 `tools=`、`tool_choice`、`functions=` 在 `src/` 下零匹配。LLM 无法结构化地发起工具调用，只能把调用请求"写"在文本里。工具参数无法类型校验，无法支持 parallel tool calls。

**2. 工具参数无 JSON Schema，缺乏约束**
- 位置：`tool_definitions.py:22-28`
- `ToolParam` 只有 name/type/required/description/default。缺少 `enum`（可选值枚举）、`minimum`/`maximum`（如 intensity 应限定 0.0-1.0）、`pattern`（正则校验）、嵌套对象支持。

**3. parse_tool_call() 正则解析脆弱**
- 位置：`tool_definitions.py:336-348`
- 正则 `r'\[TOOL_CALL:\s*(\w+)\s*\(([^)]*)\)\]'` 无法处理参数值中包含 `)` 的情况
- 按逗号分割参数 `params_str.split(',')`，无法处理值中包含逗号的情况
- 所有参数值都是字符串，不会根据 ToolParam.type 转换为 int/float/bool

**4. suggest_style_blend 参数名与执行代码不匹配（确定性 Bug）**
- 位置：`tool_definitions.py:184-196` / `orchestrator.py:922-925`
- 工具定义的参数名：`primary_style` / `secondary_style` / `intensity`
- 执行代码读取的参数名：`primary_audience` / `purpose` / `secondary_audiences`
- 参数名完全不匹配，LLM 按定义传参时执行端读不到值

**5. 工具定义重复注入，造成 Token 浪费**
- 位置：`writer_agent.py:294-297` / `orchestrator.py:1157-1159`
- 全部 17 个工具定义同时注入 Writer 和 Reviewer 的系统提示词。审查员不需要"导入工具"和"风格适配工具"，但无法按角色过滤。

**6. 无工具执行权限模型**
- 所有 Agent 角色看到所有工具。真正的 Agent 应该：Writer 只能用 during_writing 工具，Reviewer 只能用 post_writing 工具。

**7. 无工具执行超时和重试机制**
- 位置：`orchestrator.py:842-1033`
- `_execute_tool_call` 没有 timeout 参数。如果 `import_from_url` 抓取网页卡住，整个写作流程阻塞。

### 与"真正 Agent"的差距

| 标准 | 当前状态 |
|------|----------|
| 原生 function calling | 否，文本标记解析 |
| JSON Schema 参数校验 | 否，仅 name/type 声明 |
| 工具结果类型安全 | 否，全为字符串 |
| 按角色分配工具权限 | 否，所有工具注入所有角色 |
| Parallel tool calls | 不支持 |

---

## 组件三：用户消息（4/10）

### 当前实现

用户消息有三个来源：
1. 问卷答案 → 汇总为 `WritingBrief` → 注入 Writer 系统提示词（非 user 消息）
2. 原始素材 → `WriterAgent.build_user_prompt()` 构建为 user 消息
3. 多智能体协商决策 → 追加到 user 消息末尾

### 不足

**1. LLM 调用始终是单轮无状态（核心架构缺陷）**
- 位置：`orchestrator.py:691-693`
- 每次 LLM 调用只发送 system + user 两条消息，没有任何对话历史。LLM 不知道自己上一轮说了什么，审查员不知道 Writer 写了什么推理过程，多轮审查时 LLM 不知道前几轮发现了什么问题。

**2. ContextManager 已实现但未接入 LLM 调用**
- 位置：`token_optimizer.py:288-297` / `orchestrator.py:126`
- `ContextManager.build_context()` 本可以构建多轮消息列表，`orchestrator.py` 实例化了 `self._context_manager`，但 `_call_llm` 从未调用 `build_context()`。在 `agent_coordinator.py:753-761`，`ContextManager.add_message()` 被调用来记录协商历史，但这些记录从未被用于构建实际的 API 请求。

**3. 问卷 Q&A 上下文丢失**
- 位置：`gradio_app_v1.py:603-702`
- 用户的问卷答案通过 `submit_mode_answer()` 收集到 `WritingBrief`，但 LLM 只看到 WritingBrief 的汇总字段（purpose/audience/deep_meaning 等），看不到用户的原始措辞和完整回答。

**4. 无 RAG 动态检索管道**
- 位置：`writer_agent.py:283-291`
- 范文参考是预注入的，基于 writing_mode 静态检索，不是基于用户具体输入动态检索。无向量检索、无语义搜索、无实时知识更新。

**5. 协商决策上下文以非结构化方式追加**
- 位置：`orchestrator.py:524-525`
- 协商结果直接拼到 user 消息末尾，LLM 无法区分"这是写作指令"还是"这是协商建议"。

**6. 无用户意图澄清机制**
- 如果用户输入模糊，系统没有 LLM 驱动的追问能力。问卷问题是预定义的，不是基于用户输入动态生成的。

### 与"真正 Agent"的差距

| 标准 | 当前状态 |
|------|----------|
| 多轮对话历史 | 否，单轮 system+user |
| RAG 动态检索 | 否，静态预注入 |
| 用户原始上下文保留 | 部分，被汇总压缩 |
| 意图澄清追问 | 否，预定义问卷 |
| ContextManager 接入 | 否，已实现但断线 |

---

## 组件四：模型回复（5/10）

### 当前实现

`orchestrator.py` 的 `_call_llm` 提取 `reasoning_content`（DeepSeek-R1 风格思考链）存入 `_llm_reasonings`，解析 `[TOOL_CALL: ...]` 标记执行工具，`_parse_llm_review()` 用正则解析审查结果。

### 不足

**1. 无原生 tool_calls 支持**
- 位置：`orchestrator.py:732`
- 只提取 `content` 字段，不读取 `message.tool_calls`。即使模型支持 function calling，本系统也无法接收结构化的工具调用请求。

**2. reasoning 提取仅支持 DeepSeek 格式**
- 位置：`orchestrator.py:737`
- 只读取 `reasoning_content` 字段。不支持 OpenAI o1/o3 的 `reasoning` summary、Anthropic Claude 的 `thinking` block 等。

**3. 模型回复不存入对话历史**
- 位置：`orchestrator.py:749`
- `_call_llm` 返回 content 字符串后，既不存储为 assistant 角色消息，也不在后续调用中回传。`_llm_reasonings` 仅用于调试展示，不参与后续 LLM 推理。

**4. 审查结果解析脆弱，无结构化输出保障**
- 位置：`orchestrator.py:1199-1285`
- 用 4 个正则匹配"问题N：""位置：""严重程度：""建议："。如果 LLM 输出格式略有偏差，解析会失败。兜底逻辑把整个原文当成一个"问题"返回，严重降低审查质量。未使用 JSON Mode 或 Structured Output。

**5. 内容验证过于简陋**
- 位置：`orchestrator.py:733`
- 只检查非空且长度 >= 2。不检查是否包含占位文本、是否符合预期格式、长度是否在合理范围、是否包含幻觉内容。

**6. 工具调用标记格式错误被静默忽略**
- 位置：`orchestrator.py:818-820`
- 如果 LLM 输出了格式错误的 `[TOOL_CALL: ...]`，`parse_tool_call` 返回空列表，标记原样留在文本中，用户会看到残留的 `[TOOL_CALL: diagnose_text(text=...)]`。

**7. reasoning 内容不回传 LLM**
- `_llm_reasonings` 存储了思考链，但这些推理过程从不注入后续 LLM 调用。在多轮审查中，审查员无法参考自己上一轮的推理过程。

### 与"真正 Agent"的差距

| 标准 | 当前状态 |
|------|----------|
| 原生 tool_calls 解析 | 否，文本标记 |
| 结构化输出（JSON/function） | 否，正则解析 |
| 多模型 reasoning 兼容 | 否，仅 DeepSeek |
| assistant 消息存入历史 | 否，单轮丢弃 |
| 输出质量校验 | 极简（长度>=2） |

---

## 组件五：工具执行结果（4/10）

### 当前实现

`orchestrator.py` 的 `_process_tool_calls()` 解析文本中的工具调用标记，调用 `_execute_tool_call()` 执行，将结果以 `【工具结果：工具名】...【/工具结果】` 格式内联替换到原文中。

### 不足

**1. 工具结果内联到文本，而非作为 tool 角色消息回传（核心架构缺陷）**
- 位置：`orchestrator.py:834-839`
- 工具结果被替换进 assistant 的文本输出中，而非作为独立的 `{"role": "tool", "content": result}` 消息。导致 LLM 无法区分"自己说的话"和"工具返回的数据"，无法支持多轮工具调用。

**2. 无多轮工具调用循环（fire-and-forget）**
- 位置：`orchestrator.py:529-530`
- `_process_tool_calls` 执行一次后直接返回修改后的文本，不把结果回传 LLM。真正的 Agent 工具循环应该是：LLM 生成 → 解析工具调用 → 执行 → 结果作为 tool 消息回传 → LLM 基于结果继续生成 → ... 当前实现是：LLM 生成 → 执行工具 → 结束。LLM 永远看不到工具返回了什么。

**3. 未知工具名静默返回空字符串**
- 位置：`orchestrator.py:1030`
- 如果 LLM 调用了不存在的工具，返回空字符串。LLM 不知道工具调用失败了，也不知道原因。

**4. get_memory_summary 绕过了工具的预期功能**
- 位置：`orchestrator.py:938-942`
- 直接返回已注入的 `self.user_memory` 字符串，而非查询 `PersonalizedDB`。项目级记忆（project_id 参数）被忽略。

**5. analyze_weaknesses 每次创建新 DB 实例**
- 位置：`orchestrator.py:970-975`
- 每次工具调用都 `new PersonalizedDB()`，而非复用 `GradioApp` 中已初始化的 `self.pdb`。可能导致状态不一致。

**6. 工具结果无大小限制**
- 位置：`orchestrator.py:834-839`
- 工具结果 `result` 全量注入文本，无截断。如果 `search_exemplars` 返回 10 篇范文全文，可能撑爆上下文窗口。

**7. 工具执行异常被吞掉**
- 位置：`orchestrator.py:1031-1033`
- 异常只记日志，返回空字符串。LLM 收到空结果，不知道是"工具没有数据"还是"工具执行崩溃"。

### 与"真正 Agent"的差距

| 标准 | 当前状态 |
|------|----------|
| tool 角色消息回传 | 否，内联文本替换 |
| 多轮工具调用循环 | 否，fire-and-forget |
| 错误反馈给 LLM | 否，静默返回空 |
| 结果大小限制 | 否，全量注入 |
| 结果 schema 校验 | 否 |

---

## 跨组件系统性问题

### 1. "伪多智能体"——协商结果不真正影响 LLM 决策

`agent_coordinator.py` 的多智能体协商确实调用了 LLM 获取各 Agent 意见，`orchestrator.py:524-525` 也将决策摘要追加到 user_prompt。但由于没有对话历史，LLM 不知道这些协商意见是"谁说的、基于什么上下文说的"。协商结果变成了 user 消息中的一段附加文本，而非多轮对话中的结构化输入。

### 2. 迭代审查不是真正的"迭代"

`reviewer_agent.py:957-1079` 的 `iterate_review()` 实现了"审→改→审→改"循环，但这个循环是纯规则引擎驱动的（`diagnose_errors` + `apply_fixes`），LLM 深度审查是在规则迭代结束后并行执行的。LLM 审查结果只存入 `iteration_results[i]["llm_review"]`，不触发新一轮修复。真正的迭代审查应该是：LLM 审查 → 基于审查结果修复 → LLM 再审查修复后版本 → ...

### 3. 辩论机制是"表演性"的

`agent_coordinator.py:488-594` 的 `run_debate()` 确实调用了 LLM 生成反驳和共识，但共识结果只被记录到日志，不注入后续 LLM 调用。辩论达成的共识对实际写作/审查没有任何影响。

### 4. 缓存策略可能返回错误结果

`orchestrator.py:676-682` 的 LRU 缓存以 `(system_opt, user_opt)` 为 key，如果两次写作任务的 prompt 恰好相同，第二次会直接返回缓存的旧内容，而非重新生成。

---

## 问题汇总表

| 编号 | 组件 | 问题 | 严重程度 | 代码位置 |
|------|------|------|----------|----------|
| 1 | 系统提示词 | EnvState.render() 未被调用，writer_agent 手动重复渲染 | 重要 | `writer_agent.py:193-214` |
| 2 | 系统提示词 | 审查员系统提示词缺失 EnvState 和 user_memory | 重要 | `orchestrator.py:1150-1166` |
| 3 | 系统提示词 | 用户记忆为非结构化纯文本注入 | 轻微 | `writer_agent.py:217-223` |
| 4 | 系统提示词 | EnvState 缺少迭代上下文（轮次/历史问题/版本号） | 重要 | `system_prompt.py:219-233` |
| 5 | 系统提示词 | ContextManager.build_context() 已实现但从未接入 LLM 调用 | 严重 | `token_optimizer.py:288-297` / `orchestrator.py:691-693` |
| 6 | 工具定义 | 未使用原生 function calling，依赖文本标记解析 | 严重 | `tool_definitions.py:7-9` |
| 7 | 工具定义 | 工具参数无 JSON Schema 约束 | 重要 | `tool_definitions.py:22-28` |
| 8 | 工具定义 | parse_tool_call 正则无法处理值中含逗号/括号/引号 | 重要 | `tool_definitions.py:336-348` |
| 9 | 工具定义 | suggest_style_blend 参数名与执行代码不匹配（Bug） | 严重 | `tool_definitions.py:184-196` / `orchestrator.py:922-925` |
| 10 | 工具定义 | 全部工具注入所有角色，无权限过滤 | 重要 | `writer_agent.py:294-297` / `orchestrator.py:1157-1159` |
| 11 | 用户消息 | LLM 调用始终单轮无状态（system+user） | 严重 | `orchestrator.py:691-693` |
| 12 | 用户消息 | 问卷原始 Q&A 上下文被汇总压缩丢失 | 重要 | `gradio_app_v1.py:603-702` |
| 13 | 用户消息 | 无 RAG 动态检索，范文为静态预注入 | 重要 | `writer_agent.py:283-291` |
| 14 | 用户消息 | 协商决策以非结构化方式追加到 user 消息 | 轻微 | `orchestrator.py:524-525` |
| 15 | 模型回复 | 不读取 message.tool_calls，不支持原生工具调用 | 严重 | `orchestrator.py:732` |
| 16 | 模型回复 | reasoning 提取仅支持 DeepSeek 格式 | 轻微 | `orchestrator.py:737` |
| 17 | 模型回复 | assistant 消息不存入对话历史，后续调用无法引用 | 严重 | `orchestrator.py:749` |
| 18 | 模型回复 | 审查结果用正则解析，无 JSON Mode 保障 | 重要 | `orchestrator.py:1199-1285` |
| 19 | 模型回复 | 内容验证仅检查长度>=2 | 重要 | `orchestrator.py:733` |
| 20 | 模型回复 | 格式错误的工具调用标记静默残留 | 重要 | `orchestrator.py:818-820` |
| 21 | 工具结果 | 工具结果内联文本替换，非 tool 角色消息 | 严重 | `orchestrator.py:834-839` |
| 22 | 工具结果 | 无多轮工具调用循环，结果不回传 LLM | 严重 | `orchestrator.py:529-530` |
| 23 | 工具结果 | 未知工具名静默返回空字符串 | 重要 | `orchestrator.py:1030` |
| 24 | 工具结果 | get_memory_summary 绕过 DB 直接返回缓存 | 重要 | `orchestrator.py:938-942` |
| 25 | 工具结果 | analyze_weaknesses 每次创建新 DB 实例 | 重要 | `orchestrator.py:970-975` |
| 26 | 工具结果 | 工具结果无大小限制，可能撑爆上下文 | 重要 | `orchestrator.py:834-839` |
| 27 | 工具结果 | 工具执行异常被吞，LLM 无感知 | 重要 | `orchestrator.py:1031-1033` |
| 28 | 跨组件 | 迭代审查非真正迭代，LLM 审查不触发再修复 | 严重 | `reviewer_agent.py:957-1079` / `orchestrator.py:1092-1098` |
| 29 | 跨组件 | 辩论共识不注入后续 LLM 调用 | 重要 | `orchestrator.py:1321` |
| 30 | 跨组件 | LRU 缓存可能使相同 prompt 返回旧内容 | 重要 | `orchestrator.py:676-682` |

---

## 核心结论

本项目在**工程完整性**上做得相当扎实——7 个文件构成了完整的"问卷→规划→写作→审查→交付"流程，多智能体协商、辩论、迭代审查的代码骨架齐全。但从"五个上下文组件"的标准审视，存在一个**贯穿性的架构缺陷**：

> **LLM 调用始终是单轮无状态的 `system + user` 两段式，工具调用用文本正则解析，工具结果内联到文本，无法形成"LLM 决策→工具执行→结果回传→LLM 再决策"的闭环。**

这导致三个"伪 Agent"特征：
1. **伪工具调用**：LLM 把工具调用请求"写"在文本里，代码用正则解析执行，结果不回传 LLM
2. **伪多轮对话**：ContextManager 已实现但未接入，每次 LLM 调用都是失忆的
3. **伪迭代审查**：规则引擎迭代修复后，LLM 审查结果只记录不反馈，不触发新一轮修复

---

## 最优先修复的 5 个问题

按影响面排序：

1. **将 `_call_llm` 改为多轮消息列表**（接入 `ContextManager.build_context()`）— 问题 11/5
2. **迁移到原生 function calling**（`tools=` 参数）— 问题 6/15/21
3. **工具结果作为 `tool` 角色消息回传，建立工具调用循环** — 问题 22/21
4. **修复 `suggest_style_blend` 参数名不匹配 Bug** — 问题 9
5. **审查结果改用 JSON Mode 强制结构化输出** — 问题 18

其中 1-3 是架构级改动（工作量大），4-5 是具体修复（工作量小）。

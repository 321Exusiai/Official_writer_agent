# 公文写作智能体 · 工作流标准完整跨组件检查报告

> 审查日期：2026-08-04（完整版，覆盖全部 14 个组件）
> 审查基准：**工作流标准**（非 Agent 标准）——本项目是"问卷→规划→写作→审查→交付"的确定性工作流，LLM 在固定节点被调用，工具由代码按固定流程执行。
> 审查方法：逐一读取每个组件的源码，用三问框架（**环境信息获取方式 / 信息注入完整性 / 定义与调用一致性**）逐组件核对，并对关键疑点用全局 Grep 验证调用关系。

---

## 〇、组件清单与核查总览

| 组件 | 对应文件 | 三问核查结论 |
|------|----------|-------------|
| C1 系统提示词 | `src/config/system_prompt.py` | EnvState 定义完整但 render() 零调用；无迭代维度 |
| C2 工具定义 | `src/config/tool_definitions.py` | 17 工具 schema 齐全；1 处参数名与执行端不一致；3 个查询函数死代码 |
| C3 用户消息/问卷 | `src/questionnaire/questionnaire.py` | 决策树+5 模式问卷完整；保留字段在问卷路径不填充 |
| C4 模型回复处理 | `src/core/orchestrator.py`（_call_llm/_process_tool_calls） | 单轮调用；工具结果内联进稿件而非回传模型；ContextManager 断线 |
| C5 工具执行结果 | `src/core/orchestrator.py`（_execute_tool_call） | 3 个工具返回"假数据/假状态"；1 个工具是桩实现 |
| C6 写作组件 | `src/core/writer_agent.py` | EnvState 手动拼装；风格注入方法全部死代码 |
| C7 审查组件 | `src/core/reviewer_agent.py` + orchestrator._run_llm_deep_review | 审查员无 EnvState/记忆；YOUTH_ENGAGEMENT 错误库缺失；LLM 审查轮次错位 |
| C8 多智能体协商 | `src/core/agent_coordinator.py` | 自行拼装环境信息；无 EnvState/用户记忆；ContextManager 死 |
| C9 规划组件 | `src/core/document_type.py` + style_adapter.py + orchestrator.generate_plan | DOC_TYPE_PROFILES 仅 5 配置但 UI 提供 10 文种 → write() 直接索引崩溃 |
| C10 知识库 | `src/knowledge/knowledge_base.py` | 内容完整；2 个方法仅测试使用 |
| C11 个性化数据库 | `src/core/personalized_db.py` | 记忆非结构化；orchestrator 工具每次新建实例读不到数据 |
| C12 Token 优化 | `src/utils/token_optimizer.py` | ContextManager 死代码；2 个函数仅导出未消费 |
| C13 一文多体 | `src/core/multi_doc_generator.py` | 一致性检查良好；行政模式无文种组合处理；直接索引 DOC_TYPE_PROFILES |
| C14 前端接入 | `gradio_app_v1.py` | 文种下拉含 5 个无配置文种 → 触发 C9 崩溃；记忆注入正常 |

**统计**：原有 11 项（严重 5 / 中等 6）+ 本次新增 8 项（严重 3 / 中等 4 / 低 1）= **共 19 项（严重 8 / 中等 10 / 低 1）**。

---

## 一、组件一专项审查（系统提示词）

### 问题 1.1 EnvState 标准调用缺失（严重）

**现状确认**：`system_prompt.py:235` 定义了 `EnvState.render()`，但全局搜索 `.render()` 仅命中定义处，**零调用**。[writer_agent.py:193-214](file:///c:\Users\王为韬\OneDrive\桌面\项目\python\official_writer_agent\src\core\writer_agent.py#L193-L214) 手动逐字段拼装，且直接调用私有方法 `env_state._intensity_label()`（L205），违反封装。

**问题表现**：
- 手动拼装的字段集合（模式/子类型/阶段/风格强度/extra）与 `render()`（10 字段全量）逻辑分叉
- 手动拼装漏掉 `extra` 字典之外的所有下游字段，且 `render()` 的"空状态兜底文案"从未生效

**修复方向**：`EnvState.render()` 增加 `include_fields/exclude_fields` 参数，writer_agent 改为 `env_state.render(exclude_fields=[...])`。

---

### 问题 1.2 审查员提示词未注入 EnvState 和用户记忆（严重）

**现状确认**：[orchestrator.py:1150-1166](file:///c:\Users\王为韬\OneDrive\桌面\项目\python\official_writer_agent\src\core\orchestrator.py#L1150-L1166) 审查员 system prompt = `get_core_prompt()` + 审查指令 + 工具定义，**无 EnvState、无 user_memory**。

**问题表现**：
- 审查员拿不到实际 mode/subtype/style 值，只能靠指令文本猜测审查标准
- 审查员不知道用户历史常见错误，无法针对性检查

**修复方向**：审查员 prompt 复用 EnvState（至少 mode/subtype/stage）与 user_memory。

---

### 问题 1.3 记忆注入为非结构化纯文本（中等）

**现状确认**：`personalized_db.py:622` 的 `get_memory_summary()` 返回拼接字符串；`writer_agent.py:217-223` 直接拼进 prompt。

**问题表现**：LLM 无法区分记忆类型（偏好/历史错误/禁用词/项目记忆），无法按场景选择性注入（审查只要"常见错误"，写作要"偏好+禁用词"）。

---

### 问题 1.4 EnvState 缺少工作流迭代维度（中等）

**现状确认**：`system_prompt.py:219-233`，EnvState 无 `iteration_count`、`draft_version`、`previous_issues` 字段；`stage` 在 write() 中写死为"写作阶段…"，审查/交付阶段不更新。

**问题表现**：多轮审查时 LLM 无法感知"这是第几轮""上一轮发现了什么"，审查员可能重复报告同一问题。

---

### 问题 1.5 ContextManager 已实现但完全断线（严重）

**现状确认**：
- `orchestrator.py:126`：`self._context_manager = ContextManager()` 实例化后**再无任何使用**
- `agent_coordinator.py:317/754/761`：独立实例，仅 `add_message()` 记录协商历史，`build_context()` **全局零调用**（仅 `token_optimizer.py:288` 定义处）
- `agent_coordinator.py:1063`：只读 `_context_mgr._total_messages` 做统计

**修复方向**：方案 A（推荐）删除 ContextManager 及两处实例；方案 B 让 `_call_llm` 接入，但单轮工作流接入反而污染。

---

## 二、本次新增的系统性跨组件问题（N1-N8）

### 问题 N1 DOC_TYPE_PROFILES 直接索引崩溃 —— 行政文种必崩（严重）

**现状确认**：
- [document_type.py:53-294](file:///c:\Users\王为韬\OneDrive\桌面\项目\python\official_writer_agent\src\core\document_type.py#L53-L294)：`DOC_TYPE_PROFILES` 只配置了 5 个文种（消息/通讯/侧记/调研报告/简报），请示/通知/批复/函/纪要等 11 个行政文种**没有 profile**
- `get_profile()`（L412-449）为此做了动态兜底，但 [orchestrator.py:428](file:///c:\Users\王为韬\OneDrive\桌面\项目\python\official_writer_agent\src\core\orchestrator.py#L428) 和 L444 在 `write()` 中**直接索引** `DOC_TYPE_PROFILES[self.plan.document_type]`，绕过了兜底
- [gradio_app_v1.py:48-60](file:///c:\Users\王为韬\OneDrive\桌面\项目\python\official_writer_agent\gradio_app_v1.py#L48-L60) 文种下拉框提供 10 个选项，**包含 5 个无配置文种**
- `multi_doc_generator.py:189` `_get_doc_profile()` 同样直接索引

**问题表现**：用户在方案调整页选择"请示/通知/批复/函/会议纪要"→ `generate_plan()` 成功（走 get_profile 兜底）→ `write()` L428 抛 **KeyError** → 整个写作流程进入 ERROR 状态。行政模式写作实际不可用。

**连带问题**：
- `identify()`（document_type.py:335-410）只对 5 个有 profile 的文种打分 → 行政模式走自动识别时会推荐 通讯/简报 等错误文种
- `_recommend_doc_types()`（multi_doc_generator.py:167-180）对 ADMINISTRATIVE 无分支 → 行政模式"一文多体"生成 通讯/消息/简报，文种完全错位
- `system_prompt.py:92-100` 提示词中"五种文种"表与 `DOC_TYPE_PROFILES` 一致，但与 UI 10 选项、DECISION_TREE 15 种法定公文矛盾

**修复方向**：为 11 个行政文种补齐 `DocTypeProfile`（或在 `get_profile()` 兜底之上让 `write()` 改走 `get_profile()`）；`identify()` 按模式过滤候选文种；`_recommend_doc_types()` 增加 ADMINISTRATIVE 分支。

---

### 问题 N2 suggest_style_blend 工具参数名与执行端不一致（严重）

**现状确认**（实测仍存在，此前 mock 测试未覆盖到执行端读取处）：
- [tool_definitions.py:184-196](file:///c:\Users\王为韬\OneDrive\桌面\项目\python\official_writer_agent\src\config\tool_definitions.py#L184-L196) 声明参数：`primary_style` / `secondary_style` / `intensity`
- [orchestrator.py:922-935](file:///c:\Users\王为韬\OneDrive\桌面\项目\python\official_writer_agent\src\core\orchestrator.py#L922-L935) 执行端读取：`primary_audience` / `purpose` / `secondary_audiences`
- 且 `suggest_blend(primary, purpose, secondary or None)` 把 `purpose` 传给了第 2 参数 `purpose`（正确），但 `primary` 语义是"受众"而非"风格"——`_score_style` 按受众关键词打分，LLM 按定义传入的 `primary_style=人民日报` 会被当成受众描述去匹配，结果完全错乱

**问题表现**：LLM 按工具定义传 `primary_style/secondary_style/intensity` → 执行端全部取到空串 → `suggest_blend("", "", None)` 返回"单一受众场景，全篇使用新华社风格"这类误导结果。

**修复方向**：统一参数名（推荐工具定义改为 `primary_audience/purpose/secondary_audiences` 并更新示例，或执行端改读 `primary_style` 并把风格名映射回 MediaStyle）。

---

### 问题 N3 工具调用"闭环"断裂：结果内联进稿件而非回传模型（严重）

**现状确认**：
- `_call_llm()`（orchestrator.py:639-773）是**单轮** system+user 调用，无第二轮
- `write()` L529-530：`self.draft = self._process_tool_calls(self.draft)` —— 把草稿中的 `[TOOL_CALL:...]` 标记直接替换为 `【工具结果：工具名】结果【/工具结果】`（L832-839），**结果嵌入最终稿件文本**
- 全局无任何下游清理这些标签的代码（已 Grep 验证）

**问题表现**：
1. **LLM 永远看不到工具结果**——工具结果没有作为 assistant/tool 消息回传给模型，模型无法基于结果修订内容，所谓"工具闭环"实际是断的
2. **污染稿件**——若 Writer 输出中插入了工具调用，最终 `draft` 会包含 `【工具结果：lookup_term】…【/工具结果】` 原始知识文本，直接进入交付内容
3. `_process_tool_calls` 对同一工具只替换第一处（`count=1`），多次调用同一工具时残留标记

**修复方向**：改为"检测到工具调用 → 执行 → 结果作为新一条 assistant/tool 消息追加 → 再次调用 LLM 整合"；或降级为"调用后把结果注入下次请求的 system"；至少应在最终交付前剥离 `【工具结果：…】` 块。

---

### 问题 N4 LLM 深度审查轮次与稿件版本错位（中等）

**现状确认**：[orchestrator.py:1130-1178](file:///c:\Users\王为韬\OneDrive\桌面\项目\python\official_writer_agent\src\core\orchestrator.py#L1130-L1178) `review_single_round` 闭包中 `if not prompt or not self.draft` 用**全局** `self.draft`（迭代结束后的最终稿）做判空，而 `ir["review_prompt"]` 是 `iterate_review` 里基于**各轮修复后快照**构建的。

**问题表现**：若第 1 轮修复后 `self.draft` 非空则没问题；但"待审稿件"实际是各轮快照，与全局 `self.draft` 无关——当 `self.draft` 为空（write 后未设）时，**所有轮次 LLM 审查全部跳过**，静默失败。逻辑耦合脆弱。

**修复方向**：用 `ir.get("draft_snapshot")` 或显式传递的稿件文本做判空与提示，不依赖实例字段。

---

### 问题 N5 YOUTH_ENGAGEMENT 模式缺少专属错误诊断库（中等）

**现状确认**：
- `REVIEW_DIMENSIONS`（writing_mode.py:477-483）有青年共情 5 维审查；`MODE_QUESTIONS` 也有 5 题
- 但 [reviewer_agent.py:416-421](file:///c:\Users\王为韬\OneDrive\桌面\项目\python\official_writer_agent\src\core\reviewer_agent.py#L416-L421) `ALL_ERROR_DBS` 只配了 4 个模式，**YOUTH_ENGAGEMENT 回退到 STRATEGIC_NARRATIVE 错误库**

**问题表现**：青年推文会被规则引擎按"被动叙事/空泛表态/战略锚点"标准诊断，与推文文体不匹配（如"安排了/组织了"在推文中是正常语态）。`forbidden_patterns` 中"宝宝们/绝绝子"等青年模式专属禁令不会触发。

**修复方向**：新增 `YOUTH_ERROR_DB`（空泛口号、官腔、爹味称呼、AI 套话、无思想落点等），注册进 `ALL_ERROR_DBS`。

---

### 问题 N6 风格注入方法全部为死代码：强度/混合风格在生产中从未生效（中等）

**现状确认**（已 Grep 验证）：
- [style_adapter.py:722-849](file:///c:\Users\王为韬\OneDrive\桌面\项目\python\official_writer_agent\src\core\style_adapter.py#L722-L849) `get_system_prompt_injection` / `_build_single_prompt` / `_build_blend_prompt` / `_scale_language_features` / `_scale_forbidden` / `get_system_prompt_injection_with_intensity` **仅被 tests/test_all.py 调用**
- [writer_agent.py:260-273](file:///c:\Users\王为韬\OneDrive\桌面\项目\python\official_writer_agent\src\core\writer_agent.py#L260-L273) 手动拼装风格段落（仅 narrative_perspective/emotional_tone/示例），**没有**强度缩放、**没有**混合风格逻辑

**问题表现**：
- 工具定义与系统提示词宣称"支持风格混合和强度调节（0.0-1.0）"，但 `style_intensity` 只在 EnvState 里被转成"标准强度/适度风格"文字标签（writer_agent.py:205），词汇池缩放、禁用词缩放、混合方案 `_build_blend_prompt` 全部未生效
- `get_system_prompt_injection` 的混合风格能力（gradio 中 `suggest_blend` 计算结果 `blend`）没有任何一处被消费

**修复方向**：writer_agent 风格段落改调 `style_adapter.get_system_prompt_injection(profile, blend)`，或删除死方法避免误导。

---

### 问题 N7 死代码扩展清单（中等）

| 代码 | 位置 | 调用情况 |
|------|------|---------|
| `get_tool_call_format()` | `tool_definitions.py:314` | 生产零调用 |
| `get_tools_by_phase()` / `get_tools_by_category()` | `tool_definitions.py:361/366` | 生产零调用 |
| `optimize_system_prompt()` | `token_optimizer.py:511` | 仅被 `utils/__init__.py` 导出 |
| `build_implicit_review_prompt()` | `token_optimizer.py:515` | 仅被导出，无调用方 |
| `get_formatted_prompt_for_mode()` | `knowledge_base.py:1785` | 生产零调用 |
| `get_style_exemplar_summary()` | `knowledge_base.py:1717` | 仅测试调用 |
| `get_round_prompt()` / `get_all_round_prompts()` / `get_round_count()` | `reviewer_agent.py:608/623/627` | 仅测试调用 |
| `run_full_review()` / `run_parallel_review()` | `reviewer_agent.py:838/1081` | 生产零调用（生产走 iterate_review） |
| `generate_outline()` | `writer_agent.py:353` | 仅测试调用 |
| `get_llm_prompts()` | `orchestrator.py:1534` | 仅测试调用 |
| `navigate_tree()` | `writing_mode.py:649` | 仅测试调用（生产走 submit_routing_choice） |
| `ContextManager.build_context()` | `token_optimizer.py:288` | 全局零调用 |
| `StyleAdapter` 风格注入 6 方法 | `style_adapter.py:722-849` | 仅测试调用（见 N6） |

**影响**：约 20 处"定义/导出但未消费"的接口，增加维护成本并制造"这些能力已生效"的假象。

---

### 问题 N8 import_from_text 工具是桩实现（中等）

**现状确认**：[orchestrator.py:1022-1028](file:///c:\Users\王为韬\OneDrive\桌面\项目\python\official_writer_agent\src\core\orchestrator.py#L1022-L1028) `import_from_text` 只返回"已接收素材"确认文本，**不存储**；工具定义（tool_definitions.py:248-260）却声明"自动识别格式和提取风格特征"。`URLDocumentImporter.import_from_text()`（url_importer.py:360）有完整实现但未被工具执行端调用。

**问题表现**：LLM 调用后无任何副作用，风格特征提取能力（已有实现）白白闲置；且与 import_from_url 行为不对称。

**修复方向**：工具执行端调 `URLDocumentImporter.import_from_text()` 并（如定义了 project_id）写入 PersonalizedDB。

---

## 三、跨组件系统性检查（原有问题复核）

### 问题 2.1 环境信息自行拼装（未走标准 EnvState）——复核仍成立

| 位置 | 自行拼装的内容 | 应使用的标准 |
|------|---------------|-------------|
| `writer_agent.py:193-214` | EnvState 字段手动拼装 | `env_state.render()` |
| `orchestrator.py:1150-1166` | 审查员 prompt 无任何环境信息 | 注入 EnvState |
| `reviewer_agent.py:472-494` | 用模式名+tagline 当环境信息 | 注入 EnvState |
| `agent_coordinator.py:716-725` | 自己拼 writing_mode/plan/brief | 注入 EnvState |

### 问题 2.2 信息注入不完整 → "假数据"/"假状态"——复核仍成立

- **（a）审查员信息缺失**（严重）：缺 EnvState + user_memory（同 1.2）
- **（b）协商 agent 信息缺失**（严重）：`agent_coordinator.py:716-725` 无 EnvState、无 user_memory、无规则引擎已发现问题
- **（c）get_memory_summary 返回假数据**（中等）：`orchestrator.py:938-942` 直接返回 `self.user_memory` 缓存，忽略 `project_id` 参数，绕过 PersonalizedDB
- **（d）analyze_weaknesses / get_style_recommendation 新实例假状态**（中等）：`orchestrator.py:948-975` 每次调用 `PersonalizedDB()`，与 GradioApp 持久化的 `self.pdb` 不是同一实例，`get_project()` 永远返回 None → 读不到任何项目数据

### 问题 2.3 死代码清单——合并入 N7

---

## 四、问题汇总表（19 项）

| 编号 | 组件 | 问题 | 严重程度 | 位置 |
|------|------|------|----------|------|
| 1.1 | C1 系统提示词 | EnvState.render() 零调用，手动拼装字段分叉 | 严重 | `writer_agent.py:193-214` |
| 1.2 | C1/C7 | 审查员 prompt 无 EnvState、无 user_memory | 严重 | `orchestrator.py:1150-1166` |
| 1.3 | C1/C11 | 记忆注入为非结构化纯文本 | 中等 | `personalized_db.py:622` |
| 1.4 | C1 | EnvState 缺迭代维度（轮次/版本/上轮问题） | 中等 | `system_prompt.py:219-233` |
| 1.5 | C12 | ContextManager 实例化但 build_context 零调用 | 严重 | `orchestrator.py:126` / `agent_coordinator.py:317` |
| 2.1 | 跨组件 | 4 处自行拼装环境信息 | 严重 | 见三、2.1 表 |
| 2.2a | C7 | 审查员信息缺失 | 严重 | `orchestrator.py:1150-1166` |
| 2.2b | C8 | 协商 agent 信息缺失 | 严重 | `agent_coordinator.py:716-725` |
| 2.2c | C5 | get_memory_summary 返回假数据（绕过 DB） | 中等 | `orchestrator.py:938-942` |
| 2.2d | C5/C11 | analyze_weaknesses 新实例读不到持久化数据 | 中等 | `orchestrator.py:970-975` |
| 2.3 | 跨组件 | 死代码（合并 N7） | 中等 | 见 N7 |
| **N1** | C9/C13/C14 | DOC_TYPE_PROFILES 直接索引 → 行政文种写作崩溃 | **严重** | `orchestrator.py:428/444` |
| **N2** | C2/C5 | suggest_style_blend 参数名不一致 + 语义错位 | **严重** | `tool_definitions.py:184` vs `orchestrator.py:922` |
| **N3** | C4/C5 | 工具结果内联进稿件，不回传模型（闭环断裂） | **严重** | `orchestrator.py:829-839` |
| **N4** | C7 | LLM 深度审查判空依赖全局 self.draft，轮次错位 | 中等 | `orchestrator.py:1133` |
| **N5** | C7 | YOUTH_ENGAGEMENT 缺专属错误诊断库 | 中等 | `reviewer_agent.py:416-421` |
| **N6** | C6/C9 | 风格注入 6 方法死代码，强度/混合风格未生效 | 中等 | `style_adapter.py:722-849` |
| **N7** | 跨组件 | 约 20 处定义未消费的接口/函数 | 中等 | 见 N7 表 |
| **N8** | C2/C5 | import_from_text 桩实现，未存储未提取特征 | 中等 | `orchestrator.py:1022-1028` |
| **N10** | C3 | WritingBrief 保留字段（length_hint 等）问卷路径不填充 | 低 | `questionnaire.py:79-82` |

---

## 五、核心结论

以工作流标准逐组件核查后，问题可归为五类：

1. **会直接崩的功能缺陷（新增，最高优先）**：N1 行政文种 `write()` KeyError、N2 工具参数错位 —— 这两项使"行政行为模式 + 选择公文文种"、"风格混合工具"两个宣称能力实际不可用。
2. **标准方法被绕过**：EnvState.render()（1.1）、StyleAdapter 风格注入（N6）写好了不用 → 逻辑分叉、能力落空。
3. **链路未打通**：EnvState/用户记忆只在"写"节点接通，"审/协商"节点缺失（1.2/2.1/2.2a/2.2b）；工具结果不回传模型（N3）。
4. **为 Agent 设计的组件残留**：ContextManager 分层记忆对单轮工作流无意义（1.5/N7）。
5. **定义与实现漂移**：工具参数名（N2）、文种清单（N1）、模式错误库（N5）、风格能力宣称（N6）四处"文档/定义/实现"三方不一致。

### 建议修复优先级

| 优先级 | 问题 | 工作量 |
|--------|------|--------|
| P0 | N1 文种崩溃（补 11 个 DocTypeProfile 或统一走 get_profile）+ 文种推荐按模式过滤 | 中 |
| P0 | 1.2 审查员注入 EnvState + user_memory | 小 |
| P0 | 1.1 EnvState.render() 支持字段过滤并接入 | 小 |
| P1 | N2 suggest_style_blend 参数对齐 | 小 |
| P1 | N3 工具闭环修复（结果回传模型 / 至少剥离工具结果标签） | 中 |
| P1 | 1.5+N7 删除 ContextManager 及死代码 | 小 |
| P1 | 2.1 协商 agent 注入 EnvState | 中 |
| P2 | 2.2c/2.2d 工具注入真实 pdb 实例 | 小 |
| P2 | N5 补齐 YOUTH_ENGAGEMENT 错误库 | 小 |
| P2 | N6 风格注入接入 writer_agent | 中 |
| P2 | N8 import_from_text 接真实实现 | 小 |
| P3 | 1.3 记忆结构化 / 1.4 迭代维度 / N10 保留字段 | 低 |

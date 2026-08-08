# 多智能体系统性问题修复设计（2026-08-08）

> 核验结论：4 个问题全部属实（1 个措辞修正）。用户选择"全部修复"，问题 1 走真多轮协商。

## 问题与修复总览

| # | 问题 | 结论 | 修复方案 |
|---|------|------|----------|
| 1 | 伪多智能体：协商扁平文本注入、无角色归属、决策为模板匹配 | 部分属实（意见文本确实进入 prompt，但非结构化、无归属、无多轮） | 真多轮协商 + LLM 决策 + 角色归属注入 |
| 2 | 迭代审查由纯规则引擎驱动，LLM 审查结果不触发修复 | 属实 | LLM 真迭代闭环：审→改→审 |
| 3 | 辩论共识只记日志，不影响稿件 | 属实 | 共识修订稿件闭环 |
| 4 | 缓存以 (system,user) 为 key，同 prompt 返回旧内容；temperature 不在 key 中 | 属实 | key 加 temperature/model；主稿生成绕过缓存 |
| 5 | LLM 可见性：协商/决策/辩论看不到系统全景；§5.6 命名不一致（用户新增要求） | 属实 | 系统全景注入 + 职责矩阵 + 命名修正 |

## 一、真多轮协商（agent_coordinator.py + orchestrator.py）

### consult_before_decision 增加 max_rounds（默认 2）
- Round 1：并行收集各方意见（保持现状）。
- Round r（≥2）：把上一轮各方意见带角色标签汇总为"协商进展"（每角色限 2 关注 + 2 建议），并行发给各 Agent 要求回应/确认/修正，产出本轮意见。
- 返回结构不变：`Dict[AgentRole, Dict[str, Any]]`。

### make_decision 增加 llm_call（可选）
- 聚合保留角色归属：`decision["role_opinions"] = {role.value: {"concerns": [...], "suggestions": [...]}}`。
- 若传 llm_call：LLM 基于"议题 + 角色意见"生成最终决策与理由（system = 系统全景 + Orchestrator 职责）。
- LLM 不可用/失败：回退现有模板 `_orchestrator_decision`。

### _build_decision_context 重写（orchestrator.py）
- 按角色分组输出：「【Writer 意见】…」，附最终决策与理由。
- 每角色限 2 关注 + 2 建议，控制 token。

### write() 接线
- `consult_before_decision(..., max_rounds=2)`。
- `make_decision(..., llm_call=self._call_llm)`。

## 二、LLM 真迭代审查（orchestrator.py）

### 新 helper
- `_build_llm_review_prompt(draft, env_state, version, prev_findings)`：从现有 `_run_llm_deep_review` 提取审查 prompt 构建逻辑（含核心提示词 + 工具清单 + 记忆）。
- `_llm_revise_draft(draft, instruction)`：主笔角色 system prompt（含系统全景），user = 当前稿 + 指令，输出完整修订稿。

### _run_llm_iterative_review(draft, max_llm_rounds=3)
每轮：
1. LLM 审查当前稿 → 解析 findings。
2. 无 critical/major findings 或达轮次上限 → 停（早停：实际通常只消耗 1 轮）。
3. 否则 `_llm_revise_draft(draft, findings)` → 修订 == 原稿 → 停（防死循环）。
4. 记录 `draft_snapshot / llm_review / llm_revision`。

### 接线
- `review()` / `re_review()`：规则 `iterate_review` 先跑（保底），随后 `_run_llm_iterative_review` 替换原 `_run_llm_deep_review`。原 `_run_llm_deep_review` 删除。

## 三、辩论共识闭环（orchestrator.py）

- `_check_and_run_debate` 返回 `(triggered, consensus_text)`。
- 共识非空 → `_llm_revise_draft(draft, "辩论共识…请按共识修改稿件")` → 写回 `self.draft` → 记入 agent_log 与 review_summary_display。

## 四、缓存修正（orchestrator.py + agent_coordinator.py）

- `_call_llm`：`use_cache: bool = True` 参数；缓存 key = `make_cache_key(system_opt, user_opt, temperature, config.model)`；仅 `use_cache` 时查/写缓存。
- `_call_llm_with_tool_loop`：透传 `use_cache`。
- `write()` 主稿调用传 `use_cache=False`（每次生成全新输出）。
- agent_coordinator 协商缓存：`hash()` → `make_cache_key`（md5），key 加轮次号。

## 五、LLM 可见性保障（用户新增要求）

### 系统全景注入（agent_coordinator.py）
- `AGENT_RESPONSIBILITY_MATRIX`：AgentRole 枚举 → 中文职责一句话。
- `build_agent_orientation()`：工作流摘要（状态机 4 行）+ 各 Agent 职责矩阵 + 工具职责清单（name + description，来自 tool_definitions 的 ToolDef 列表）。
- `_llm_agent_response` system prompt = 系统全景 + 自身角色详细职责（现有 role_profiles）+ 隐式推理 + JSON 输出要求。
- 决策 LLM 调用 system = 系统全景 + Orchestrator 职责。
- `_llm_rebuttal` / `_llm_consensus` system prompt 增加双方角色说明。

### 命名修正（system_prompt.py）
- §5.6 增加枚举名 ↔ 展示名映射：Writer/Reviewer/StyleAdapter(展示名 StyleAdvisor)/KnowledgeBase(KnowledgeKeeper)/DocTypeIdentifier(DocTypeAnalyst)/PersonalizedDB(UserProxy)。

## 验证

1. `python run_tests.py`（现有测试通过）。
2. 端到端冒烟：skip_questionnaire → generate_plan → write → review（LLM 可用时）。
3. 无 LLM 时降级路径不受影响（模板回退保留）。

# 公文写作工作室（writer_studio）— 设计规格说明

> 版本：1.0 · 日期：2026-08-15 · 状态：待审阅
> 定位：工作流驱动的公文写作辅助工具（workflow-first，不是"智能体"包装）。

---

## 1. 目标与定位

从零重构一个公文写作辅助工具，核心原则：**统一化、高效化、人性化、真实化**。

- 是**工作流编排工具**：路由 → 问卷 → 规划 → 协作协商 → 写作 → 审查 → 一文多体 → 交付，用户全程可见、可介入。
- **保留原版审美与领域精华，重构工程实现**；不拼凑、不写屎山。

## 2. 扬弃清单

### 2.1 保留（原版的精华，需迁移）

| 类别 | 具体内容 |
|---|---|
| 审美 | 三套壁纸主题（见 §10.1）、iOS 毛玻璃卡片、金色 glow 按钮、缓动曲线、五步进度徽章、Agent 气泡流、审查热力图、`prefers-reduced-motion` 降级 |
| 领域知识 | 5 写作模式、16 文种、5 媒体风格、决策树路由、模式专属问卷（`why_ask`/`hint` 教学）、6 知识容器、5 模式审查维度 |
| 设计理念 | "一党执政·民主协商"多智能体协作、审→改→审迭代、双 HITL、一文多体（长版→提取短版）、Token 经济学 |
| 工程细节 | 原子写入持久化（tmp + `os.replace`）、LRU 缓存、LLM 优雅降级、URL scheme 白名单 |

### 2.2 舍弃（原版的糟粕，坚决重构）

1. **God Object**：`orchestrator.py` 735 行单类、`gradio_app_v1.py` 4069 行单文件。
2. **假装多智能体**：`if "风格" in topic` 关键词兜底、辩论双方固定模板立场、规则兜底伪装协商。
3. **两套评分公式并存**、死代码、注释声称但未实现的能力（六大 Token 策略用一半、ModelRouter 不路由、PDF 导入未实现等）。
4. **词汇库键名不一致**（人民日报有 four_char、央视有 scene_words、光明有 philosophical）。
5. **文种识别断裂**：媒体轨/行政轨两套互斥函数硬编码。
6. **线性 UI**：选择用户冗余、下拉式项目选择、两步确认弹窗。
7. **工程缺陷**：API Key 明文、anthropic 模板不兼容、404 分类不一致、`date_with_zero` 正则永不命中。

---

## 3. 技术栈

| 层 | 选型 |
|---|---|
| 后端 | Python 3.11 + **FastAPI** + **Pydantic v2**（唯一数据真相）+ `httpx`（LLM 调用）+ uvicorn |
| 前端 | **Vue 3 + Vite + Pinia**，原生 CSS（design tokens），手写 iOS 组件层，无重型 UI 库 |
| 持久化 | 本地 JSON，原子写；知识数据为只读 JSON + 统一 loader |
| 通信 | REST JSON（CRUD）+ **SSE**（工作流过程流式推送） |

项目落点：当前仓库内新建 `writer_studio/` 子目录，与旧代码并存。

## 4. 总体架构

```
writer_studio/
├── backend/
│   ├── main.py                  # FastAPI 入口 + 静态托管前端 build 产物
│   ├── api/                     # 路由层（薄：绑定参数→调 core→返回响应）
│   │   ├── projects.py  workflow.py  knowledge.py  config.py  events.py
│   ├── core/                    # 领域逻辑（纯 Python，无 Web 依赖，可独立测试）
│   │   ├── engine.py            # 工作流引擎（显式状态机 + 步骤注册表 + 事件发射）
│   │   ├── agents.py            # 角色协作（AgentSpec + 真实 LLM + 诚实降级）
│   │   ├── review.py            # 审查流水线（单一评分公式）
│   │   ├── style.py             # 风格适配（分轨道统型化 + 强度缩放）
│   │   ├── doctype.py           # 文种识别（分轨道统型化）
│   │   ├── multi_doc.py         # 一文多体（长版→提取短版）
│   │   ├── brief.py             # 问卷与 WritingBrief
│   │   └── llm.py               # LLM 客户端（重试/降级/缓存/工具闭环）
│   ├── domain/
│   │   ├── schemas.py           # 全部 Pydantic 模型（唯一数据真相）
│   │   ├── registry.py          # 统一注册表（核心，见 §5.1）
│   │   └── events.py            # 工作流事件模型（SSE 载荷）
│   ├── knowledge/
│   │   ├── data/*.json          # 统一 Schema 的知识数据
│   │   └── loader.py            # 统一加载 + 完整性校验
│   └── storage/                 # 本地 JSON 持久化（原子写）
└── frontend/
    ├── src/
    │   ├── styles/tokens.css    # 设计 token（唯一样式真相，含三主题）
    │   ├── api/client.js        # 统一 REST 客户端（类型化封装）
    │   ├── api/events.js        # SSE 客户端（重连 + 事件分发）
    │   ├── stores/              # Pinia（project/workflow/knowledge/theme）
    │   ├── components/ui/       # 手写 iOS 基础组件
    │   ├── components/project/  # 文件夹式项目浏览器
    │   ├── components/workflow/ # 工作流步骤面板 + 决策过程可视化
    │   └── components/knowledge/# 资料库（搜索/过滤/详情）
    └── index.html / vite.config.js
```

**设计约束**：每个源文件保持可单次上下文理解（目标 < 400 行）；`core/` 与 `api/`、`storage/` 分层，无反向依赖；领域逻辑不 import FastAPI。

---

## 5. 统一化设计（统型化 + 领域区分）

> 核心：**结构形式统一（统型化），内容按领域区分**。统一是为了维护/阅读/修改，不是为了抹平领域差异。

### 5.1 统一注册表（Registry）

所有可枚举静态知识走同一条加载链，统一查询接口：

```python
Registry.load("modes")       # 5 写作模式
Registry.load("styles")      # 5 媒体风格（含 domain 区分）
Registry.load("doctypes")    # 16 文种（含 domain 区分）
Registry.load("exemplars")   # 范文
Registry.load("terms")       # 术语
Registry.load("errors")      # 错误模式
Registry.load("transitions") # 过渡句
Registry.load("formulaic")   # 格式化用语
```

- 每个容器 JSON 统一顶层结构 `{"id": {...}}`；
- 每条由**统一 Pydantic 模型**约束（`schemas.py`）；
- 统一查询接口：`by_id` / `filter(domain=...)` / `match(text, weights=...)`；
- **加载时完整性校验**：字段缺失或违反约束直接报错启动失败，杜绝"空转"。

### 5.2 词汇池统一（不允许缺失）

所有风格词汇池统一为**固定五类键**，且**每类必须有内容（schema 强制 ≥ 5 条，缺失即校验失败）**：

```json
{
  "vocabulary_pool": {
    "verbs": ["...至少5条"],
    "nouns": ["...至少5条"],
    "adjectives": ["...至少5条"],
    "phrases": ["...至少5条"],
    "transitions": ["...至少5条"]
  }
}
```

- 数据源：迁移原 `style_adapter.py` 五份 `STYLE_PROFILES` 词汇，**统一键名并补齐缺类**；
- 风格强度缩放作用于五类**统一逐类截取**（≥0.8 取全、≥0.5 取 3、否则取 1 条/类），消除原版各风格缩放逻辑分叉。

### 5.3 领域区分（媒体 vs 行政、官方 vs 舆论）

- **文种 `domain`**：`media`（消息/通讯/侧记/调研报告/简报）与 `official`（请示/通知/批复/函/纪要/通报/公告/决定/报告/意见/议案）；
- **风格 `domain`**：`official`（党政机关行文）与 `media`（人民日报/新华社/央视/光明）；
- **同框架、分轨道权重**：文种识别共用四维度打分框架（关键词/受众/篇幅/素材），但**权重矩阵按 `domain` 配置**（官方文种重"格式/行文方向"关键词、媒体文种重"新闻价值/叙事"关键词），不再是两套互斥硬编码函数；
- **风格-文种匹配约束**：`official` 文种默认只匹配 `official` 风格，`media` 文种默认 `media` 风格；用户可覆盖，覆盖时前端**预警**（保留原版 `_detect_style_conflict` 的正确意图，但做成显式约束而非散落判断）。

---

## 6. 真实多智能体（不再假装）

### 6.1 声明式角色（AgentSpec）

每个角色是声明式定义，输入/输出为结构化 JSON Schema：

```python
AgentSpec(
    id="reviewer", name="审稿人",
    system_prompt=...,                      # 由 core prompt + 角色职责拼装
    input_schema=...,
    output_schema={"concerns": [...], "suggestions": [...]},
    rule_backend=review_rule_backend,        # 降级用，基于真实上下文计算
)
```

7 个角色：`orchestrator / writer / reviewer / style / doctype / knowledge / profile`。

### 6.2 协作机制（真实 LLM + 诚实降级）

| 机制 | 真实路径 | 降级路径（诚实标注） |
|---|---|---|
| 协商 | 并行调用各角色 LLM，输出严格 JSON `{concerns,suggestions}`，多轮互相回应 | `rule_backend` 基于真实上下文（素材字数/风格冲突/文种匹配）计算，**UI 标注「规则模式」** |
| 辩论 | 双方立场来自**真实审查发现**，LLM 多轮反驳→共识 JSON | 加权规则汇总（有依据，非写死文案） |
| 决策 | Orchestrator LLM 基于各方真实意见裁决 | 加权规则汇总 |

- 绝对禁止 `if "风格" in topic` 式关键词伪装协商；
- 降级永远**显式标注**给用户，不冒充 LLM 结果；
- 协商/辩论结果**带角色标签注入写作 prompt**，共识**落实到稿件修订**。

## 7. 审查机制（单一评分公式）

单一 `review()` 流水线，统一 `ReviewFinding`/`ReviewResult`：

```
规则诊断（正则+统计，真实可命中）→ LLM 逐轮审查（审→改→审，早停）
→ 分歧触发辩论（critical≥1 或 major≥2）→ 共识落实到稿件 → HITL 面板
```

**唯一评分公式**（全系统共用，消除两套并存）：

```
score = clamp(100 − Σ severity_weight, 0, 100)
critical=25, major=15, minor=5, suggestion=2
passed = (无 critical) 且 (score ≥ 70)
```

修复原版缺陷：`date_with_zero` 等正则**用真实正则引擎**（不再子串匹配）；修复 `_remove_pattern` 只删第一处的问题——规则修复走**结构化替换**，语义级修复交给 LLM 重写。

## 8. 风格与文种设计

- **StyleProfile**（统一字段）：`id/name/domain/description/typical_length_range/narrative_perspective/emotional_tone/data_density/literary_level/policy_linkage/vocabulary_pool(五类非空)/forbidden_patterns/example_opening/example_closing`；
- **DocTypeProfile**（统一字段）：`id/name_cn/domain/description/typical_length_range/structure_mode/benchmark_media/opening_template/body_template/closing_template/keywords(分轨道权重)`；
- **识别**：四维度加权（`WEIGHT_MATRIX[domain]`），返回全量排序；
- **风格混合**：主风格打分 + 次要受众（×0.6 衰减）→ `primary_weight = primary/(primary+secondary)`；修复原版 `best_secondary == primary` 死分支（主风格不参与次要打分）；
- **强度**：统一 `_intensity_note` 5 档 + 五类词汇统一截取。

## 9. 知识库

6 容器统一 Schema（数据与代码分离），统一 loader + 完整性校验：

| 容器 | 统一模型 | 完整性约束 |
|---|---|---|
| exemplars | `Exemplar`（id/title/source/mode/doc_type/style/structure_skeleton/key_phrases/reusable_pattern/language_tags） | 每 mode 至少 2 篇 |
| formulaic | `Formulaic`（doc_type/opening/transition/closing） | 覆盖全部 official 文种 |
| format_errors | `FormatError`（id/check_method/pattern/severity/fix） | **每条必须有真实可执行的 check_method**（不再 11/17 空转） |
| error_patterns | `ErrorPattern`（id/mode/patterns/severity/prescription） | patterns 为正则语义，逐条可命中 |
| terminology | `Term`（term/definition/context/usage_note/common_misuse） | — |
| transitions | `Transition`（style/phrases） | 覆盖 5 风格，每风格 ≥5 条 |

## 10. UI 设计

### 10.1 设计 token + 三壁纸迁移 + 颜色创新

- **三壁纸主题全部迁移**，通过 CSS 变量切换（`data-theme`），非硬编码三份全量 CSS：
  - **星月夜**（暗色，默认）：SVG SMIL 动画背景 + 梵高色板（`#0D162B/#1C3765/#4F7EA4` + 月光金 `#DFCB5C`）；
  - **经典流光**（暗色）：CSS 双径向流体渐变 + `blur(100px)` + `mix-blend-mode: color-dodge` 旋转动画；
  - **苹果极简**（浅色）：Apple HIG，`--color-accent:#0A84FF`，背景 `#F5F5F7`，白色卡片，禁用 backdrop-filter、克制动效；
- **颜色创新**：在三主题基础上新增可选的**配色方案**（如"墨青""暖杏"）作为 accent 变体，`tokens.css` 统一管理；
- 统一 token：`--color-* / --radius-* / --blur-* / --ease-* / --font-*`，iOS 毛玻璃（`backdrop-filter`）、金色 glow 按钮、五步进度徽章、Agent 气泡流、审查热力图全部保留；`prefers-reduced-motion` 降级。

### 10.2 布局（人性化）

- **去掉「选择用户」**：单用户本地工具，启动即进项目页；
- **文件夹式项目浏览器**：项目以文件夹/卡片网格呈现，点击进入、悬浮/右键查看详情、内联新建/重命名/删除（无下拉 + 两步确认弹窗）；含搜索与最近打开；
- 三栏：左侧项目/资料库导航 → 中间工作区（当前步骤）→ 右侧过程面板（见 §10.3）；
- 资料库：卡片式搜索/过滤/详情抽屉，非原版表格+弹窗。

### 10.3 决策过程可视化（真实化）

右侧「过程面板」通过 **SSE 实时流**展示完整工作流，每步可展开：

```
路由 → 问卷 → 规划 → 协商(各角色气泡) → 写作 → 审查(发现清单+热力图) → 一文多体(多版本对比) → 交付
```

- 协商/辩论/决策的每个角色发言**实时可见**，降级时标注「规则模式」；
- HITL 节点（方案确认、审查介入）在此面板直接操作；
- 一文多体：版本对比视图（并排/差异高亮）。

## 11. 通信协议

- **REST JSON**：`/api/projects`（CRUD）、`/api/projects/{id}/workflow`（启动/推进/回答）、`/api/knowledge`（查询）、`/api/config`（LLM 配置）、`/api/styles|doctypes|modes`（元数据）；
- **SSE**：`/api/projects/{id}/events`，事件模型 `{seq, type, step, payload, ts}`，类型覆盖 `routing/question/plan/consult/write/review/debate/multidoc/finalize/hitl`；
- Pydantic v2 自动校验 + 自动 OpenAPI；前端 `client.js` 统一封装 + Pinia 单状态源；
- LLM 工具调用改用**结构化 JSON 工具调用**（OpenAI 兼容 `tools` 参数 + 原生 `tool_calls` 回传），降级时退回文本 `[TOOL_CALL]` 协议。

## 12. 数据模型（Pydantic，唯一真相）

`Brief / Plan / EnvState / Project / ReferenceArticle / ReviewFinding / ReviewResult / DocVersion / WorkflowEvent / AgentResponse / LLMConfig` 等全部在 `domain/schemas.py` 定义；前后端共享字段命名（前端 TypeScript 类型可由 OpenAPI 生成或手写对齐）。

## 13. 错误处理与降级

- LLM：重试（401/403/404/429/5xx 分类）+ 超时 + 空响应 → 统一降级为**明确标注的规则结果**（`_generate_fallback` 保留但只在无 Key 时触发，不冒充内容）；
- API Key：存本地 JSON，**前端显示时脱敏，落盘可选 base64 混淆 + 明确提示非安全存储**；
- 工作流异常：引擎捕获后发 `error` 事件，前端展示可恢复的失败步骤，不静默吞掉。

## 14. 测试策略

- 后端 `pytest`：`core/` 领域逻辑单测（模式路由、文种识别、风格混合、评分公式、Registry 完整性校验、LLM 降级路径）；
- 前端：关键 store 与组件逻辑单测（Vitest），组件冒烟；
- 集成：一条无 Key 全链路（路由→…→交付）降级可跑通 + 一条 mock LLM 全链路。

## 15. 实现阶段（纵向切片优先）

| 阶段 | 交付 |
|---|---|
| P0 骨架 | FastAPI + 前端脚手架 + Registry + 三壁纸 tokens + 文件夹式项目浏览器 + 持久化 |
| P1 工作流主链 | 问卷→规划→写作→审查→一文多体→交付（无 Key 规则版全链路跑通）+ SSE 过程面板 |
| P2 真实协作 | AgentSpec + 真实 LLM 协商/辩论/决策 + 诚实降级 + 工具闭环 |
| P3 知识库完整化 | 6 容器数据补齐 + 统一 loader 校验 + 资料库 UI |
| P4 打磨 | 审查热力图/版本对比/HITL 完整化 + 无障碍 + 测试补齐 |

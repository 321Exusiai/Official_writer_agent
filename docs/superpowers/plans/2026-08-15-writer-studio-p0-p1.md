# 公文写作工作流工具（writer_studio）实现计划 — P0 骨架 + P1 主链

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `writer_studio/` 内交付第一个可运行纵向切片：FastAPI + Vue3 前后端，含统一注册表、三壁纸 iOS UI、文件夹式项目浏览器、无 Key 规则版全链路（路由→问卷→规划→写作→审查→一文多体→交付）与 SSE 决策过程可视化。

**Architecture:** 后端 `core/`（纯领域逻辑，无 Web 依赖）↔ `api/`（薄路由）↔ `domain/schemas.py`（Pydantic 唯一真相）↔ `storage/`（原子写 JSON）；前端 Pinia 单状态源 + 手写 iOS 组件层，经 REST JSON 与 SSE 与后端通信。P2（真实 LLM 协作）P3（知识库完整化）P4（打磨）另行成 plan。

**Tech Stack:** Python 3.11 / FastAPI / Pydantic v2 / httpx / uvicorn / pytest；Vue 3 + Vite + Pinia + 原生 CSS。

## Global Constraints

- 落点：`writer_studio/` 子目录（与旧代码并存，互不引用）。
- 每个源文件 < 400 行；`core/` 不得 import FastAPI。
- 词汇池五类键 `verbs/nouns/adjectives/phrases/transitions`，每类 ≥5 条，Registry 加载时校验缺失即抛错。
- 唯一评分公式：`score = clamp(100 − Σ w, 0, 100)`，`critical=25, major=15, minor=5, suggestion=2`，`passed = (无 critical) 且 (score ≥ 70)`。
- 三壁纸经 `data-theme` 属性 + CSS 变量切换；`prefers-reduced-motion` 降级。
- LLM 未配置时降级为规则结果，且返回体必须含 `mode: "rule"` 标记（前端据此标注「规则模式」）。
- 文种/风格含 `domain` 字段（`media`/`official`）；打分框架统一、权重矩阵按 domain 分轨道。

---

### Task 1: 后端脚手架与领域模型骨架

**Files:**
- Create: `writer_studio/backend/requirements.txt`
- Create: `writer_studio/backend/domain/__init__.py`
- Create: `writer_studio/backend/domain/schemas.py`

**Interfaces:**
- Produces: `Brief`, `Plan`, `EnvState`, `Project`, `ProjectStatus(str,Enum)`, `ReviewFinding`, `ReviewResult`, `ReviewSeverity(str,Enum)`, `DocVersion`, `WorkflowEvent`, `AgentResponse`, `LLMConfig` — 后续所有 task 依赖的 Pydantic 模型。

- [ ] **Step 1: 写 requirements 与 schemas.py 的 Pydantic 模型**

```python
# writer_studio/backend/domain/schemas.py
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ProjectStatus(str, Enum):
    DRAFT = "draft"; IN_PROGRESS = "in_progress"; COMPLETED = "completed"; ARCHIVED = "archived"

class Brief(BaseModel):
    writing_mode: str = ""
    subtype: str = ""
    purpose: str = ""
    primary_audience: str = ""
    secondary_audiences: List[str] = Field(default_factory=list)
    deep_meaning: str = ""
    strategic_anchor: str = ""
    opportunity_context: str = ""
    key_materials: str = ""
    differentiator: str = ""
    length_hint: Optional[int] = None
    style_intensity: float = 1.0
    raw_answers: Dict[str, str] = Field(default_factory=dict)

class Plan(BaseModel):
    doc_type: str = ""
    media_style: str = ""
    audience_focus: str = "external"
    estimated_length: str = ""
    structure_outline: str = ""
    writing_mode: str = ""

class EnvState(BaseModel):
    writing_mode: str = ""; mode_value: str = ""; subtype: str = ""
    stage: str = ""; doc_type: str = ""; media_style: str = ""
    style_intensity: float = 1.0; purpose: str = ""; primary_audience: str = ""
    length_hint: Optional[int] = None; iteration_count: int = 0
    draft_version: int = 0; previous_issues: str = ""

class ReviewSeverity(str, Enum):
    CRITICAL = "critical"; MAJOR = "major"; MINOR = "minor"; SUGGESTION = "suggestion"

class ReviewFinding(BaseModel):
    round_name: str = ""; severity: ReviewSeverity = ReviewSeverity.MINOR
    location: str = ""; issue: str = ""; suggestion: str = ""
    error_key: str = ""; source: str = "rule"  # rule | llm

class ReviewResult(BaseModel):
    round_name: str = ""; passed: bool = True; score: float = 100.0
    findings: List[ReviewFinding] = Field(default_factory=list); draft_version: int = 0

class DocVersion(BaseModel):
    doc_type: str = ""; doc_type_name: str = ""; content: str = ""
    word_count: int = 0; generation_order: int = 0; extracted_from: str = ""

class Project(BaseModel):
    id: str = ""; name: str = ""; description: str = ""
    status: ProjectStatus = ProjectStatus.DRAFT
    brief: Optional[Brief] = None; plan: Optional[Plan] = None
    draft: str = ""; final_draft: str = ""
    versions: List[DocVersion] = Field(default_factory=list)
    review_results: List[ReviewResult] = Field(default_factory=list)
    created_at: str = ""; updated_at: str = ""

class WorkflowEvent(BaseModel):
    seq: int = 0; type: str = ""; step: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict); ts: float = 0.0

class AgentResponse(BaseModel):
    role: str = ""; concerns: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list); mode: str = "rule"  # llm | rule

class LLMConfig(BaseModel):
    provider: str = "openai"; api_base: str = ""; api_key: str = ""
    model: str = ""; temperature: float = 0.7; max_tokens: int = 8000; enabled: bool = False
```

- [ ] **Step 2: 写测试验证模型可实例化与默认值**

`writer_studio/backend/tests/test_schemas.py`：断言 `Brief()` 默认字段、`ReviewResult(passed=False, score=50)`、`AgentResponse(mode="rule")` 可构造且类型正确。

- [ ] **Step 3: 运行 pytest 通过并 commit**

```bash
cd writer_studio/backend && pip install -r requirements.txt && pytest -q
git add writer_studio && git commit -m "feat(writer_studio): 后端脚手架 + Pydantic 领域模型"
```

---

### Task 2: 统一注册表 Registry 与知识加载器

**Files:**
- Create: `writer_studio/backend/domain/registry.py`
- Create: `writer_studio/backend/knowledge/loader.py`
- Create: `writer_studio/backend/knowledge/data/modes.json`
- Create: `writer_studio/backend/knowledge/data/styles.json`
- Create: `writer_studio/backend/knowledge/data/doctypes.json`

**Interfaces:**
- Produces: `Registry.load(name) -> dict[str, dict]`, `Registry.by_id(name, id)`, `Registry.filter(name, domain=None)`；`loader.load_container(name)` 校验后返回 dict。词汇池校验规则：五类键存在且每类 list 长度 ≥5。

- [ ] **Step 1: 写 registry 与 loader（统一加载 + 完整性校验）**

```python
# writer_studio/backend/domain/registry.py
import json
from pathlib import Path
from . import schemas  # noqa

_DATA_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "data"

class Registry:
    _cache: dict = {}

    @classmethod
    def load(cls, name: str) -> dict:
        if name in cls._cache:
            return cls._cache[name]
        data = json.loads((_DATA_DIR / f"{name}.json").read_text(encoding="utf-8"))
        cls._validate(name, data)
        cls._cache[name] = data
        return data

    @classmethod
    def by_id(cls, name: str, id_: str):
        return cls.load(name).get(id_)

    @classmethod
    def filter(cls, name: str, domain: str = None):
        items = cls.load(name).values()
        return [i for i in items if domain is None or i.get("domain") == domain]

    @classmethod
    def _validate(cls, name, data):
        if name == "styles":
            for sid, s in data.items():
                pool = s.get("vocabulary_pool", {})
                for key in ("verbs", "nouns", "adjectives", "phrases", "transitions"):
                    assert len(pool.get(key, [])) >= 5, f"styles.{sid}.vocabulary_pool.{key} 不足5条"
```

- [ ] **Step 2: 写 styles.json（5 风格，词汇池五类均 ≥5 条，含 domain）**

每风格结构（示例，人民日报）：`{"people_daily": {"id":"people_daily","name":"人民日报","domain":"media","narrative_perspective":"第三人称","emotional_tone":"庄重有温度","data_density":"中","literary_level":"中高","policy_linkage":"高","vocabulary_pool":{"verbs":[...≥5],"nouns":[...],"adjectives":[...],"phrases":[...],"transitions":[...]},"forbidden_patterns":[...],"example_opening":"...","example_closing":"..."}}`。五风格：people_daily/xinhua/cctv/guangming（domain=media）+ government_admin（domain=official）。词汇从原 `src/core/style_adapter.py` 迁移并补齐。

- [ ] **Step 3: 写 doctypes.json（16 文种，含 domain 与 keywords 权重）与 modes.json（5 模式）**

doctypes 结构：`{"feature": {"id":"feature","name_cn":"通讯","domain":"media","typical_length_range":[1500,3000],"structure_mode":"总-分-总","keywords":[["研学",0.18],...],"opening_template":"...","body_template":"...","closing_template":"..."}}`。16 个文种：media 5（news_brief/feature/sidelight/research_report/bulletin）+ official 11（circular/request/notification/reply/letter/meeting_minutes/announcement/decision/report/opinion/motion）。

modes 结构：`{"strategic_narrative": {"id":"strategic_narrative","name":"战略叙事","tagline":"...","principles":[{"name":"...","check":"..."}],"review_dimensions":[{"name":"...","weight":0.25}],"questions":[{"id":"sn_vision","text":"...","why_ask":"...","hint":"..."}]}}`。5 模式：strategic_narrative/objective_report/administrative/informational/youth_engagement（原则与问题从原 `src/core/writing_mode.py` 迁移）。

- [ ] **Step 4: 写测试断言完整性（styles 词汇池 ≥5、doctypes=16、modes=5、media/official domain 分布）**

- [ ] **Step 5: 运行 pytest 通过并 commit**

---

### Task 3: 文种识别与风格适配（分轨道统型化）

**Files:**
- Create: `writer_studio/backend/core/doctype.py`
- Create: `writer_studio/backend/core/style.py`
- Test: `writer_studio/backend/tests/test_doctype_style.py`

**Interfaces:**
- Produces: `identify_doc_type(brief: Brief) -> list[tuple[str, float]]`（返回 16 文种全量排序）；`select_style(brief, doc_type) -> str`；`suggest_blend(primary_audience, purpose, secondary_audiences) -> dict`；`score_doc(text, patterns) -> float`。

- [ ] **Step 1: 实现 doctype.py（四维度打分 + WEIGHT_MATRIX 分轨道）**

```python
# writer_studio/backend/core/doctype.py
from ..domain.registry import Registry
from ..domain.schemas import Brief

WEIGHT_MATRIX = {
    "media":   {"keyword": 0.40, "audience": 0.25, "length": 0.25, "material": 0.10},
    "official":{"keyword": 0.45, "audience": 0.30, "length": 0.15, "material": 0.10},
}

def identify_doc_type(brief: Brief) -> list[tuple[str, float]]:
    target_domain = "official" if brief.writing_mode == "administrative" else "media"
    w = WEIGHT_MATRIX[target_domain]
    doctypes = Registry.filter("doctypes", domain=target_domain)
    scores = []
    for dt in doctypes:
        s = 0.0
        s += w["keyword"] * _keyword_hits(dt.get("keywords", []), brief.purpose)
        s += w["audience"] * _audience_match(dt.get("audience_kw", []), brief.primary_audience)
        if brief.length_hint:
            lo, hi = dt["typical_length_range"]
            s += w["length"] * (1.0 - abs(brief.length_hint - (lo + hi) / 2) / (hi - lo))
        s += w["material"] * _material_match(dt, brief.key_materials)
        scores.append((dt["id"], round(min(1.0, max(0.0, s)), 4)))
    scores.sort(key=lambda x: -x[1])
    if not scores or scores[0][1] <= 0:
        fallback = "notification" if target_domain == "official" else "feature"
        scores = [(fallback, 0.5)] + [x for x in scores if x[0] != fallback]
    return scores
```

- [ ] **Step 2: 实现 style.py（auto_select + suggest_blend + 强度缩放 + 风格-文种约束）**

```python
# writer_studio/backend/core/style.py
from ..domain.registry import Registry
from ..domain.schemas import Brief

def auto_select_style(brief: Brief, doc_type_id: str) -> str:
    dt = Registry.by_id("doctypes", doc_type_id)
    domain = dt["domain"] if dt else "media"
    cands = Registry.filter("styles", domain="official" if domain == "official" else "media")
    return cands[0]["id"] if cands else "people_daily"

def suggest_blend(primary_audience, purpose, secondary_audiences):
    # 主风格打分 + 次要受众(×0.6衰减)，primary_weight = p/(p+s)
    # 返回 {"primary_style","primary_weight","secondary_style","secondary_weight","apply_to","reasoning"}
    ...
```

- [ ] **Step 3: 写测试（识别行政 mode 返回 official 文种、媒体返回 media 文种、混合权重 0.7/0.3 边界、风格-文种 domain 匹配）**

- [ ] **Step 4: pytest 通过并 commit**

---

### Task 4: 审查流水线（单一评分公式 + 真实规则诊断）

**Files:**
- Create: `writer_studio/backend/core/review.py`
- Create: `writer_studio/backend/knowledge/data/errors.json`
- Test: `writer_studio/backend/tests/test_review.py`

**Interfaces:**
- Produces: `review(text, mode) -> list[ReviewResult]`；`score(findings: list[ReviewFinding]) -> float`；`is_passed(results) -> bool`。

- [ ] **Step 1: 实现统一评分函数**

```python
# writer_studio/backend/core/review.py
from ..domain.schemas import ReviewFinding, ReviewResult, ReviewSeverity

SEVERITY_WEIGHT = {"critical": 25, "major": 15, "minor": 5, "suggestion": 2}

def score(findings):
    return max(0.0, min(100.0, 100.0 - sum(SEVERITY_WEIGHT[f.severity.value] for f in findings)))

def is_passed(results):
    return all(not any(f.severity == ReviewSeverity.CRITICAL for f in r.findings)
               and r.score >= 70 for r in results)
```

- [ ] **Step 2: 实现规则诊断（真实正则命中，修复 date_with_zero）**

`diagnose(text, mode)` 从 `Registry.load("errors")` 取当前 mode 的错误模式，用 `re.search` 真实匹配（每条含 `pattern` 与 `severity` 与 `prescription`）；`errors.json` 每条 pattern 为正则语义（含 `date_with_zero = r"\d{4}年0\d月"` 等），逐条可命中。

- [ ] **Step 3: 写测试（评分公式精确值：2 critical = 50 分；date_with_zero 正则真实命中 "2025年07月"；passed 阈值 70）**

- [ ] **Step 4: pytest 通过并 commit**

---

### Task 5: 工作流引擎（显式状态机 + 事件发射）

**Files:**
- Create: `writer_studio/backend/core/engine.py`
- Create: `writer_studio/backend/core/brief.py`
- Create: `writer_studio/backend/core/multi_doc.py`
- Test: `writer_studio/backend/tests/test_engine.py`

**Interfaces:**
- Produces: `WorkflowEngine`（`start(project_id)`, `answer(text)`, `confirm_plan()`, `write()`, `review()`, `finalize()`, `events: list[WorkflowEvent]`, `state`）；`brief.py` 的 `route(answers) -> mode`, `mode_questions(mode) -> list[dict]`；`multi_doc.py` 的 `generate_multi_doc(draft, brief) -> list[DocVersion]`。

- [ ] **Step 1: 实现 brief.py（决策树路由 + 模式问卷，数据来自 Registry modes）**

`route` 用两级决策树（root 4 选项 → 分支）；`mode_questions` 返回该模式 `questions` 列表。决策树常量内联在 `brief.py`（< 80 行）。

- [ ] **Step 2: 实现 multi_doc.py（长版→提取短版，规则版）**

规则版：按 `doctypes` 的 `typical_length_range` 生成长版（主文种全文）+ 短版（导语截取 + 结构套用），返回 `list[DocVersion]`；LLM 版留待 P2。

- [ ] **Step 3: 实现 engine.py（状态机 + 事件流 + 无 Key 规则版全链路）**

状态：`IDLE→ROUTING→QUESTIONING→PLANNING→WAITING_APPROVAL→WRITING→REVIEWING→COMPLETED/ERROR`。每步推进时 `emit(type, step, payload)` 追加 `WorkflowEvent`（seq 自增）。`write()`/`review()` 在无 LLM 时走规则版（`mode="rule"`），产出占位初稿 + 规则审查结果，全程可跑通。

- [ ] **Step 4: 写测试（全链路无 Key 跑通：start→answer×N→confirm→write→review→finalize，断言状态 COMPLETED、events 覆盖全部 step 类型、review 评分公式正确）**

- [ ] **Step 5: pytest 通过并 commit**

---

### Task 6: 存储层与 FastAPI 路由 + SSE

**Files:**
- Create: `writer_studio/backend/storage/store.py`
- Create: `writer_studio/backend/api/projects.py`
- Create: `writer_studio/backend/api/workflow.py`
- Create: `writer_studio/backend/api/events.py`
- Create: `writer_studio/backend/main.py`

**Interfaces:**
- Produces: `Store`（`create_project(name, desc) -> Project`, `get_project(id)`, `list_projects()`, `update_project(id, patch)`, `delete_project(id)`，原子写 `writer_studio/backend/data/projects.json`）；FastAPI 路由：`GET/POST /api/projects`、`GET/PATCH/DELETE /api/projects/{id}`、`POST /api/projects/{id}/workflow/{action}`、`GET /api/projects/{id}/events`（SSE）。

- [ ] **Step 1: 实现 store.py（原子写 tmp + os.replace）**

- [ ] **Step 2: 实现 main.py + 三个路由（薄路由，Pydantic 自动校验）**

`main.py` 用 `FastAPI(title="公文写作工作室")`，`app.mount("/assets", ...)` 托管前端 build；`api/events.py` 用 `StreamingResponse(text/event-stream)` 从 engine 的 `events` 队列推送。

- [ ] **Step 3: 写测试（projects CRUD、workflow 全链路 HTTP 级、SSE 返回 event-stream）**

- [ ] **Step 4: pytest 通过并 commit**

---

### Task 7: 前端脚手架 + 三壁纸 tokens + 文件夹式项目浏览器

**Files:**
- Create: `writer_studio/frontend/package.json`, `vite.config.js`, `index.html`
- Create: `writer_studio/frontend/src/main.js`, `App.vue`
- Create: `writer_studio/frontend/src/styles/tokens.css`
- Create: `writer_studio/frontend/src/stores/project.js`, `theme.js`
- Create: `writer_studio/frontend/src/api/client.js`
- Create: `writer_studio/frontend/src/components/project/ProjectBrowser.vue`
- Create: `writer_studio/frontend/src/components/ui/GlassCard.vue`, `Button.vue`

**Interfaces:**
- Consumes: `GET/POST/DELETE /api/projects`；`GET /api/styles|doctypes|modes`。
- Produces: `client.js` 的 `api.get/post/patch/del`；Pinia `useProjectStore`（`projects`, `active`, `fetchProjects`, `createProject`, `removeProject`）；`tokens.css` 的 `:root[data-theme=...]` 三主题变量。

- [ ] **Step 1: 写 tokens.css（三壁纸主题 + 统一 token + 星月夜 SVG 背景 + reduced-motion）**

`:root`（默认星月夜暗色）：`--color-sky-deep:#0D162B; --color-accent:#DFCB5C; --blur-glass:blur(28px) saturate(130%); --radius-card:22px; --radius-button:14px; --ease-out-expo:cubic-bezier(0.23,1,0.32,1);`；`:root[data-theme="classic"]` 流体渐变背景 + `@keyframes fluid-rotate`；`:root[data-theme="apple"]` 浅色 `--color-accent:#0A84FF; --color-ink:#1D1D1F; background:#F5F5F7`；`@media (prefers-reduced-motion: reduce)` 关闭动画。

- [ ] **Step 2: 写 ui 基础组件（GlassCard / Button，含 glow 与毛玻璃）**

- [ ] **Step 3: 写 ProjectBrowser.vue（文件夹式卡片网格：点击进入/悬浮详情/内联新建重命名删除，无下拉无两步弹窗）**

- [ ] **Step 4: 写 client.js + store + App.vue 骨架（三栏布局 + 主题切换）**

- [ ] **Step 5: `npm run dev` 手动冒烟（新建项目→卡片出现→点击进入→主题切换三壁纸生效）并 commit**

---

### Task 8: 前端工作流面板 + SSE 决策过程可视化 + 主链 UI

**Files:**
- Create: `writer_studio/frontend/src/api/events.js`
- Create: `writer_studio/frontend/src/stores/workflow.js`
- Create: `writer_studio/frontend/src/components/workflow/WorkflowPanel.vue`
- Create: `writer_studio/frontend/src/components/workflow/QuestionStep.vue`, `PlanStep.vue`, `WriteStep.vue`, `ReviewStep.vue`, `MultiDocStep.vue`, `FinalizeStep.vue`
- Create: `writer_studio/frontend/src/components/workflow/ProcessPanel.vue`

**Interfaces:**
- Consumes: `POST /api/projects/{id}/workflow/{action}`、`GET /api/projects/{id}/events`（SSE）。
- Produces: `events.js` 的 `subscribeProject(projectId, onEvent)`（EventSource + 重连）；`useWorkflowStore`（`state`, `events`, `answer`, `confirm`, `write`, `review`, `finalize`）。

- [ ] **Step 1: 写 events.js（SSE 客户端：EventSource + 断线重连 + 事件分发）**

- [ ] **Step 2: 写 workflow store（驱动六步 + 维护 events 列表）**

- [ ] **Step 3: 写六个步骤组件（问卷→方案→写作→审查→一文多体→交付，各渲染当前步骤；审查步展示 findings 清单 + 热力图占位；一文多体步展示版本对比）**

- [ ] **Step 4: 写 ProcessPanel.vue（右侧过程面板：按 events 渲染步骤时间线，可展开每个 step 细节；协商/审查气泡；「规则模式」徽标）**

- [ ] **Step 5: 集成到 App.vue（中间工作区 = 当前步骤组件，右侧 = ProcessPanel）**

- [ ] **Step 6: 手动冒烟（无 Key 全链路：路由→问卷→确认→写作→审查→一文多体→交付，过程面板实时显示）并 commit**

---

### Task 9: 集成验证与收尾

**Files:**
- Modify: `writer_studio/backend/tests/test_engine.py`（补 HTTP 级集成）
- Create: `writer_studio/README.md`（启动方式）

- [ ] **Step 1: 写集成测试（无 Key 全链路 HTTP 级：创建项目→workflow 全 action→finalize，断言 200 与 COMPLETED 与 events 序列完整）**

- [ ] **Step 2: 写 README（后端 `uvicorn backend.main:app`；前端 `npm run dev`/`npm run build`；LLM 配置说明与「规则模式」说明）**

- [ ] **Step 3: 全量 pytest + 前端 build 冒烟，commit 并标注 P0+P1 切片完成**

---

## 后续计划（P2–P4，本 plan 不展开）

- **P2 真实协作**：`AgentSpec` + `agents.py`（真实 LLM 协商/辩论/决策 + 诚实降级）+ `llm.py`（httpx 重试/缓存/工具闭环）+ 工具 JSON 调用。
- **P3 知识库完整化**：补齐 exemplars/formulaic/format_errors/terminology/transitions 五容器数据 + 资料库 UI（搜索/过滤/详情抽屉）。
- **P4 打磨**：审查热力图/版本对比 diff/HITL 完整化 + 无障碍 + 前端单测 + `prefers-reduced-motion` 全量覆盖。

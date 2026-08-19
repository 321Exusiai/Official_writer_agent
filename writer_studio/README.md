# 🏛️ 公文写作工作室 (Official Writer Studio)

> **工业级、双轨智能体驱动的专业党政机关公文与宣传文书智能写作工作台**
> 严格遵循《党政机关公文处理工作条例》（中办发〔2012〕14号）与 **GB/T 9704-2012**《党政机关公文格式》国家标准。

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue-3.5+-4FC08D.svg)](https://vuejs.org/)
[![Vite](https://img.shields.io/badge/Vite-5.4+-646CFF.svg)](https://vitejs.dev/)
[![Tests](https://img.shields.io/badge/Tests-140%2F140%20Passing-brightgreen.svg)]()
[![Code Style](https://img.shields.io/badge/Code%20Style-Black%20%7C%20Ruff-000000.svg)]()

---

## 🌟 核心设计理念

本项目贯彻 **「真干活，不演戏」** 与 **「统一化 / 高效化 / 人性化 / 真实化」** 四项基本原则：
- **拒绝假模型/假按钮**：多角色协商、审稿辩论、分段递进起草、红蓝军压力测试、自愈改写均走真实主模型与规则引擎，无 Key 诚实标注「规则模式」。
- **双轨制智能体分工**：
  - **主写作智能体（Core Multi-Agent Writing Engine）**：承载问卷剖析 ➔ 6大专家特化协商 ➔ 权威加权集中仲裁 ➔ 大纲分段起草 ➔ 智能审查与多轮自愈 ➔ 领导审签与舆情红蓝军测试。
  - **辅助智能体（Assistant Copilot）**：轻量 ReAct 工具循环（GLM-4-Flash / 规则），负责全局搜索、历史项目 BM25 检索、单位专有知识库沉淀、公文国标速查、写作灵感置顶备忘录。
- **国家公文规范与马克思主义新闻观**：融合宣传“四力”（脚力、眼力、脑力、笔力）与法定 15 种文种铁律，坚决剔除“假大空套话”与“AI 腔调”。

---

## 🚀 系统全景架构

```mermaid
graph TD
    subgraph 辅助轨道 [辅助智能体 Copilot (ReAct Agent)]
        A1["对话问答 & 快捷指令 (/搜索 /项目 /术语)"] --> A2["ReAct 6轮工具循环 (多工具并发)"]
        A2 --> T1["BM25 历史项目检索 (search_project_history)"]
        A2 --> T2["单位专有知识库 CRUD (search/add_custom_knowledge)"]
        A2 --> T3["领导审签与舆情排查 (get_red_team_report)"]
        A2 --> T4["国标公文规范速查 (inspect_document_standard)"]
        A2 --> T5["作者备忘录置顶 (pin_to_scratchpad)"]
    end

    subgraph 主写作轨道 [主写作与自愈闭环 (Core Writing Workflow)]
        W1["1. 需求交互剖析 (Brief & Questionnaire)"] --> W2["2. 动态专家特化协商 (6-Role MoA)"]
        W2 --> W3["3. 权威加权集中决策 (Decide + Veto)"]
        W3 --> W4["4. 大纲驱动分段递进起草 (Chunked Generator)"]
        W4 --> W5["5. 逐维度智能审查与辩论 (Review & Debate)"]
        W5 --> W6["6. 重要级驱动自愈循环 (Auto-Healing 85分+)"]
        W6 --> W7["7. 分管领导审签与红蓝军测试 (Red-Team Adversarial)"]
        W7 --> W8["8. GB/T 9704-2012 Word 导出 & 一文多体交付"]
    end
```

---

## 💎 四大核心支柱功能

### 1. 💾 数据库与现代存储架构
- **单项目独立文件拆分**：项目详情独立落盘至 `data/projects/{pid}.json`，轻量级索引落盘至 `data/project_index.json`，配备 `_WRITE_LOCK` 线程锁与原子写入。
- **时光机版本快照（Time Machine）**：草稿编辑 800ms 防抖自动暂存，每次变动自动记录 `Revision` 历史快照（最多保留 30 版），支持一键无损回滚。
- **历史项目 BM25 全文检索**：支持跨所有历史项目草稿、作者备忘录与简报诉求进行模糊与精准语义检索。
- **单位专有知识库与自定义模板**：支持上传与沉淀单位红头规范、领导讲话金句与排版模板。
- **GB/T 9704-2012 Word 导出引擎**：支持直接导出 A4 版心、小标宋标题、3号仿宋正文、固定28磅行距、2字符缩进的规范 `.docx` 文档。

### 2. 🧠 智能体系统与决策算法
- **动态专家路由与特化注水（Dynamic MoA）**：根据文种与写作模式智能选派 3~4 个专家（主笔、文种、风格、知识、审稿、画像），各自注入专属背景片段，告别“千人一面”。
- **大纲分段递进起草（Chunked Generator）**：规划三段式大纲后，按前文衔接锚点逐段生成并全局缝合，彻底突破长文本逻辑衰减。
- **领导审签与舆情红蓝军测试（Red-Team Adversarial）**：模拟严苛分管领导挑刺（查主体责任、资金与时间节点）与舆情风控排查（查绝对化表述与次生舆情）。
- **专家决策权威权重微调**：支持用户交互式拖动滑块调节各专家权威权重（0.5x ~ 3.0x），影响集中仲裁结论。

### 3. 🤝 人性化与人机协同（HITL Workflow）
- **划词局部 AI 伴写浮条（Inline Copilot）**：选中文本即时呼出 `[✨ 金句升华]`、`[✂️ 精简去套话]`、`[🔍 政策校对]`、`[🔄 青年态]`、`[🏛️ 政论体]`，点击一键原地润色。
- **版本差异 Diff 高亮视图**：行级差异对比，直观展现 `<ins>` 新增与 `<del>` 删改。
- **国家标准红头公文排版实时预览**：直观预览红头标头、发文字号、小标宋标题、黑体/楷体层级标题与仿宋正文。

### 4. 🎨 UI/UX 视觉美学
- **🧘 极简专注写作模式 (Zen Focus Mode)**：一键收缩侧栏，进入 980px 宽屏居中沉浸式纸张排版。
- **📊 动态质量自愈雷达图**：基于 SVG 动态实时渲染六维公文质量雷达图（政治方向、体例规范、逻辑严谨、表述得体等）。
- **三款专属主题**：星月夜深色（默认）、经典流光白、苹果极简风。

---

## 🛠️ 快速上手

### 环境要求
- Python 3.11+
- Node.js 18+ / npm

### 1. 后端启动 (FastAPI)

```bash
# 进入后端目录
cd backend

# 安装 Python 依赖
pip install -r requirements.txt

# 启动开发服务器（端口 8000）
uvicorn main:app --reload --port 8000
```

### 2. 前端启动 (Vue 3 + Vite)

```bash
# 进入前端目录
cd frontend

# 安装前端依赖
npm install

# 启动前端开发服务器（端口 5173，内置代理转发至后端 8000）
npm run dev
```

### 3. 生产单端口部署

```bash
# 编译前端生产包
npm --prefix frontend run build

# 启动后端（FastAPI 会自动托管 frontend/dist 静态资源）
uvicorn backend.main:app --port 8000
```
浏览器直接访问 `http://localhost:8000` 即可。

---

## 🧪 自动化测试与质量保障

项目内置 140 项覆盖全链路的单元测试与集成测试：

```powershell
# 运行全量后端单元测试
$env:PYTHONPATH=".."; python -m unittest discover -s backend/tests -p "test_*.py"
```

测试覆盖范围：
- `test_v2_features.py`: 存储分拆、历史 BM25 检索、时光机快照回滚、单位知识库 CRUD、GB/T 9704 Docx 导出、动态 Few-Shot、分段起草与红蓝军测试。
- `test_assistant_v2.py`: 辅助智能体 5 大新工具、全景看板上下文注水、公文国标速查。
- `test_engine.py` / `test_agents.py` / `test_review.py`: 工作流引擎状态机、多专家协商与加权仲裁、自愈改写收敛。
- `test_api.py` / `test_p0_p3.py`: HTTP 接口规范、安全加密备份与恢复。

---

## 📂 项目结构全景

```text
writer_studio/
├── backend/
│   ├── api/                  # FastAPI 路由端点
│   │   ├── assistant.py      # 辅助智能体对话与动作 API
│   │   ├── backup.py         # 全量安全备份与恢复 API
│   │   ├── config.py         # 双轨模型密钥与配置 API
│   │   ├── knowledge.py      # 内置与单位专有知识库/模板 API
│   │   ├── profile.py        # 用户写作画像与偏好 API
│   │   ├── projects.py       # 项目 CRUD、全文检索与 Docx 导出 API
│   │   └── workflow.py       # 主写作工作流、自愈、伴写与红蓝军 API
│   ├── core/                 # 核心算法与领域引擎
│   │   ├── agents.py         # 6专家协商、加权仲裁决策、红蓝军测试
│   │   ├── assistant.py      # 辅助智能体 ReAct 工具循环与执行器
│   │   ├── engine.py         # WorkflowEngine 状态机、分段起草与自愈
│   │   ├── exporter.py       # GB/T 9704-2012 国家标准 Word 导出器
│   │   ├── llm.py            # 多模型适配层与 Function Calling
│   │   ├── retrieval.py      # BM25 检索、少样本抽取与政策召回
│   │   └── review.py         # 逐维度评分公式、规则审查与辩论
│   ├── domain/               # 领域模型与注册表
│   │   ├── registry.py       # 统一只读注册表
│   │   └── schemas.py        # Pydantic 领域模型（单一数据真相）
│   ├── storage/              # 本地持久化层
│   │   ├── crypto.py         # 敏感密钥本地加密存储 (Fernet)
│   │   ├── custom_kb.py      # 单位专有知识库与模板存储
│   │   └── store.py          # 单项目拆分存储、时光机快照与 BM25 索引
│   └── tests/                # 140 项完整单元测试集
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── assistant/    # 随叫随到辅助智能体面板
│   │   │   ├── config/       # 双轨道与模型设置面板
│   │   │   ├── knowledge/    # 政策库、范文库、单位专有库与模板面板
│   │   │   ├── profile/      # 写作画像雷达图与偏好面板
│   │   │   ├── project/      # 历史项目浏览器与全文搜索面板
│   │   │   └── workflow/     # 划词伴写浮条、Diff对比、GB/T 9704预览、时光机抽屉
│   │   ├── stores/           # Pinia 状态管理
│   │   └── styles/           # 设计 Token、玻璃拟态与三主题 CSS
│   └── package.json
└── README.md
```

---

## 📜 许可协议与标准引用
- 本项目遵循 MIT 开源协议。
- 公文格式规范依据：**GB/T 9704-2012《党政机关公文格式》**、**中办发〔2012〕14号《党政机关公文处理工作条例》**。

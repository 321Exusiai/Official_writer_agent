# 公文写作工作室（writer_studio）

工作流驱动的公文写作辅助工具。FastAPI 后端 + Vue 3 前端。

## 启动

### 后端

```bash
cd writer_studio/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 前端（开发）

```bash
cd writer_studio/frontend
npm install
npm run dev          # http://localhost:5173（代理 /api 到 8000）
```

### 前端（生产，单端口）

```bash
cd writer_studio/frontend
npm run build        # 产出 dist/，由 FastAPI 托管
```

然后仅启动后端，访问 http://localhost:8000。

## 测试

```bash
python -m unittest discover -s writer_studio/backend/tests -p "test_*.py"
```

## 说明

- **规则模式**：未配置 LLM 时，写作/审查走规则版，UI 明确标注「规则模式」，不冒充 LLM 结果。
- **三壁纸**：星月夜（默认）/ 经典流光 / 苹果极简，右上角切换。
- **数据**：项目持久化于 `backend/data/projects.json`；知识库为只读 `backend/knowledge/data/*.json`。

## 当前进度

- [x] P0 骨架：FastAPI + 前端脚手架 + 统一注册表 + 三壁纸 + 项目浏览器
- [x] P1 主链：问卷→规划→写作→审查→一文多体→交付（规则版）+ SSE 过程面板
- [ ] P2 真实协作：LLM 协商/辩论/决策 + 工具闭环
- [ ] P3 知识库完整化
- [ ] P4 打磨

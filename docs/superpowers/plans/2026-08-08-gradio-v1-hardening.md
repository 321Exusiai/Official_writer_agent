# gradio_app_v1 (V11) 修复与主题移植 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 gradio_app_v1.py（V11）的三个启动级崩溃，并将 v10（gradio_app.py）已验证的改进移植过来：自定义场景路由、写作文案、星月夜 SMIL 动画、苹果极简第三主题，以及安全与无障碍项。

**Architecture:** 纯前端（Gradio Blocks）修复与移植，不动 src/ 后端。三个崩溃分别是：`gr.Dataframe` 的 `height` 参数与 Gradio 5.35 不兼容；事件绑定引用已删除的 `topic_selector` 组件；事件绑定引用不存在的 `q_btn_next` 按钮。主题移植直接复制 gradio_app.py 中已验证的常量（同仓库、内容一致，DRY）。

**Tech Stack:** Python 3.11、Gradio 5.35.0、gradio_app_v1.py（公文写作智能体 V11）。

## Global Constraints

- 只改 `gradio_app_v1.py`。`gradio_app.py`（V10）与 `src/core/*` 在本次计划中**不得再修改**。
- 安装的 Gradio 版本固定为 5.35.0：`gr.Dataframe` 不接受 `height` 参数。
- UI 文案使用中文（与现有 UI 一致）。
- 不自动执行 git commit（工作区含大量无关未提交改动）；如需提交必须先与用户确认。
- 每个任务的验收标准：`python -m py_compile gradio_app_v1.py` 通过，且（除 Task 1-2 外）`python -c "import gradio_app_v1; gradio_app_v1.build_ui(); print('BUILD OK')"` 以退出码 0 结束。

---

### Task 1: 修复启动崩溃 #1 — gr.Dataframe 移除 height 参数

**Files:**
- Modify: `gradio_app_v1.py:2852-2859`（`ref_docs_table = gr.Dataframe(...)` 定义）

**Interfaces:**
- Consumes: 无（纯组件参数修复）
- Produces: 无新增接口；`ref_docs_table` 组件继续被 `ref_search_btn`/`ref_docs_table.select` 使用（7 列数据保持不变）

- [ ] **Step 1: 删除 `height=250,` 行**

把：

```python
                        ref_docs_table = gr.Dataframe(
                            headers=["文档ID", "标题", "格式", "字数", "日期", "来源", "所属主题"],
                            datatype=["str", "str", "str", "number", "str", "str", "str"],
                            col_count=(7, "fixed"),
                            interactive=False,
                            wrap=True,
                            height=250
                        )
```

改为（仅删最后一行参数，其余不动）：

```python
                        ref_docs_table = gr.Dataframe(
                            headers=["文档ID", "标题", "格式", "字数", "日期", "来源", "所属主题"],
                            datatype=["str", "str", "str", "number", "str", "str", "str"],
                            col_count=(7, "fixed"),
                            interactive=False,
                            wrap=True
                        )
```

- [ ] **Step 2: 验证语法**

Run: `python -m py_compile gradio_app_v1.py`
Expected: 退出码 0，无输出。

- [ ] **Step 3: 验证参数已移除**

Run: `Select-String -Path gradio_app_v1.py -Pattern "height=250"`
Expected: 无匹配（输出为空）。

---

### Task 2: 修复启动崩溃 #2 — 移除未定义组件 topic_selector 的引用

**Files:**
- Modify: `gradio_app_v1.py:3037`（`login_user_fn` 返回元组第 4 位）与 `gradio_app_v1.py:3066`（`user_login_btn.click` 的 outputs 列表）

**Interfaces:**
- Consumes: 无
- Produces: `login_user_fn` 返回值数量从 26 变为 25，与 `user_login_btn.click` 的 outputs 数量同步

- [ ] **Step 1: 从返回元组删除第 4 个元素**

在 `login_user_fn`（约 3033-3060 行）中，删除这一行（元组第 4 位）：

```python
                gr.update(choices=app.get_topics_list(), value=None),
```

删除后元组变为 25 个值，其余元素顺序不动（`msg` → `user_status` → `project_selector` → `active_proj_title` → `plan_output_text` → …）。

- [ ] **Step 2: 从 outputs 列表删除同名引用**

在 `user_login_btn.click`（约 3062-3076 行）的 outputs 列表中，删除 `topic_selector,`：

```python
                global_status_msg, user_status_msg, project_selector, topic_selector,
```

改为：

```python
                global_status_msg, user_status_msg, project_selector,
```

（本行其余内容不变，后续 `active_proj_title, plan_output_text, ...` 保持原样。）

- [ ] **Step 3: 验证引用已清零**

Run: `Select-String -Path gradio_app_v1.py -Pattern "topic_selector"`
Expected: 无匹配。

- [ ] **Step 4: 验证语法**

Run: `python -m py_compile gradio_app_v1.py`
Expected: 退出码 0。

---

### Task 3: 修复启动崩溃 #3 — q_btn_next 重绑到存在的按钮

**Files:**
- Modify: `gradio_app_v1.py:3717-3720`（`q_btn_next.click(...)` 绑定块）

**Interfaces:**
- Consumes: `update_plan_components()`（同文件 3709-3714 行，无参、返回 `(md_str, gr.update)` 二元组）、`q_btn_submit` / `q_btn_finish`（布局中已存在的按钮）
- Produces: `update_plan_components` 在两个既有按钮上以 `.then` 链式触发，输出仍为 `[doc_type_recommend_md, ui_doc_selector]`

- [ ] **Step 1: 替换绑定块**

把：

```python
        # 当从问卷进入Plan时更新文种推荐与下拉框默认值
        q_btn_next.click(
            fn=update_plan_components,
            outputs=[doc_type_recommend_md, ui_doc_selector]
        )
```

改为：

```python
        # 当问卷提交/提前完成时更新文种推荐与下拉框默认值
        # （V11 布局无 q_btn_next 按钮，改挂在 submit/finish 的 .then 链上）
        q_btn_submit.click(
            fn=update_plan_components,
            outputs=[doc_type_recommend_md, ui_doc_selector]
        )
        q_btn_finish.click(
            fn=update_plan_components,
            outputs=[doc_type_recommend_md, ui_doc_selector]
        )
```

- [ ] **Step 2: 验证引用已清零**

Run: `Select-String -Path gradio_app_v1.py -Pattern "q_btn_next"`
Expected: 无匹配。

- [ ] **Step 3: 全量构建冒烟（本任务为最后一个崩溃修复，必须整链通过）**

Run: `python -c "import gradio_app_v1; gradio_app_v1.build_ui(); print('BUILD OK')"`
Expected: 输出 `BUILD OK`，退出码 0。

> 已知非致命现象（允许存在，Task 5 会消除）：构建输出中会出现 `UserWarning: The value passed into gr.Dropdown() is not in the list of choices ... 全部主题`——来自 `ref_filter_topic`（2846 行），不阻止构建。

---

### Task 4: 移植 P2 — 自定义场景描述写入写作简报

**Files:**
- Modify: `gradio_app_v1.py:543-549`（`submit_routing_choice_fn` 的 `is_custom` 分支）与 `569-570`（`routing_complete` 成功消息）

**Interfaces:**
- Consumes: `self.orchestrator.brief.key_materials`（WritingBrief 既有字段，见 `src/questionnaire/questionnaire.py`）
- Produces: 无新接口；`submit_routing_choice_fn` 的 13 元组返回签名不变

- [ ] **Step 1: 在 `is_custom` 分支记录描述到简报**

把：

```python
        # 执行路由
        if is_custom:
            if not custom_text:
                ui = self._get_routing_ui_state()
                return "选择了自定义场景，请在输入框中对该写作场景进行简短描述。", "", "", "", gr.update(elem_classes="ios-card ws-panel-visible"), gr.update(elem_classes="ws-panel-hidden"), "", "", "", "", ui["title"], ui["options_text"], gr.update(choices=ui["choices"], value=None)
            # Fallback 路由：默认选择第一个
            print(f"[DEBUG] Executing fallback routing with choice_index=0")
            result = self.orchestrator.submit_routing_choice(0)
        else:
            print(f"[DEBUG] Executing routing with choice_index={choice_idx}")
            result = self.orchestrator.submit_routing_choice(choice_idx)
```

改为：

```python
        # 执行路由
        custom_note = ""
        if is_custom:
            if not custom_text:
                ui = self._get_routing_ui_state()
                return "选择了自定义场景，请在输入框中对该写作场景进行简短描述。", "", "", "", gr.update(elem_classes="ios-card ws-panel-visible"), gr.update(elem_classes="ws-panel-hidden"), "", "", "", "", ui["title"], ui["options_text"], gr.update(choices=ui["choices"], value=None)
            # 自定义场景描述不再被丢弃——写入写作简报，后续写作与审查都会用到；
            # 路由本身按默认场景进入流程（决策树不支持按自由文本路由）
            try:
                if self.orchestrator and self.orchestrator.brief:
                    base = self.orchestrator.brief.key_materials or ""
                    self.orchestrator.brief.key_materials = (
                        (base + "\n" if base else "") + f"【自定义场景描述】{custom_text}"
                    )
                    custom_note = "（已记录你的场景描述，将并入写作简报）"
            except Exception:
                pass
            print(f"[DEBUG] Custom routing recorded: {custom_text[:60]}")
            result = self.orchestrator.submit_routing_choice(0)
        else:
            print(f"[DEBUG] Executing routing with choice_index={choice_idx}")
            result = self.orchestrator.submit_routing_choice(choice_idx)
```

- [ ] **Step 2: 在成功消息中追加提示**

把 `routing_complete` 分支的成功消息（约 569-571 行）：

```python
                return (
                    f"✅ 锚定成功！我们将采用【{get_mode_profile(self.orchestrator.writing_mode).name}】笔法。为了写出带感的好文章，请回答这几个关键问题：",
```

改为：

```python
                return (
                    f"✅ 锚定成功！我们将采用【{get_mode_profile(self.orchestrator.writing_mode).name}】笔法。{custom_note} 为了写出带感的好文章，请回答这几个关键问题：",
```

- [ ] **Step 3: 验证**

Run: `Select-String -Path gradio_app_v1.py -Pattern "【自定义场景描述】"`
Expected: 1 处匹配。

Run: `python -c "import gradio_app_v1; gradio_app_v1.build_ui(); print('BUILD OK')"`
Expected: `BUILD OK`。

---

### Task 5: 移植 P3 文案 + "全部主题" choices 修复 + 温度标签澄清

**Files:**
- Modify: `gradio_app_v1.py:2783`（write_start_btn 文案）、`2846`（ref_filter_topic choices）、`2934`（api_temp 标签）

**Interfaces:**
- Consumes: 无
- Produces: 无新接口

- [ ] **Step 1: 更新写作按钮文案**

把：

```python
                            write_start_btn = gr.Button("开始写作（通常需要 30-60 秒）", variant="primary", elem_classes="ios-btn-primary")
```

改为：

```python
                            write_start_btn = gr.Button("开始写作（多智能体协商 + 生成，首次可能需要 1-3 分钟）", variant="primary", elem_classes="ios-btn-primary")
```

- [ ] **Step 2: 修复"全部主题"不在 choices 的告警**

把：

```python
                            ref_filter_topic = gr.Dropdown(label="按主题过滤", choices=app.get_topics_list(), value="全部主题", scale=2)
```

改为：

```python
                            ref_filter_topic = gr.Dropdown(label="按主题过滤", choices=["全部主题"] + app.get_topics_list(), value="全部主题", scale=2)
```

- [ ] **Step 3: 澄清 api_temp 语义（避免与 Agent Hub 温度混淆）**

把：

```python
                            api_temp = gr.Slider(0.0, 2.0, value=0.7, step=0.1, label="创新度 (Temperature)")
```

改为：

```python
                            api_temp = gr.Slider(0.0, 2.0, value=0.7, step=0.1, label="创新度默认值 (保存到配置)", info="实际写作使用右侧「Agent 决策大脑」的创新温度滑杆")
```

- [ ] **Step 4: 验证构建无 Dropdown 告警**

Run: `python -c "import gradio_app_v1; gradio_app_v1.build_ui(); print('BUILD OK')" 2>&1 | Select-String -Pattern 'not in the list|BUILD OK'`
Expected: 只输出 `BUILD OK`（无 `not in the list` 告警）。

---

### Task 6: 移植星月夜内联 SVG（SMIL 动画真正执行）

**Files:**
- Modify: `gradio_app_v1.py:1654-1668`（`THEME_STARRY_NIGHT_HTML` 整块替换）
- 内容来源（复制，不要手改）：`gradio_app.py:1056-1184` 中已验证的 `THEME_STARRY_NIGHT_HTML`（内联 `<svg id="starry-night-bg">` + 8 组 `<animateTransform>` + 模糊半径 24/12/6 + 容器透明 + reduced-motion 隐藏）

**Interfaces:**
- Consumes: 无
- Produces: `THEME_STARRY_NIGHT_HTML` 从"背景图 data-URI（SMIL 在浏览器中静止）"变为"内联 SVG（SMIL 持续旋转）"；`update_bg_theme`（3767 行）与 `dynamic_theme_css`（2545 行）的消费方式不变

- [ ] **Step 1: 用标记替换脚本整块替换常量**

v1 当前常量以 `THEME_STARRY_NIGHT_HTML = """` 开头、以 `</style>\n"""` 结尾。写临时脚本 `_theme_rewrite_tmp.py`：

```python
# -*- coding: utf-8 -*-
"""临时脚本：把 v1 的 THEME_STARRY_NIGHT_HTML 替换为 v10(gradio_app.py) 已验证的内联 SVG 版本。用后即删。"""
import io
src_v10 = io.open("gradio_app.py", encoding="utf-8").read()
start10 = src_v10.index('THEME_STARRY_NIGHT_HTML = """')
end10 = src_v10.index('</svg>\n"""', start10) + len('</svg>\n"""')
NEW_STARRY = src_v10[start10:end10]   # 直接从 v10 提取，保证逐字一致

p = "gradio_app_v1.py"
s = io.open(p, encoding="utf-8").read()
start = s.index('THEME_STARRY_NIGHT_HTML = """')
end = s.index('</style>\n"""', start) + len('</style>\n"""')
s = s[:start] + NEW_STARRY + s[end:]
io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print("OK", s.count("<animateTransform"), s.count("starry-night-bg"))
```

Run: `python _theme_rewrite_tmp.py`
Expected: 输出 `OK 8 1`。

Run: `Remove-Item _theme_rewrite_tmp.py`（删除临时脚本）

- [ ] **Step 2: 验证**

Run: `python -c "import gradio_app_v1 as m; assert m.THEME_STARRY_NIGHT_HTML.count('<animateTransform')==8; assert 'starry-night-bg' in m.THEME_STARRY_NIGHT_HTML; assert 'data:image/svg+xml' not in m.THEME_STARRY_NIGHT_HTML; print('STARRY OK')"`
Expected: `STARRY OK`。

Run: `python -c "import gradio_app_v1; gradio_app_v1.build_ui(); print('BUILD OK')"`
Expected: `BUILD OK`。

---

### Task 7: 移植苹果极简第三主题

**Files:**
- Modify: `gradio_app_v1.py:1669` 之后插入 `THEME_APPLE_MINIMAL_HTML` 常量；`2615-2619`（bg_theme_selector choices）；`3767-3771`（update_bg_theme）
- 内容来源（复制）：`gradio_app.py:1192-1323` 的 `THEME_APPLE_MINIMAL_HTML` 常量（浅色 F5F5F7 / 白卡片 / Apple 蓝 0A84FF / 无模糊）

**Interfaces:**
- Consumes: 无
- Produces: `THEME_APPLE_MINIMAL_HTML`（新常量）；`update_bg_theme` 三分支；`bg_theme_selector` 三个选项

- [ ] **Step 1: 插入常量**

在 `gradio_app_v1.py` 的 `THEME_STARRY_NIGHT_HTML` 常量结束（`"""`，约 1668 行）与 `# ═══... 界面构建` 注释之间，粘贴 `gradio_app.py:1192-1323` 的 `THEME_APPLE_MINIMAL_HTML = """..."""` 整块（含顶部注释 `/* 苹果极简主题：浅色、克制动效、单一强调色，遵循 Apple HIG 克制原则 */`）。

- [ ] **Step 2: 更新主题下拉框选项**

把：

```python
                    bg_theme_selector = gr.Dropdown(
                        label="背景美学风格",
                        choices=["经典流光 (Classic Fluid)", "星月夜漩涡 (Starry Night)"],
                        value="星月夜漩涡 (Starry Night)"
                    )
```

改为：

```python
                    bg_theme_selector = gr.Dropdown(
                        label="背景美学风格",
                        choices=["星月夜漩涡 (Starry Night)", "经典流光 (Classic Fluid)", "苹果极简 (Apple Minimal)"],
                        value="星月夜漩涡 (Starry Night)"
                    )
```

- [ ] **Step 3: 更新切换函数三分支**

把：

```python
        def update_bg_theme(choice):
            if choice == "经典流光 (Classic Fluid)":
                return THEME_CLASSIC_HTML
            else:
                return THEME_STARRY_NIGHT_HTML
```

改为：

```python
        def update_bg_theme(choice):
            if choice == "经典流光 (Classic Fluid)":
                return THEME_CLASSIC_HTML
            if choice == "苹果极简 (Apple Minimal)":
                return THEME_APPLE_MINIMAL_HTML
            return THEME_STARRY_NIGHT_HTML
```

- [ ] **Step 4: 验证**

Run: `python -c "import gradio_app_v1 as m; assert '#0A84FF' in m.THEME_APPLE_MINIMAL_HTML; print('APPLE OK')"`
Expected: `APPLE OK`。

Run: `Select-String -Path gradio_app_v1.py -Pattern "苹果极简 \(Apple Minimal\)" | Measure-Object | Select-Object -ExpandProperty Count`
Expected: 2（bg_theme_selector 的 choices 中 1 处 + update_bg_theme 分支中 1 处；常量注释里的"苹果极简主题"不含 "(Apple Minimal)" 后缀，不计数）。

Run: `python -c "import gradio_app_v1; gradio_app_v1.build_ui(); print('BUILD OK')"`
Expected: `BUILD OK`。

---

### Task 8: 安全 — 关闭公网共享

**Files:**
- Modify: `gradio_app_v1.py:3783`

**Interfaces:**
- Consumes: 无
- Produces: 无

- [ ] **Step 1: 改 share 参数**

把：

```python
    demo.launch(share=True, inbrowser=True)
```

改为：

```python
    demo.launch(share=False, inbrowser=True)
```

- [ ] **Step 2: 验证**

Run: `Select-String -Path gradio_app_v1.py -Pattern "share=True"`
Expected: 无匹配。

Run: `python -m py_compile gradio_app_v1.py`
Expected: 退出码 0。

---

### Task 9: 无障碍 — user_input 中文可访问名

**Files:**
- Modify: `gradio_app_v1.py:2570-2575`

**Interfaces:**
- Consumes: 无
- Produces: `user_input` 组件的可访问名从默认变量名 `user_input` 变为 `用户名`

- [ ] **Step 1: 补 label**

把：

```python
                    user_input = gr.Textbox(
                        show_label=False,
                        placeholder="输入姓名以切换或建立新空间",
                        value=app.current_user_name or "",
                        scale=2
                    )
```

改为：

```python
                    user_input = gr.Textbox(
                        label="用户名",
                        show_label=False,
                        placeholder="输入姓名以切换或建立新空间",
                        value=app.current_user_name or "",
                        scale=2
                    )
```

- [ ] **Step 2: 验证**

Run: `python -c "import gradio_app_v1; gradio_app_v1.build_ui(); print('BUILD OK')"`
Expected: `BUILD OK`（`show_label=False` 仅隐藏视觉标签，Gradio 5 仍以 label 作为输入框可访问名）。

---

### Task 10: 最终验证

**Files:**
- 无改动；仅验证

**Interfaces:**
- Consumes: Task 1-9 全部产物

- [ ] **Step 1: 语法 + 构建 + 后端回归**

Run: `python -m py_compile gradio_app_v1.py`
Expected: 退出码 0。

Run: `python -c "import gradio_app_v1; gradio_app_v1.build_ui(); print('BUILD OK')" 2>&1 | Select-Object -Last 3`
Expected: 输出含 `BUILD OK`，无异常堆栈。

Run: `python run_tests.py 2>&1 | Select-Object -Last 3`
Expected: `测试完成: 16 通过, 0 失败`（后端未改动，回归确认）。

- [ ] **Step 2: 汇总 grep 断言（可选复检）**

Run: `Select-String -Path gradio_app_v1.py -Pattern "topic_selector|q_btn_next|share=True|height=250"`
Expected: 无匹配。

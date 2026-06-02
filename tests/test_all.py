"""
公文写作智能体 — 测试套件 (V2：模式感知版)

验证各模块的正确性和协作流程。
"""

import sys
import os

if sys.platform == 'win32':
    import io
    try:
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.questionnaire.questionnaire import (
    Questionnaire, WritingBrief, QuestionnairePhase,
)
from src.core.style_adapter import (
    StyleAdapter, MediaStyle, STYLE_PROFILES, StyleBlend,
)
from src.core.document_type import (
    DocumentTypeIdentifier, DocumentType, DOC_TYPE_PROFILES
)
from src.core.writer_agent import WriterAgent, WriterConfig
from src.core.reviewer_agent import (
    ReviewerAgent, ReviewResult, ALL_ERROR_DBS, OBJECTIVE_ERROR_DB,
)
from src.core.orchestrator import Orchestrator, OrchestratorState
from src.core.writing_mode import (
    WritingMode, ALL_PRINCIPLES, DECISION_TREE,
    get_mode_profile, get_review_dimensions, get_mode_questions,
    navigate_tree,
)
from src.knowledge.knowledge_base import KnowledgeBase


def test_writing_mode_module():
    """测试写作模式模块"""
    print("=" * 40)
    print("测试 1: 写作模式模块")
    print("=" * 40)

    assert len(ALL_PRINCIPLES) == 4
    for mode, profile in ALL_PRINCIPLES.items():
        assert profile.name
        assert len(profile.principles) >= 3
        assert len(profile.content_rules["must_write"]) > 0
        assert len(profile.forbidden_patterns) > 0
        assert len(profile.language_guidelines) > 0
        print(f"  [OK] {profile.name}: {len(profile.principles)}条原则")

    assert len(DECISION_TREE) >= 5
    print(f"  [OK] 决策树: {len(DECISION_TREE)}个节点")

    for mode in WritingMode:
        dims = get_review_dimensions(mode)
        assert len(dims) >= 3, f"{mode.value} 应有至少3个审查维度"
        questions = get_mode_questions(mode)
        assert len(questions) >= 4, f"{mode.value} 应有至少4个问题"
        print(f"  [OK] {mode.value}: {len(dims)}审查维度, {len(questions)}个问题")

    mode, subtype, desc = navigate_tree([0, 1])
    assert mode == WritingMode.STRATEGIC_NARRATIVE
    print(f"  [OK] 导航测试: {desc} -> {mode.value}")

    mode, subtype, desc = navigate_tree([1, 0])
    assert mode == WritingMode.ADMINISTRATIVE
    print(f"  [OK] 导航测试: {desc} -> {mode.value}")

    print("[PASS] 写作模式模块测试通过")


def test_questionnaire():
    """测试新版问卷模块（决策树路由 + 模式专属问题）"""
    print("\n" + "=" * 40)
    print("测试 2: 问卷模块")
    print("=" * 40)

    q = Questionnaire()

    routing_q = q.get_routing_question()
    assert routing_q is not None
    assert routing_q["phase"] == "routing"
    assert len(routing_q["options"]) == 4

    result = q.submit_routing_choice(0)
    assert result["phase"] in ["routing", "routing_complete"]

    if result["phase"] == "routing":
        result = q.submit_routing_choice(1)

    assert result["phase"] == "routing_complete"
    assert result["mode"] == WritingMode.STRATEGIC_NARRATIVE.value
    print(f"  路由结果: {result['mode_name']} ({result['path']})")
    print(f"  模式专属问题数: {result['total_mode_questions']}")

    for i in range(result["total_mode_questions"]):
        mode_q = q.get_current_mode_question()
        assert mode_q is not None
        has_next = q.submit_mode_answer(f"测试回答第{i+1}题")
        if i < result["total_mode_questions"] - 1:
            assert has_next

    assert q.is_complete()
    brief = q.get_brief()
    assert brief.is_complete()
    assert brief.writing_mode == WritingMode.STRATEGIC_NARRATIVE.value

    summary = q.generate_brief_summary()
    assert "写作模式" in summary

    print("[PASS] 新版问卷模块测试通过")

    print("\n  --- 测试不同路由路径 ---")
    for route_path, expected_mode in [
        ([1, 0], WritingMode.ADMINISTRATIVE),
        ([3, 1], WritingMode.OBJECTIVE_REPORT),
        ([2, 0], WritingMode.INFORMATIONAL),
    ]:
        q2 = Questionnaire()
        for choice in route_path:
            result = q2.submit_routing_choice(choice)
        assert result["phase"] == "routing_complete"
        assert WritingMode(result["mode"]) == expected_mode
        print(f"  路径 {route_path} -> {expected_mode.value} [OK]")

    print("[PASS] 多路径路由测试通过")


def test_style_adapter():
    """测试风格适配模块"""
    print("\n" + "=" * 40)
    print("测试 3: 风格适配模块")
    print("=" * 40)

    adapter = StyleAdapter()
    assert len(adapter.list_styles()) == 5

    style = adapter.auto_select_style("分管学生工作的副校长", "让领导看到投入值得")
    assert style in [MediaStyle.PEOPLE_DAILY, MediaStyle.XINHUA, MediaStyle.GUANGMING]

    style = adapter.auto_select_style("媒体记者", "新闻发布通稿")
    assert style == MediaStyle.XINHUA

    style = adapter.auto_select_style("行政秘书", "关于举办会议的通知")
    assert style == MediaStyle.GOVERNMENT_ADMIN

    for style_enum, profile in STYLE_PROFILES.items():
        assert profile.name
        assert profile.opening_template
        assert profile.body_template
        assert profile.closing_template
        assert profile.example_opening
        assert profile.example_closing
        assert len(profile.language_features) > 0
        assert len(profile.forbidden_patterns) > 0

    assert MediaStyle.GOVERNMENT_ADMIN in STYLE_PROFILES
    gov_profile = STYLE_PROFILES[MediaStyle.GOVERNMENT_ADMIN]
    assert gov_profile.name == "党政机关行文规范风格"
    assert len(gov_profile.vocabulary_pool.get("formulaic", [])) > 3

    profile = STYLE_PROFILES[MediaStyle.XINHUA]
    injection = adapter.get_system_prompt_injection(profile)
    assert "新华社" in injection
    assert "严禁" in injection

    print("[PASS] 风格适配模块测试通过")


def test_document_type():
    """测试文种识别模块"""
    print("\n" + "=" * 40)
    print("测试 4: 文种识别模块")
    print("=" * 40)

    brief = WritingBrief(
        writing_mode=WritingMode.STRATEGIC_NARRATIVE.value,
        purpose="让领导看到这次研学投入是值得的",
        primary_audience="分管学生工作的副校长",
        secondary_audiences=["教务处", "学生家长"],
        deep_meaning="培养质量获得了顶尖平台的认可",
        strategic_anchor="对应拔尖创新人才培养计划",
        key_materials="学生感言、参观记录",
    )

    identifier = DocumentTypeIdentifier()
    ranked = identifier.identify(brief)
    assert len(ranked) > 0

    for dt, profile in DOC_TYPE_PROFILES.items():
        assert profile.name_cn
        assert profile.opening_template
        assert profile.body_template
        assert profile.closing_template
        assert len(profile.key_features) > 0
        assert profile.typical_length_range[0] > 0

    print("[PASS] 文种识别模块测试通过")


def test_writer_agent():
    """测试写作Agent（多模式）"""
    print("\n" + "=" * 40)
    print("测试 5: 写作Agent（多模式）")
    print("=" * 40)

    brief = WritingBrief(
        writing_mode=WritingMode.STRATEGIC_NARRATIVE.value,
        purpose="让领导看到研学投入值得",
        primary_audience="分管学生工作的副校长",
        deep_meaning="培养质量获得顶尖平台认可",
        strategic_anchor="对应拔尖创新人才培养计划",
        key_materials="三位同学在北大实验室的感言",
    )

    config = WriterConfig(
        writing_brief=brief,
        style_profile=STYLE_PROFILES[MediaStyle.PEOPLE_DAILY],
        doc_type_profile=DOC_TYPE_PROFILES[DocumentType.FEATURE],
        raw_materials="研学活动材料...",
        audience="upward",
        writing_mode=WritingMode.STRATEGIC_NARRATIVE,
    )

    writer = WriterAgent()
    writer.configure(config)

    system_prompt = writer.build_system_prompt()
    assert "公文写作专家" in system_prompt or "写作" in system_prompt
    assert "战略叙事原则" in system_prompt or "STRATEGIC" in system_prompt

    user_prompt = writer.build_user_prompt()
    assert "原始材料" in user_prompt or "写作模式" in user_prompt

    full_prompt = writer.get_full_prompt()
    assert "system" in full_prompt
    assert "user" in full_prompt

    outline = writer.generate_outline()
    assert "大纲" in outline or "写作模式" in outline

    print(f"  [OK] STRATEGIC_NARRATIVE: System Prompt {len(system_prompt)}字符")

    print("[PASS] 写作Agent测试通过")


def test_reviewer_agent():
    """测试审稿Agent（多模式）"""
    print("\n" + "=" * 40)
    print("测试 6: 审稿Agent（多模式）")
    print("=" * 40)

    reviewer = ReviewerAgent()

    assert len(ALL_ERROR_DBS) >= 4
    assert WritingMode.OBJECTIVE_REPORT in ALL_ERROR_DBS
    assert len(OBJECTIVE_ERROR_DB) >= 4, "OBJECTIVE_ERROR_DB 应有至少4个诊断条目"
    print(f"  错误诊断库: {len(ALL_ERROR_DBS)}个模式专属库")

    for mode in WritingMode:
        reviewer.set_mode(mode)
        dims = reviewer.get_dimensions()
        assert len(dims) >= 3, f"{mode.value} 应有至少3个审查维度"
        print(f"  {mode.value}: {len(dims)}个审查维度")

        for i, dim in enumerate(dims):
            assert dim["name"]
            assert len(dim["check_items"]) > 0
            assert dim["weight"] > 0

    reviewer.set_mode(WritingMode.STRATEGIC_NARRATIVE)
    bad_text = "北京大学教授详细介绍了图灵班的培养模式。活动结束后，大家纷纷表示收获很大。上午8点30分，同学们乘车前往下一站。本次活动圆满成功。"
    findings = reviewer.diagnose_errors(bad_text)
    assert len(findings) > 0, f"应该检测到错误，实际发现{len(findings)}个"

    we_heavy_text = "我们参观了实验室。同学们认真聆听。团队成员积极提问。我们的收获很大。师生们感受深刻。学院的培养模式得到了验证。"
    result = reviewer.check_subject_ratio(we_heavy_text)
    assert result["healthy"], f"主体性应该良好，实际我方占比{result['we_ratio']:.0%}"

    reviewer.set_mode(WritingMode.ADMINISTRATIVE)
    admin_text = "通知各学院请于2026年6月1日前提交年度工作总结。特此通知。"
    fmt_findings = reviewer.check_format_compliance(admin_text)

    draft = "测试稿件内容..."
    prompt = reviewer.build_review_prompt(draft, 0)
    assert prompt

    all_prompts = reviewer.get_all_round_prompts()
    assert len(all_prompts) == reviewer.get_round_count()

    print("[PASS] 审稿Agent测试通过")


def test_knowledge_base():
    """测试知识库模块"""
    print("\n" + "=" * 40)
    print("测试 7: 知识库模块")
    print("=" * 40)

    kb = KnowledgeBase()

    exemplars = kb.search_exemplars(doc_type="通讯")
    assert len(exemplars) > 0

    exemplar = kb.get_exemplar("shudao_xinge")
    assert exemplar is not None
    assert exemplar.title == "蜀道新歌"
    assert exemplar.style == "人民日报"

    bad_text = "大家纷纷表示收获很大，本次活动圆满成功。"
    findings = kb.diagnose_text(bad_text)
    assert len(findings) > 0

    term = kb.lookup_term("新质生产力")
    assert term is not None
    assert "创新" in term["definition"]

    transitions = kb.get_transitions("新华社")
    assert len(transitions) > 0

    summary = kb.get_style_exemplar_summary("光明日报")
    assert "光明日报" in summary or "荒凉" in summary

    tips = kb.get_writing_tips("通讯", "人民日报")
    assert len(tips) > 0

    print("[PASS] 知识库模块测试通过")


def test_orchestrator():
    """测试协调者Agent（新版API）"""
    print("\n" + "=" * 40)
    print("测试 8: 协调者Agent（新版）")
    print("=" * 40)

    orch = Orchestrator()

    routing_q = orch.start_routing()
    assert routing_q is not None

    result = orch.submit_routing_choice(0)
    if result["phase"] == "routing":
        result = orch.submit_routing_choice(1)
    assert result["phase"] == "routing_complete"
    print(f"  路由完成: {result['mode_name']}")

    for i in range(result["total_mode_questions"]):
        mode_q = orch.get_current_mode_question()
        if mode_q:
            orch.submit_mode_answer(f"测试回答第{i+1}题")

    brief = orch.questionnaire.get_brief()
    assert brief.is_complete()

    plan = orch.generate_plan()
    assert plan is not None
    assert plan.document_type in DocumentType
    assert plan.media_style in MediaStyle
    assert plan.writing_mode in WritingMode

    draft = orch.write("测试原始材料...")
    assert draft is not None

    reviews = orch.review()
    assert len(reviews) > 0
    print(f"  审查轮次: {len(reviews)}")

    output = orch.finalize()
    assert output is not None
    assert "mode_principles" in output

    prompts = orch.get_llm_prompts()
    assert "write" in prompts
    assert "reviews" in prompts
    assert "mode" in prompts

    summary = orch.get_workflow_summary()
    assert "写作模式" in summary or "工作流" in summary

    print("[PASS] 协调者Agent测试通过")


def test_orchestrator_legacy_compat():
    """测试协调者Agent旧版兼容性"""
    print("\n" + "=" * 40)
    print("测试 9: 协调者Agent（旧版兼容）")
    print("=" * 40)

    orch = Orchestrator()

    brief = orch.skip_questionnaire({
        "purpose": "让领导看到研学投入值得，培养方向正确",
        "primary_audience": "分管学生工作的副校长",
        "secondary_audiences": "教务处；学生家长",
        "deep_meaning": "培养质量获得顶尖平台认可",
        "strategic_anchor": "对应拔尖创新人才培养计划",
        "key_materials": "三位同学在北大实验室的感言",
    }, mode=WritingMode.STRATEGIC_NARRATIVE)
    assert brief.is_complete()

    plan = orch.generate_plan()
    assert plan.writing_mode == WritingMode.STRATEGIC_NARRATIVE

    draft = orch.write("测试材料")
    assert draft

    reviews = orch.review()
    assert len(reviews) > 0

    output = orch.finalize()
    assert output

    print("[PASS] 旧版兼容测试通过")


def test_admin_mode_workflow():
    """测试行政管理模式完整工作流"""
    print("\n" + "=" * 40)
    print("测试 10: 行政管理模式工作流")
    print("=" * 40)

    orch = Orchestrator()

    orch.start_routing()
    result = orch.submit_routing_choice(1)
    result = orch.submit_routing_choice(0)
    assert WritingMode(result["mode"]) == WritingMode.ADMINISTRATIVE
    print(f"  路由: {result['mode_name']}")

    for i in range(result["total_mode_questions"]):
        mode_q = orch.get_current_mode_question()
        if mode_q:
            orch.submit_mode_answer(f"测试通知内容第{i+1}题")

    plan = orch.generate_plan()
    assert plan.writing_mode == WritingMode.ADMINISTRATIVE

    draft = orch.write("关于举办2026年毕业典礼的通知")
    assert draft

    reviews = orch.review()
    assert len(reviews) > 0
    print(f"  ADMINISTRATIVE审查维度: {[r['round'] for r in reviews]}")

    output = orch.finalize()
    assert output["mode_principles"]
    print(f"  激活原则: {output['mode_principles']}")

    print("[PASS] 行政管理模式测试通过")


def test_iterative_review():
    """测试迭代式审查 — V2.1 核心功能"""
    print("\n" + "=" * 40)
    print("测试 11: 迭代式审查（审 -> 改 -> 审）")
    print("=" * 40)

    reviewer = ReviewerAgent()

    bad_text = (
        "北京大学教授安排了实验室参观。大家纷纷表示收获很大。"
        "上午8点30分，同学们乘车前往下一站。本次活动圆满成功。"
        "主办方组织了一场专题讲座，专家介绍了最新研究成果。"
    )
    print(f"  原始文本: {bad_text[:50]}...")

    auto_findings = reviewer.diagnose_errors(bad_text)
    assert len(auto_findings) > 0, "应该检测到错误"
    print(f"  发现 {len(auto_findings)} 个问题")

    fixed_text, change_log = reviewer.apply_fixes(bad_text, auto_findings)
    assert len(change_log) > 0, "应该有修改"
    print(f"  应用 {len(change_log)} 处修复")

    second_findings = reviewer.diagnose_errors(fixed_text)
    assert len(second_findings) < len(auto_findings), (
        f"迭代后应减少错误: 前{len(auto_findings)} -> 后{len(second_findings)}"
    )
    print(f"  迭代后剩余 {len(second_findings)} 个问题（减少 {len(auto_findings) - len(second_findings)}）")

    reviewer.set_mode(WritingMode.STRATEGIC_NARRATIVE)
    final_draft, iter_results = reviewer.iterate_review(
        bad_text,
        WritingMode.STRATEGIC_NARRATIVE,
    )
    assert len(iter_results) > 0
    assert len(final_draft) > 0
    assert final_draft != bad_text, "迭代后文本应有变化"

    total_fixes = sum(r["fixes_applied"] for r in iter_results)
    print(f"  迭代审查: {len(iter_results)} 轮, 共 {total_fixes} 处修复")

    print("[PASS] 迭代式审查测试通过")


def test_orchestrator_iterative_flow():
    """测试 Orchestrator 的迭代式审查集成"""
    print("\n" + "=" * 40)
    print("测试 12: Orchestrator 迭代审查集成")
    print("=" * 40)

    orch = Orchestrator()
    orch.skip_questionnaire(
        {
            "purpose": "让领导看到研学投入值得",
            "primary_audience": "分管学生工作的副校长",
            "deep_meaning": "培养质量获得顶尖平台认可",
            "strategic_anchor": "对应拔尖创新人才培养计划",
            "key_materials": "三位同学在北大实验室的感言",
        },
        mode=WritingMode.STRATEGIC_NARRATIVE,
    )
    orch.generate_plan()

    orch.write("北京大学教授安排了实验室参观。大家纷纷表示收获很大。本次活动圆满成功。")

    reviews = orch.review()
    assert len(reviews) > 0

    draft_after_review = orch.draft
    assert draft_after_review is not None

    original_findings = orch.reviewer.diagnose_errors(
        "北京大学教授安排了实验室参观。大家纷纷表示收获很大。本次活动圆满成功。"
    )
    residual_findings = orch.reviewer.diagnose_errors(draft_after_review)
    assert len(residual_findings) <= len(original_findings), (
        f"迭代审查应减少或保持错误数: 原{len(original_findings)} -> 后{len(residual_findings)}"
    )

    total_fixes = sum(r.get("fixes_applied", 0) for r in reviews)
    assert total_fixes > 0, "应该有自动修复"
    print(f"  审查轮次: {len(reviews)}, 总修复数: {total_fixes}")
    print(f"  原始错误数: {len(original_findings)}, 迭代后: {len(residual_findings)}")

    output = orch.finalize()
    assert output["draft"] is not None
    assert output["review_count"] > 0

    print("[PASS] Orchestrator 迭代审查集成测试通过")


def test_style_blend():
    """测试风格混合建议 — V2.2 新功能"""
    print("\n" + "=" * 40)
    print("测试 13: 风格混合建议（StyleBlend）")
    print("=" * 40)

    adapter = StyleAdapter()

    blend = adapter.suggest_blend(
        primary_audience="分管学生工作的副校长",
        purpose="展示研学成果",
        secondary_audiences=["媒体", "学生家长"],
    )
    assert blend.primary_style is not None
    assert blend.primary_weight > 0
    assert blend.primary_weight + blend.secondary_weight > 0.9
    assert len(blend.reasoning) > 0
    print(f"  混合建议: {blend.display()}")
    print(f"  推理: {blend.reasoning}")

    blend_dict = blend.to_dict()
    assert "primary" in blend_dict
    assert "secondary" in blend_dict
    assert "reasoning" in blend_dict

    print("[PASS] 风格混合建议测试通过")


def test_style_blend_single_audience():
    """测试单一受众不触发混合"""
    print("\n" + "=" * 40)
    print("测试 14: 单一受众风格选择")
    print("=" * 40)

    adapter = StyleAdapter()

    blend = adapter.suggest_blend(
        primary_audience="分管学生工作的副校长",
        purpose="展示研学成果",
    )
    assert blend.secondary_style is None or blend.secondary_weight == 0
    assert blend.primary_weight == 1.0
    print(f"  单一受众: {blend.display()}")

    print("[PASS] 单一受众风格测试通过")


def test_style_intensity():
    """测试风格强度参数 — V2.2 新功能"""
    print("\n" + "=" * 40)
    print("测试 15: 风格强度参数")
    print("=" * 40)

    adapter = StyleAdapter()
    profile = adapter.select_style(MediaStyle.PEOPLE_DAILY, intensity=0.3)

    assert adapter.intensity == 0.3

    prompt_low = adapter.get_system_prompt_injection(profile)
    assert "轻度风格" in prompt_low or "极简风格" in prompt_low
    print(f"  低强度 (0.3): {adapter._intensity_note()}")

    features_low = adapter._scale_language_features(profile)

    adapter.select_style(MediaStyle.PEOPLE_DAILY, intensity=0.9)
    prompt_high = adapter.get_system_prompt_injection(profile)
    assert "完整强度" in prompt_high or "标准强度" in prompt_high
    print(f"  高强度 (0.9): {adapter._intensity_note()}")

    features_high = adapter._scale_language_features(profile)
    assert len(features_high) >= len(features_low), "高强度应有更多语言特征"
    print(f"  低强度特征数: {len(features_low)}, 高强度特征数: {len(features_high)}")

    print("[PASS] 风格强度参数测试通过")


def test_orchestrator_hitl_methods():
    """测试 Orchestrator HITL 方法 — V2.2 新功能"""
    print("\n" + "=" * 40)
    print("测试 16: Orchestrator HITL 方法")
    print("=" * 40)

    orch = Orchestrator()
    orch.skip_questionnaire(
        {
            "purpose": "让领导看到研学投入值得",
            "primary_audience": "分管学生工作的副校长",
            "deep_meaning": "培养质量获得顶尖平台认可",
            "strategic_anchor": "对应拔尖创新人才培养计划",
            "key_materials": "三位同学在北大实验室的感言",
        },
        mode=WritingMode.STRATEGIC_NARRATIVE,
    )
    orch.generate_plan()
    orch.write("北京大学教授安排了实验室参观。大家纷纷表示收获很大。本次活动圆满成功。")

    reviews = orch.review()
    assert len(reviews) > 0

    issues = orch.get_review_issues()
    assert isinstance(issues, list)
    assert all("severity" in i for i in issues)
    assert all("issue" in i for i in issues)
    print(f"  get_review_issues: {len(issues)} 个问题")

    orch.update_draft("修改后的全新草稿内容，同学们在北大感受到顶尖科研氛围。")
    assert "顶尖科研氛围" in orch.draft
    print("  update_draft: 草稿已手动更新")

    new_reviews = orch.re_review()
    assert len(new_reviews) > 0
    print(f"  re_review: {len(new_reviews)} 轮审查完成")

    output = orch.finalize()
    assert output
    print("  finalize: 输出正常")

    print("[PASS] Orchestrator HITL 方法测试通过")


def run_all():
    """运行所有测试"""
    tests = [
        ("写作模式模块", test_writing_mode_module),
        ("新版问卷模块", test_questionnaire),
        ("风格适配模块", test_style_adapter),
        ("文种识别模块", test_document_type),
        ("写作Agent", test_writer_agent),
        ("审稿Agent", test_reviewer_agent),
        ("知识库模块", test_knowledge_base),
        ("协调者Agent（新版）", test_orchestrator),
        ("协调者Agent（旧版兼容）", test_orchestrator_legacy_compat),
        ("行政管理模式", test_admin_mode_workflow),
        ("迭代式审查", test_iterative_review),
        ("Orchestrator迭代集成", test_orchestrator_iterative_flow),
        ("风格混合建议", test_style_blend),
        ("单一受众风格", test_style_blend_single_audience),
        ("风格强度参数", test_style_intensity),
        ("Orchestrator HITL方法", test_orchestrator_hitl_methods),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"\n[FAIL] [{name}] 测试失败: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"  测试完成: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)

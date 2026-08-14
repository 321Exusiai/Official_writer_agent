"""
UIFormatter — 展示格式化 Mixin（重构阶段 1，从 Orchestrator 提取）

以 Mixin 方式注入 Orchestrator，负责将工作流状态、多智能体协作日志、
多版本文稿对比、审查总结等格式化为可展示文本。

依赖：本 Mixin 与 Orchestrator 共享 self 命名空间，可直接访问
agent_log/multi_versions/reviewer/coordinator/llm_client 等。
"""

from typing import Any, List, Dict

from .writing_mode import get_mode_profile


class UIFormatter:
    """展示格式化 Mixin：工作流摘要、协作日志、多版本对比、审查总结。"""

    def get_workflow_summary(self) -> str:
        if not self.brief:
            return "⚠️ 工作流尚未启动。请调用start_routing()开始。"

        # 使用列表收集字符串片段，最后一次性 join，避免多次字符串拼接的内存开销
        parts = [
            "═══════════════════════════════════════════",
            "  工 作 流 摘 要",
            "═══════════════════════════════════════════\n",
            f"【状态】{self.state.value}\n",
            f"【写作模式】{get_mode_profile(self.writing_mode).name}\n",
        ]

        if self.brief:
            purpose = self.brief.purpose or "未指定"
            audience = self.brief.primary_audience or "未指定"
            deep = self.brief.deep_meaning or "未指定"

            parts.append("【写作简报】")
            parts.append(f"  核心目的：{purpose[:80]}{'...' if len(purpose) > 80 else ''}")
            parts.append(f"  第一读者：{audience}")
            parts.append(f"  深层含义/核心发现：{deep[:60]}{'...' if len(deep) > 60 else ''}\n")

        if self.plan:
            parts.append("【写作方案】")
            parts.append(f"  文种：{self.plan.doc_type_name}")
            parts.append(f"  风格：{self.plan.style_name}")
            parts.append(f"  篇幅：{self.plan.estimated_length}")
            parts.append(f"  受众：{self.plan.audience_focus}\n")

        if self.draft:
            parts.append("【初稿状态】已生成\n")

        if self.review_results:
            passed_count = sum(1 for r in self.review_results if r.passed)
            parts.append(f"【审查结果】{passed_count}/{len(self.review_results)} 轮通过")
            parts.append(f"【审查维度】{', '.join(r.round_name for r in self.review_results)}")

        parts.append("═══════════════════════════════════════════")
        return "\n".join(parts)

    def get_agent_log_display(self) -> str:
        """展示多智能体协作日志"""
        if not self.agent_log:
            return "（暂无协作日志）"
        lines = ["═══════════════════════════════════════"]
        lines.append("  多智能体协作日志")
        lines.append("═══════════════════════════════════════")
        for entry in self.agent_log:
            lines.append(entry)
        lines.append("═══════════════════════════════════════")
        return "\n".join(lines)

    def get_multi_versions_display(self) -> str:
        """展示多版本文稿对比"""
        if not self.multi_versions:
            return "（未生成多版本文稿）"
        lines = ["═══════════════════════════════════════"]
        lines.append("  一文多体 — 版本对比")
        lines.append("═══════════════════════════════════════")
        for label, content in self.multi_versions.items():
            lines.append(f"\n【{label}】（{len(content)} 字）")
            lines.append(f"{content[:300]}...")
        lines.append("═══════════════════════════════════════")
        return "\n".join(lines)

    def _log_agent(self, agent: str, message: str):
        """记录智能体日志"""
        self.agent_log.append(f"  [{agent}] {message}")

    def _build_review_summary_display(self, iteration_results: List[Dict[str, Any]]) -> str:
        """构建审查总结的展示文本"""
        lines = ["【审查结果】"]
        for i, result in enumerate(self.reviewer.review_history):
            status = "✅ 通过" if result.passed else "❌ 未通过"
            lines.append(f"\n第{i+1}轮 {result.round_name}：{status}")
            if result.findings:
                for finding in result.findings:
                    lines.append(f"  • {finding.severity.value}: {finding.issue}")
                    if finding.suggestion:
                        lines.append(f"    建议：{finding.suggestion}")
            else:
                lines.append("  （无问题）")

        # 添加迭代结果信息
        lines.append("\n【迭代统计】")
        for i, ir in enumerate(iteration_results):
            lines.append(f"  第{i+1}轮 [{ir['round']}]: 发现 {ir['findings_count']} 个问题，修复 {ir['fixes_applied']} 个")
            # 草稿快照对比：展示修复前后的字数变化
            snapshot = ir.get("draft_snapshot", "")
            if snapshot and self.draft:
                lines.append(f"    📝 草稿变化：{len(snapshot)}字 → 修复后逐轮迭代")
            if ir.get("llm_review"):
                llm_data = ir["llm_review"]
                if "raw_response" in llm_data:
                    parsed = llm_data.get("parsed_findings", [])
                    lines.append(f"    🤖 AI深度审查: 发现 {len(parsed)} 个问题")
                    # 展示AI审查的具体发现摘要（前2条）
                    for pf in parsed[:2]:
                        issue_preview = pf.get("issue", "")[:60]
                        lines.append(f"       • {pf.get('severity', '')}: {issue_preview}")
                elif "error" in llm_data:
                    lines.append(f"    ⚠️ AI审查异常: {llm_data['error'][:80]}")

        # AI思考链摘要（教学价值：让用户看到AI审查的推理过程）
        llm_reasonings = self.llm_client._llm_reasonings
        if llm_reasonings:
            lines.append(f"\n【AI审查思考摘要】（共{len(llm_reasonings)}条，用于理解审查逻辑）")
            for i, r in enumerate(llm_reasonings[-3:], 1):  # 最近3条
                reasoning_preview = r.get("reasoning", "")[:150].replace("\n", " ")
                lines.append(f"  思考{i}: {reasoning_preview}...")

        # 添加协调统计
        coordination = self.coordinator.get_coordination_report()
        lines.append(f"\n【协同统计】")
        lines.append(f"  消息总数: {coordination['communication_stats']['total_messages']}")
        lines.append(f"  协商次数: {coordination['consultations']}")
        lines.append(f"  辩论次数: {coordination['debates']}")
        lines.append(f"  主动预警: {coordination['proactive_alerts']}")

        return "\n".join(lines)

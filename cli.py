"""
CLI 入口 — 命令行交互界面（V3.0 人性化版）

设计理念：
- 公文写作是压力很大的事，用户需要被理解和支持
- 全程温和引导，像一位耐心的导师在陪伴你
- 答得好有鼓励，答不上来有理解
- 让每次交互都有"陪伴感"
"""

import sys
import os
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.questionnaire.questionnaire import Questionnaire
from src.core.orchestrator import Orchestrator
from src.core.writing_mode import WritingMode
from src.core.personalized_db import PersonalizedDB, ProjectStatus
from src.core.agent_coordinator import AgentCoordinator, AgentRole


class CLI:
    def __init__(self):
        self.questionnaire = Questionnaire()
        self.orchestrator = Orchestrator()
        self.pdb = PersonalizedDB()
        self.coordinator = AgentCoordinator()

        self._welcome_shown = False
        self._user_name = ""
        self._answers_given = 0

    # ═══ 人性化问候与引导 ═══

    def welcome(self):
        """温暖的欢迎语"""
        print("\n" + "=" * 60)
        print("  你好！欢迎来到公文写作助手")
        print("=" * 60)
        print()
        print("  我是你的写作伙伴，会一步步引导你完成公文写作。")
        print("  别担心，不着急，我们慢慢来。")
        print()
        print("  在开始之前，想认识一下你：")
        self._user_name = self._ask("  怎么称呼你呢？（直接回车也可以）").strip()
        if not self._user_name:
            self._user_name = "朋友"
            print(f"\n  好的，{self._user_name}！那我们开始吧~")
        else:
            print(f"\n  你好，{self._user_name}！很高兴认识你。")

        print("  接下来我会问你几个问题，帮你理清写作思路。")
        print("  有些问题可能不太好回答，没关系，慢慢想就好。")
        print()
        print("  准备好了吗？我们开始吧！")
        print("-" * 60)
        print()

    def _warm_encouragement(self, answer: str, question_type: str) -> str:
        """根据回答质量给予正向反馈"""
        if len(answer) > 50:
            encouragements = [
                "写得真好！你的思路很清晰，这一步做得很棒。",
                "这个想法很好！能想得这么具体，后面写起来会很顺利。",
                "说得很清楚！有你在前面把方向定好，后面的写作就轻松多了。",
                "很好！这个角度很有价值，继续保持~",
                "答得很详细！看得出来你认真思考过了，非常好。",
            ]
            return encouragements[self._answers_given % len(encouragements)]
        elif len(answer) > 10:
            encouragements = [
                "好的，方向基本清楚了。后面如果有更多细节可以随时补充。",
                "明白了，先记下来。后面写作的时候我们再细化。",
                "好的，这个方向可以。后面有需要补充的随时说。",
            ]
            return encouragements[self._answers_given % len(encouragements)]
        else:
            encouragements = [
                "没关系，这个问题确实不太好想。后面我们可以在写作时一起完善。",
                "没事，先不着急。后面根据框架再补充也可以。",
                "理解，有些问题确实需要边写边想。我们继续下一步~",
            ]
            return encouragements[self._answers_given % len(encouragements)]

    def _warm_progress(self, current: int, total: int, phase: str) -> str:
        """温暖的进度提示"""
        pct = int(current / total * 100) if total > 0 else 0
        filled = int(pct / 10)
        bar = "[" + "=" * filled + "." * (10 - filled) + "]"
        messages = {
            0: "我们刚刚开始，慢慢来就好~",
            25: "进展不错！继续加油~",
            50: "已经完成一半了！做得很好~",
            75: "快了快了！就差最后几步~",
            90: "马上就要完成了！坚持一下~",
            100: "全部完成！太棒了！",
        }
        milestone = max(m for m in messages if pct >= m)
        return f"  进度 {bar} {pct}% ({current}/{total}) {phase}\n  {messages[milestone]}"

    def _ask(self, prompt: str) -> str:
        """统一输入接口，带温暖的前缀"""
        return input(f"{prompt}\n  > ")

    # ═══ 路由阶段 ═══

    def routing_loop(self):
        """路由阶段循环"""
        while True:
            q = self.questionnaire.get_routing_question()
            if q is None:
                break

            print(f"{'='*60}")
            print(f"  第 {q['step']} 步：确定写作类型")
            print(f"{'='*60}")
            print()
            print(f"  {q['question']}")
            print()
            print(f"  为什么问这个：{q['why_ask']}")
            print()

            for opt in q["options"]:
                print(f"  [{opt['index']}] {opt['label']}")
                if opt.get("description"):
                    print(f"      {opt['description']}")

            print()
            choice = self._ask(f"  请选择（输入编号 0-{len(q['options'])-1}）")
            try:
                choice_idx = int(choice)
                result = self.questionnaire.submit_routing_choice(choice_idx)
                if result["phase"] == "routing_complete":
                    print()
                    print("-" * 60)
                    print(f"  已为你确定写作模式：{result['mode_name']}")
                    print(f"  路径：{result['path']}")
                    print(f"  {result['mode_description'][:100]}...")
                    print("-" * 60)
                    print()
                    print("  很好！写作类型确定了，接下来我问几个具体问题，")
                    print("  帮你理清这篇文章的写作思路。")
                    print()
                    return
            except (ValueError, IndexError):
                print()
                print("  输入有误，请重新输入~ 别担心，慢慢来。")
                print()

    # ═══ 模式专属问题阶段 ═══

    def mode_questions_loop(self):
        """模式专属问题循环（支持回退/跳过/上下文感知）"""
        while True:
            q = self.questionnaire.get_current_mode_question()
            if q is None:
                break

            current, total, phase = self.questionnaire.get_progress()
            progress = self._warm_progress(current, total, phase)
            print(progress)
            print()

            # 上下文感知：展示已填信息
            filled = self.questionnaire.get_filled_summary()
            if filled and current > 0:
                print(filled)
                print()

            print(f"{'='*60}")
            print(f"  第 {q['index']}/{q['total']} 个问题")
            print(f"{'='*60}")
            print()
            print(f"  {q['question']}")
            print()
            print(f"  为什么问这个：{q['why_ask']}")
            if q.get("hint"):
                print(f"\n  提示：{q['hint']}")
            print()
            print("  [输入答案后回车 | back 回退 | skip 跳过 | finish 完成]")
            print()

            answer = self._ask("  你的回答").strip()

            if answer.lower() == "back":
                prev = self.questionnaire.go_back()
                if prev:
                    print(f"\n  已回退到第 {prev['index']} 题")
                    print(f"  上一题你的回答：{prev['previous_answer'][:50]}...")
                    print("  可以重新回答，或输入 skip 跳过\n")
                else:
                    print("\n  已经是最前面了，不能回退。\n")
                continue

            if answer.lower() == "skip":
                has_next = self.questionnaire.skip_current()
                print("\n  已跳过，后面可以随时补充。\n")
                if not has_next:
                    break
                continue

            if answer.lower() == "finish":
                print("\n  好的，我们提前完成问卷！\n")
                break

            if not answer:
                print("\n  输入为空，已跳过。\n")
                has_next = self.questionnaire.skip_current()
                if not has_next:
                    break
                continue

            self._answers_given += 1
            has_next = self.questionnaire.submit_mode_answer(answer)

            if answer and len(answer) > 10:
                print()
                print(f"  {self._warm_encouragement(answer, q['id'])}")
                print()

            teaching = self.questionnaire.get_teaching_note()
            if teaching and len(answer) > 10:
                print(f"  {teaching}")
                print()

            if not has_next:
                break

        # 显示跳过的题目
        skipped = self.questionnaire._skipped_questions
        if skipped:
            print("-" * 60)
            print(f"  跳过了 {len(skipped)} 个问题：{', '.join(skipped)}")
            print("  生成时会自动补充，你也可以稍后手动修改。")
            print("-" * 60)
            print()

    # ═══ 生成与输出 ═══

    def generate(self):
        """生成文章并输出"""
        brief = self.questionnaire.finish()

        print()
        print("=" * 60)
        print(f"  {self._user_name}，你的写作思路已经很清晰了！")
        print("=" * 60)
        print()
        print(self.questionnaire.generate_brief_summary())

        print()
        print("  现在，我正在根据你的思路起草文章...")
        print("  这个过程需要一点时间，请等一下~")
        print()

        output = self.orchestrator.generate()

        print("=" * 60)
        print(f"  初稿完成！{self._user_name}，看看效果吧~")
        print("=" * 60)
        print()
        print(output)

        print()
        print("=" * 60)
        print(f"  谢谢你的信任，{self._user_name}！")
        print("=" * 60)
        print()
        print("  这篇文章已经根据你的思路起草好了。")
        print("  写作是一件不容易的事，你已经做得很棒了。")
        print()
        print("  如果对文章有任何想法或需要调整的地方，")
        print("  随时可以继续告诉我，我会帮你完善。")
        print()
        print("  记住：好文章都是改出来的，初稿只是第一步。")
        print("  你已经走出了最重要的一步。")
        print()

    # ═══ 主循环 ═══

    def run(self):
        try:
            self.welcome()
            self.routing_loop()
            self.mode_questions_loop()
            self.generate()
        except KeyboardInterrupt:
            print("\n\n  没关系，随时可以停下来。")
            print("  下次来的时候，我们继续~")
        except EOFError:
            print("\n\n  输入已结束。感谢你的使用！")
        except Exception as e:
            print(f"\n\n  抱歉，遇到了一些问题：{e}")
            print("  这不是你的错，是我的问题。请重试一下~")


if __name__ == "__main__":
    cli = CLI()
    cli.run()

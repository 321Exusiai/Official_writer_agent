<template>
  <div class="workflow-panel">
    <!-- 路由阶段 -->
    <div v-if="store.state === 'routing' && store.routing" class="animate-enter">
      <h3 class="step-title">场景路由</h3>
      <p class="step-question">{{ store.routing.question }}</p>
      <div class="option-list">
        <button
          v-for="o in store.routing.options"
          :key="o.index"
          class="option-card ios-card"
          @click="answer(o.index)"
        >
          <span class="option-label">{{ o.label }}</span>
          <span v-if="o.description" class="option-desc">{{ o.description }}</span>
        </button>
      </div>
    </div>

    <!-- 问卷阶段 -->
    <div v-else-if="store.state === 'questioning' && store.question" class="animate-enter">
      <h3 class="step-title">需求问卷</h3>
      <div class="step-track" style="margin-bottom: 12px">
        <span class="step-badge step-current">
          <span class="step-num">{{ store.question.index }}</span>{{ store.question.total }} 题
        </span>
      </div>
      <p class="step-question">{{ store.question.question }}</p>
      <p v-if="store.question.why_ask" class="why-ask">💡 {{ store.question.why_ask }}</p>
      <p v-if="store.question.hint" class="hint-text">示例：{{ store.question.hint }}</p>
      <textarea
        class="ios-input answer-input"
        v-model="answerText"
        rows="4"
        placeholder="请输入你的回答…"
        @keydown.ctrl.enter="submitAnswer"
      />
      <div class="actions">
        <Button @click="submitAnswer">提交回答</Button>
      </div>
    </div>

    <!-- 方案确认（HITL-1） -->
    <div v-else-if="store.state === 'waiting_approval' && store.plan" class="animate-enter">
      <h3 class="step-title">写作方案</h3>
      <GlassCard>
        <div class="plan-grid">
          <div class="plan-item"><span class="plan-k">写作模式</span><span class="plan-v">{{ modeName }}</span></div>
          <div class="plan-item"><span class="plan-k">文种</span><span class="plan-v">{{ store.plan.doc_type_name }}</span></div>
          <div class="plan-item"><span class="plan-k">风格</span><span class="plan-v">{{ store.plan.style_name }}</span></div>
          <div class="plan-item"><span class="plan-k">篇幅</span><span class="plan-v">{{ store.plan.estimated_length }}</span></div>
        </div>
        <p v-if="store.plan.style_match === false" class="warn-text">⚠️ 风格与文种不匹配，建议调整</p>
      </GlassCard>
      <div class="actions">
        <Button @click="confirm">确认方案，开始写作</Button>
      </div>
    </div>

    <!-- 写作/审查 -->
    <div v-else-if="store.state === 'reviewing'" class="animate-enter">
      <h3 class="step-title">文稿生成</h3>
      <GlassCard>
        <pre class="draft-text">{{ draftContent }}</pre>
      </GlassCard>
      <div class="actions">
        <Button @click="runReview">对文稿执行智能审查</Button>
      </div>
    </div>

    <!-- 审查结果 -->
    <div v-else-if="store.state === 'reviewed' && store.review" class="animate-enter">
      <h3 class="step-title">审查结果</h3>
      <GlassCard>
        <div class="score-row">
          <span class="score" :class="{ low: store.review.score < 70 }">{{ store.review.score }}</span>
          <span class="score-label">分 · {{ store.review.passed ? '通过' : '未通过' }}</span>
          <span class="badge" :class="store.review.mode === 'llm' ? 'badge-llm' : 'badge-rule'">{{ store.review.mode === 'llm' ? 'LLM' : '规则模式' }}</span>
        </div>
        <div v-if="store.review.findings && store.review.findings.length" class="findings">
          <div v-for="(f, i) in store.review.findings" :key="i" class="finding">
            <span class="sev" :class="'sev-' + f.severity">{{ sevText(f.severity) }}</span>
            <span class="issue">{{ f.issue }}</span>
            <span class="sugg">{{ f.suggestion }}</span>
          </div>
        </div>
        <div v-else class="hint-text">未发现问题</div>
      </GlassCard>
      <div class="actions">
        <Button @click="finalize">确认无误，完成交付</Button>
      </div>
    </div>

    <!-- 交付 -->
    <div v-else-if="store.state === 'completed'" class="animate-enter">
      <h3 class="step-title">交付完成 🎉</h3>
      <GlassCard>
        <div v-if="versions.length" class="multi-doc">
          <h4>一文多体版本</h4>
          <div v-for="v in versions" :key="v.doc_type" class="version">
            <span class="version-name">{{ v.doc_type_name }}</span>
            <span class="version-count">{{ v.word_count }} 字</span>
          </div>
        </div>
      </GlassCard>
    </div>

    <div v-else class="empty-state">
      <div style="font-size: 40px">🚀</div>
      <div>点击「开始写作」启动工作流</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useWorkflowStore } from '../../stores/workflow'
import { useProjectStore } from '../../stores/project'
import { api } from '../../api/client'
import Button from '../ui/Button.vue'
import GlassCard from '../ui/GlassCard.vue'

const store = useWorkflowStore()
const projectStore = useProjectStore()
const answerText = ref('')

const pid = computed(() => projectStore.active && projectStore.active.id)
const draftContent = computed(() => {
  const p = projectStore.active
  return (p && p.draft) || '（草稿生成中…）'
})
const versions = computed(() => store.versions)
const modeName = computed(() => (store.plan ? store.plan.writing_mode : ''))

function answer(index) { store.answer(pid.value, String(index)) }
function submitAnswer() {
  if (!answerText.value.trim()) return
  store.answer(pid.value, answerText.value.trim())
  answerText.value = ''
}
function confirm() { store.confirm(pid.value) }
function runReview() { store.review(pid.value) }
async function finalize() {
  await store.finalize(pid.value)
  // 刷新项目草稿
  if (pid.value) projectStore.active = await api.get(`/projects/${pid.value}`)
}
function sevText(s) {
  return { critical: '严重', major: '重要', minor: '轻微', suggestion: '建议' }[s] || s
}
</script>

<style scoped>
.workflow-panel { display: flex; flex-direction: column; gap: 16px; }
.step-title { font-size: 18px; font-weight: 700; }
.step-question { font-size: 15px; font-weight: 600; margin: 8px 0; }
.why-ask { color: var(--color-accent); font-size: 13px; margin: 6px 0; }
.hint-text { color: var(--color-ink-muted); font-size: 12px; margin: 4px 0; }
.warn-text { color: var(--color-danger); font-size: 13px; margin-top: 8px; }
.option-list { display: flex; flex-direction: column; gap: 8px; }
.option-card {
  display: flex; flex-direction: column; gap: 4px; cursor: pointer; text-align: left;
  padding: 14px 16px; color: var(--color-ink);
}
.option-card:hover { border-color: var(--color-accent); }
.option-label { font-weight: 600; font-size: 14px; }
.option-desc { color: var(--color-ink-muted); font-size: 12px; }
.answer-input { resize: vertical; min-height: 80px; }
.actions { display: flex; gap: 8px; margin-top: 8px; }
.plan-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.plan-item { display: flex; flex-direction: column; gap: 2px; }
.plan-k { color: var(--color-ink-muted); font-size: 12px; }
.plan-v { font-weight: 600; font-size: 14px; }
.draft-text { white-space: pre-wrap; font-family: var(--font-ui); font-size: 13px; line-height: 1.7; color: var(--color-ink-body); }
.score-row { display: flex; align-items: center; gap: 10px; }
.score { font-size: 32px; font-weight: 700; color: var(--color-accent); }
.score.low { color: var(--color-danger); }
.score-label { color: var(--color-ink-muted); font-size: 13px; }
.findings { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.finding { padding: 10px; border-radius: 12px; background: var(--glass-highlight); border: 1px solid var(--glass-border); }
.sev { display: inline-block; font-size: 11px; font-weight: 700; padding: 1px 6px; border-radius: 4px; margin-right: 6px; }
.sev-critical { background: rgba(255, 107, 94, 0.2); color: var(--color-danger); }
.sev-major { background: rgba(255, 180, 90, 0.2); color: #FFB45A; }
.sev-minor { background: rgba(167, 139, 250, 0.2); color: #A78BFA; }
.sev-suggestion { background: rgba(140, 160, 180, 0.2); color: var(--color-ink-muted); }
.issue { font-weight: 600; font-size: 13px; }
.sugg { display: block; color: var(--color-ink-muted); font-size: 12px; margin-top: 4px; }
.multi-doc h4 { font-size: 14px; margin-bottom: 8px; }
.version { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--glass-border); }
.version-name { font-weight: 600; font-size: 13px; }
.version-count { color: var(--color-ink-muted); font-size: 12px; }
</style>

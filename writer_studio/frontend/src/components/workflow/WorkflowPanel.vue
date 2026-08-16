<template>
  <div class="workflow-panel">
    <!-- 路由阶段 -->
    <div v-if="cur.state === 'routing' && cur.routing" class="animate-enter">
      <h3 class="step-title">场景路由</h3>
      <p class="step-question">{{ cur.routing.question }}</p>
      <div class="option-list">
        <button
          v-for="o in cur.routing.options"
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
    <div v-else-if="cur.state === 'questioning' && cur.question" class="animate-enter">
      <h3 class="step-title">需求问卷</h3>
      <div class="step-track" style="margin-bottom: 12px">
        <span class="step-badge step-current">
          <span class="step-num">{{ cur.question.index }}</span>{{ cur.question.total }} 题
        </span>
      </div>
      <p class="step-question">{{ cur.question.question }}</p>
      <p v-if="cur.question.why_ask" class="why-ask">💡 {{ cur.question.why_ask }}</p>
      <p v-if="cur.question.hint" class="hint-text">示例：{{ cur.question.hint }}</p>
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
    <div v-else-if="cur.state === 'waiting_approval' && cur.plan" class="animate-enter">
      <h3 class="step-title">写作方案</h3>
      <GlassCard>
        <div class="plan-grid">
          <div class="plan-item"><span class="plan-k">写作模式</span><span class="plan-v">{{ modeName }}</span></div>
          <div class="plan-item"><span class="plan-k">文种</span><span class="plan-v">{{ cur.plan.doc_type_name }}</span></div>
          <div class="plan-item"><span class="plan-k">风格</span><span class="plan-v">{{ cur.plan.style_name }}</span></div>
          <div class="plan-item"><span class="plan-k">篇幅</span><span class="plan-v">{{ cur.plan.estimated_length }}</span></div>
        </div>
        <p v-if="cur.plan.style_match === false" class="warn-text">⚠️ 风格与文种不匹配，建议调整</p>
      </GlassCard>
      <div class="actions">
        <Button @click="confirm">确认方案，开始写作</Button>
      </div>
    </div>

    <!-- 写作/审查 -->
    <div v-else-if="cur.state === 'reviewing'" class="animate-enter">
      <h3 class="step-title">文稿生成</h3>
      <GlassCard>
        <pre class="draft-text">{{ draftContent }}</pre>
      </GlassCard>
      <div class="actions">
        <Button @click="runReview">对文稿执行智能审查</Button>
      </div>
    </div>

    <!-- 审查结果 -->
    <div v-else-if="cur.state === 'reviewed' && store.review" class="animate-enter">
      <h3 class="step-title">审查结果</h3>
      <GlassCard>
        <div class="score-row">
          <span class="score" :class="{ low: cur.review.score < 70 }">{{ cur.review.score }}</span>
          <span class="score-label">分 · {{ cur.review.passed ? '通过' : '未通过' }}</span>
          <span class="badge" :class="cur.review.mode === 'llm' ? 'badge-llm' : 'badge-rule'">{{ cur.review.mode === 'llm' ? 'LLM' : '规则模式' }}</span>
        </div>
        <div v-if="cur.review.findings && cur.review.findings.length" class="heatmap">
          <div v-for="s in severities" :key="s.key" class="heat-row">
            <span class="heat-label">{{ s.label }}</span>
            <div class="heat-bar">
              <div class="heat-fill" :class="'fill-' + s.key" :style="{ width: heatPct(s.key) + '%' }" />
            </div>
            <span class="heat-count">{{ heatCount(s.key) }}</span>
          </div>
        </div>
        <div v-if="cur.review.findings && cur.review.findings.length" class="findings">
          <div v-for="(f, i) in cur.review.findings" :key="i" class="finding">
            <span class="sev" :class="'sev-' + f.severity">{{ sevText(f.severity) }}</span>
            <span class="issue">{{ f.issue }}</span>
            <span class="sugg">{{ f.suggestion }}</span>
          </div>
        </div>
        <div v-else class="hint-text">未发现问题</div>
      </GlassCard>
      <div class="actions">
        <Button variant="secondary" @click="toggleEdit">{{ editing ? '收起编辑' : '编辑草稿 (HITL)' }}</Button>
        <Button @click="finalize">确认无误，完成交付</Button>
      </div>
      <GlassCard v-if="editing">
        <p class="hint-text">在下方直接修改草稿，保存后可重新审查。</p>
        <textarea class="ios-input draft-edit" v-model="draftEdit" rows="10" />
        <div class="actions">
          <Button variant="secondary" @click="saveDraft">保存修改</Button>
          <Button @click="reReview">保存并重新审查</Button>
        </div>
      </GlassCard>
    </div>

    <!-- 交付 -->
    <div v-else-if="cur.state === 'completed'" class="animate-enter">
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
const cur = computed(() => store.cur)
const answerText = ref('')
const editing = ref(false)
const draftEdit = ref('')

const severities = [
  { key: 'critical', label: '严重' },
  { key: 'major', label: '重要' },
  { key: 'minor', label: '轻微' },
  { key: 'suggestion', label: '建议' },
]

const pid = computed(() => projectStore.active && projectStore.active.id)
const draftContent = computed(() => {
  const p = projectStore.active
  return (p && p.draft) || '（草稿生成中…）'
})
const versions = computed(() => cur.value.versions)
const modeName = computed(() => (cur.value.plan ? cur.value.plan.writing_mode : ''))

function findings() { return (cur.value.review && cur.value.review.findings) || [] }
function heatCount(key) { return findings().filter((f) => f.severity === key).length }
function heatPct(key) {
  const total = findings().length || 1
  return Math.round((heatCount(key) / total) * 100)
}

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
  if (pid.value) projectStore.active = await api.get(`/projects/${pid.value}`)
}
function toggleEdit() {
  editing.value = !editing.value
  if (editing.value) draftEdit.value = draftContent.value
}
async function saveDraft() {
  if (pid.value) {
    await api.patch(`/projects/${pid.value}/draft`, { draft: draftEdit.value })
    projectStore.active = await api.get(`/projects/${pid.value}`)
    editing.value = false
  }
}
async function reReview() {
  if (pid.value) {
    await api.patch(`/projects/${pid.value}/draft`, { draft: draftEdit.value })
    projectStore.active = await api.get(`/projects/${pid.value}`)
    editing.value = false
    store.review(pid.value)
  }
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
.heatmap { margin-top: 12px; display: flex; flex-direction: column; gap: 6px; }
.heat-row { display: flex; align-items: center; gap: 8px; }
.heat-label { font-size: 11px; color: var(--color-ink-muted); width: 30px; flex-shrink: 0; }
.heat-bar { flex: 1; height: 8px; border-radius: 4px; background: var(--glass-highlight); overflow: hidden; }
.heat-fill { height: 100%; border-radius: 4px; transition: width 0.4s var(--ease-out-expo); }
.fill-critical { background: var(--color-danger); }
.fill-major { background: #FFB45A; }
.fill-minor { background: #A78BFA; }
.fill-suggestion { background: var(--color-ink-muted); }
.heat-count { font-size: 11px; color: var(--color-ink-body); width: 20px; text-align: right; }
.draft-edit { resize: vertical; min-height: 160px; margin-bottom: 4px; }
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

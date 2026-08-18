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
      <div v-if="cur.question.why_ask" class="guide-box">
        <span class="guide-tag">写作说明</span>
        <p class="why-ask">{{ cur.question.why_ask }}</p>
      </div>
      <p v-if="cur.question.hint" class="hint-text">参考：{{ cur.question.hint }}</p>
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
      <div v-if="cur.answers && cur.answers.length" class="answers-review">
        <button class="structure-toggle" @click="showAnswers = !showAnswers">
          {{ showAnswers ? '收起已答回顾 ▾' : `已答 ${cur.answers.length} 题 · 展开回顾 ▸` }}
        </button>
        <div v-if="showAnswers" class="answers-list">
          <div v-for="(a, i) in cur.answers" :key="i" class="answer-item">
            <span class="aq">{{ i + 1 }}. {{ a.question.slice(0, 26) }}</span>
            <span class="aa">{{ a.answer.slice(0, 60) }}</span>
          </div>
        </div>
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
        <div class="adjust-box">
          <div class="adjust-row">
            <label class="adjust-label">文种</label>
            <select class="ios-input" v-model="selDocType" @change="onDocTypeChange">
              <option v-for="d in doctypeOptions" :key="d.id" :value="d.id">{{ d.name_cn }}</option>
            </select>
            <label class="adjust-label">风格</label>
            <select class="ios-input" v-model="selStyle" @change="onStyleChange">
              <option v-for="s in styleOptions" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </div>
        </div>
        <div v-if="cur.plan.structure_detail" class="structure-box">
          <button class="structure-toggle" @click="showStructure = !showStructure">
            {{ showStructure ? '收起结构大纲 ▾' : '展开结构大纲 ▸' }}
          </button>
          <pre v-if="showStructure" class="structure-detail">{{ cur.plan.structure_detail }}</pre>
        </div>
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
    <div v-else-if="cur.state === 'reviewed' && cur.review" class="animate-enter">
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
        <div v-if="cur.review.dimension_scores && cur.review.dimension_scores.length" class="dim-scores">
          <div class="dim-title">逐维度得分</div>
          <div v-for="d in cur.review.dimension_scores" :key="d.name" class="dim-row">
            <span class="dim-name">{{ d.name }}</span>
            <div class="dim-bar">
              <div class="dim-fill" :class="{ low: d.score < 70 }" :style="{ width: d.score + '%' }" />
            </div>
            <span class="dim-score" :class="{ low: d.score < 70 }">{{ d.score }}</span>
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
      <MultiDocCompare v-if="versions.length >= 2" :versions="versions" />
      <div class="actions">
        <Button variant="secondary" @click="exportProject">导出项目 JSON</Button>
      </div>
    </div>

    <div v-else class="empty-state">
      <div style="font-size: 40px">🚀</div>
      <div>点击「开始写作」启动工作流</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useWorkflowStore } from '../../stores/workflow'
import { useProjectStore } from '../../stores/project'
import { api } from '../../api/client'
import Button from '../ui/Button.vue'
import GlassCard from '../ui/GlassCard.vue'
import MultiDocCompare from './MultiDocCompare.vue'

const store = useWorkflowStore()
const projectStore = useProjectStore()
const cur = computed(() => store.cur)
const answerText = ref('')
const editing = ref(false)
const draftEdit = ref('')
const showStructure = ref(false)
const showAnswers = ref(false)

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
const doctypeOptions = ref([])
const styleOptions = ref([])
const selDocType = ref('')
const selStyle = ref('')

function findings() { return (cur.value.review && cur.value.review.findings) || [] }
function heatCount(key) { return findings().filter((f) => f.severity === key).length }
function heatPct(key) {
  const total = findings().length || 1
  return Math.round((heatCount(key) / total) * 100)
}

async function loadPlanOptions() {
  try {
    const mode = cur.value.plan && cur.value.plan.writing_mode
    doctypeOptions.value = await api.get(`/knowledge/doctypes?mode=${mode}`)
    styleOptions.value = await api.get(`/knowledge/styles?mode=${mode}`)
    if (cur.value.plan) {
      selDocType.value = cur.value.plan.doc_type
      selStyle.value = cur.value.plan.media_style
    }
  } catch { /* ignore */ }
}

async function applyPlanChange() {
  if (!pid.value || !selDocType.value || !selStyle.value) return
  const plan = await api.post(`/projects/${pid.value}/workflow/plan`, {
    doc_type: selDocType.value, media_style: selStyle.value,
  })
  store.items[pid.value].plan = plan
}

function onDocTypeChange() { applyPlanChange() }
function onStyleChange() { applyPlanChange() }

watch(() => cur.value.state, (s) => {
  if (s === 'waiting_approval') loadPlanOptions()
})

function answer(index) { store.answer(pid.value, String(index)) }
function submitAnswer() {
  if (!answerText.value.trim()) return
  store.answer(pid.value, answerText.value.trim())
  answerText.value = ''
}

async function exportProject() {
  if (!pid.value) return
  const data = await api.get(`/projects/${pid.value}/export`)
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `${(projectStore.active && projectStore.active.name) || 'project'}.json`
  a.click()
  URL.revokeObjectURL(a.href)
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
.guide-box { background: var(--glass-highlight); border: 1px solid var(--glass-border); border-radius: 12px; padding: 10px 12px; margin: 8px 0; }
.guide-tag { display: inline-block; font-size: 11px; color: var(--color-accent); border: 1px solid var(--color-accent-focus); border-radius: 6px; padding: 1px 8px; margin-bottom: 4px; }
.why-ask { color: var(--color-ink-body); font-size: 13px; line-height: 1.7; margin: 0; }
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
.adjust-box { margin-top: 12px; border-top: 1px solid var(--glass-border); padding-top: 10px; }
.adjust-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.adjust-label { font-size: 12px; color: var(--color-ink-muted); }
.adjust-row select { flex: 1; min-width: 100px; }
.structure-box { margin-top: 12px; border-top: 1px solid var(--glass-border); padding-top: 10px; }
.structure-toggle { background: none; border: none; color: var(--color-accent); font-size: 12px; font-weight: 600; cursor: pointer; font-family: var(--font-ui); }
.structure-detail { white-space: pre-wrap; font-family: var(--font-ui); font-size: 12px; line-height: 1.7; color: var(--color-ink-body); background: rgba(0,0,0,0.15); padding: 10px; border-radius: 10px; margin-top: 8px; }
.answers-review { margin-top: 12px; border-top: 1px solid var(--glass-border); padding-top: 10px; }
.answers-list { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
.answer-item { display: flex; flex-direction: column; gap: 2px; padding: 8px 10px; border-radius: 10px; background: var(--glass-highlight); }
.aq { font-size: 12px; font-weight: 600; color: var(--color-ink-body); }
.aa { font-size: 12px; color: var(--color-ink-muted); }
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
.dim-scores { margin-top: 12px; display: flex; flex-direction: column; gap: 6px; }
.dim-title { font-size: 12px; font-weight: 700; color: var(--color-ink-body); margin-bottom: 2px; }
.dim-row { display: flex; align-items: center; gap: 8px; }
.dim-name { font-size: 12px; color: var(--color-ink-muted); width: 52px; flex-shrink: 0; }
.dim-bar { flex: 1; height: 8px; border-radius: 4px; background: var(--glass-highlight); overflow: hidden; }
.dim-fill { height: 100%; border-radius: 4px; background: var(--color-accent); transition: width 0.4s var(--ease-out-expo); }
.dim-fill.low { background: var(--color-danger); }
.dim-score { font-size: 12px; font-weight: 700; color: var(--color-accent); width: 34px; text-align: right; }
.dim-score.low { color: var(--color-danger); }
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

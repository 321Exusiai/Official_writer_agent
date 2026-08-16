<template>
  <div class="process-panel">
    <div v-if="projectName" class="proj-name">{{ projectName }}</div>

    <!-- 步骤导航（可点击回退到已完成步骤） -->
    <div class="step-nav">
      <button
        v-for="s in steps"
        :key="s.key"
        class="step-nav-item"
        :class="{ on: currentStepIdx === s.idx, done: currentStepIdx > s.idx, clickable: currentStepIdx > s.idx }"
        :disabled="currentStepIdx <= s.idx || s.key === 'completed'"
        :title="currentStepIdx > s.idx && s.key !== 'completed' ? `回退到「${s.label}」` : ''"
        @click="rollback(s.key)"
      >
        <span class="sn-num">{{ s.idx + 1 }}</span>
        <span class="sn-label">{{ s.label }}</span>
      </button>
    </div>

    <!-- 事件时间线（只读细节） -->
    <div v-if="!events.length" class="empty-state">
      <div style="font-size: 28px">📡</div>
      <div>选择项目后开始写作，过程将在这里实时呈现</div>
    </div>
    <div v-else class="timeline">
      <div v-for="ev in events" :key="ev.seq" class="timeline-item">
        <div class="timeline-dot" />
        <div class="timeline-body">
          <div class="timeline-head">
            <span class="timeline-step">{{ stepLabel(ev.step) }}</span>
            <span v-if="ev.payload && ev.payload.mode" class="badge" :class="ev.payload.mode === 'llm' ? 'badge-llm' : 'badge-rule'">
              {{ ev.payload.mode === 'llm' ? 'LLM' : '规则' }}
            </span>
          </div>
          <div class="timeline-detail">{{ detail(ev) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useWorkflowStore } from '../../stores/workflow'
import { useProjectStore } from '../../stores/project'

const store = useWorkflowStore()
const projectStore = useProjectStore()

const events = computed(() => store.cur.events)
const projectName = computed(() => (projectStore.active ? projectStore.active.name : ''))
const pid = computed(() => projectStore.active && projectStore.active.id)

const steps = [
  { key: 'routing', label: '路由', idx: 0 },
  { key: 'questioning', label: '问卷', idx: 1 },
  { key: 'planning', label: '方案', idx: 2 },
  { key: 'writing', label: '写作', idx: 3 },
  { key: 'reviewing', label: '审查', idx: 4 },
  { key: 'completed', label: '交付', idx: 5 },
]

const STATE_IDX = { idle: -1, routing: 0, questioning: 1, waiting_approval: 2, reviewing: 3, reviewed: 4, completed: 5 }
const currentStepIdx = computed(() => STATE_IDX[store.cur.state] ?? -1)

function rollback(step) {
  if (!pid.value || step === 'completed') return
  if (currentStepIdx.value <= steps.find((s) => s.key === step).idx) return
  store.rollback(pid.value, step)
}

const STEP_LABELS = {
  routing: '场景路由',
  questioning: '需求问卷',
  planning: '写作方案',
  writing: '文稿生成',
  reviewing: '智能审查',
  finalize: '交付',
  error: '出错',
}
function stepLabel(step) { return STEP_LABELS[step] || step }

function detail(ev) {
  const p = ev.payload || {}
  switch (ev.type) {
    case 'routing': return p.question || ''
    case 'routing_complete': return `模式：${p.mode || ''}`
    case 'question': return `Q${p.index || ''}：${(p.question || '').slice(0, 30)}`
    case 'plan': return `文种 ${p.doc_type_name || ''} · 风格 ${p.style_name || ''}`
    case 'plan_confirmed': return '方案已确认'
    case 'write_start': return '开始起草'
    case 'retrieval': return `检索到 术语${(p.terms || []).length} · 政策${(p.policies || []).length} · 范文${(p.exemplars || []).length}`
    case 'consult': return `【${roleName(p.role)}】${(p.suggestions || []).slice(0, 1).join('；')}`
    case 'decision': return (p.decision || '').slice(0, 40)
    case 'draft_ready': return `初稿 ${p.word_count} 字`
    case 'multi_doc': return `生成 ${(p.versions || []).length} 个版本`
    case 'review_start': return '开始审查'
    case 'review_done': return `得分 ${p.score} · ${(p.findings || []).length} 个问题`
    case 'rollback': return `已回退到「${STEP_LABELS[p.to] || p.to}」`
    case 'finalize': return '交付完成'
    case 'error': return p.message || ''
    default: return ev.type
  }
}

function roleName(role) {
  return { writer: '主笔', reviewer: '审稿人', style: '风格', doctype: '文种', knowledge: '知识库', profile: '画像' }[role] || role
}
</script>

<style scoped>
.process-panel { display: flex; flex-direction: column; gap: 14px; }
.proj-name { font-size: 14px; font-weight: 700; }
.step-nav { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
.step-nav-item {
  display: flex; align-items: center; gap: 6px;
  border: 1px solid var(--glass-border); background: none;
  color: var(--color-ink-muted); padding: 7px 8px; border-radius: 10px;
  font-size: 12px; font-weight: 600; cursor: default; font-family: var(--font-ui);
  transition: all 0.2s;
}
.step-nav-item.clickable { cursor: pointer; }
.step-nav-item.clickable:hover { border-color: var(--color-accent); color: var(--color-ink-body); }
.step-nav-item.done { color: var(--color-ink-body); }
.step-nav-item.on { border-color: var(--color-accent); color: var(--color-accent); }
.sn-num {
  width: 18px; height: 18px; border-radius: 50%; flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 11px; background: var(--glass-highlight);
}
.step-nav-item.on .sn-num { background: var(--color-accent); color: #1D1D1F; }
.sn-label { font-size: 11px; }
.timeline { display: flex; flex-direction: column; }
.timeline-item { display: flex; gap: 10px; margin-bottom: 12px; }
.timeline-dot {
  width: 9px; height: 9px; border-radius: 50%;
  background: var(--color-accent); margin-top: 4px; flex-shrink: 0;
  box-shadow: 0 0 8px var(--color-accent);
}
.timeline-body { flex: 1; }
.timeline-head { display: flex; align-items: center; gap: 8px; }
.timeline-step { font-weight: 700; font-size: 13px; }
.timeline-detail { color: var(--color-ink-muted); font-size: 12px; margin-top: 2px; line-height: 1.5; }
</style>

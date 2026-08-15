<template>
  <div class="process-panel">
    <div v-if="!events.length" class="empty-state">
      <div style="font-size: 32px">📡</div>
      <div>决策过程将在这里实时呈现</div>
    </div>
    <div v-else class="timeline">
      <div v-for="ev in events" :key="ev.seq" class="timeline-item">
        <div class="timeline-dot" :class="'dot-' + ev.step" />
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

const store = useWorkflowStore()
const events = computed(() => store.events)

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
    case 'draft_ready': return `初稿 ${p.word_count} 字`
    case 'multi_doc': return `生成 ${(p.versions || []).length} 个版本`
    case 'review_start': return '开始审查'
    case 'review_done': return `得分 ${p.score} · ${(p.findings || []).length} 个问题`
    case 'finalize': return '交付完成'
    case 'error': return p.message || ''
    default: return ev.type
  }
}
</script>

<style scoped>
.process-panel { display: flex; flex-direction: column; }
.timeline { display: flex; flex-direction: column; }
.timeline-item { display: flex; gap: 10px; margin-bottom: 14px; }
.timeline-dot {
  width: 10px; height: 10px; border-radius: 50%;
  background: var(--color-accent);
  margin-top: 4px; flex-shrink: 0;
  box-shadow: 0 0 8px var(--color-accent);
}
.timeline-body { flex: 1; }
.timeline-head { display: flex; align-items: center; gap: 8px; }
.timeline-step { font-weight: 700; font-size: 13px; }
.timeline-detail { color: var(--color-ink-muted); font-size: 12px; margin-top: 2px; line-height: 1.5; }
</style>

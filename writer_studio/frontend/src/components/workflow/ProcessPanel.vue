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

    <!-- 动态自愈六维雷达图（当存在审查维度得分时） -->
    <div v-if="dimensionScores.length >= 3" class="radar-card">
      <div class="radar-title">📊 多维公文质量雷达</div>
      <div class="radar-container">
        <svg class="radar-svg" viewBox="0 0 200 200">
          <!-- 网格多边形 -->
          <polygon v-for="level in [0.25, 0.5, 0.75, 1.0]" :key="level" :points="getGridPoints(level)" class="radar-grid" />
          <!-- 轴线 -->
          <line v-for="(dim, i) in dimensionScores" :key="i" x1="100" y1="100" :x2="getAxisPoint(i)[0]" :y2="getAxisPoint(i)[1]" class="radar-axis" />
          <!-- 得分多边形 -->
          <polygon :points="scorePolygonPoints" class="radar-polygon" />
          <!-- 得分端点 -->
          <circle v-for="(p, i) in scorePoints" :key="i" :cx="p[0]" :cy="p[1]" r="3" class="radar-dot" />
          <!-- 维度文本 -->
          <text v-for="(dim, i) in dimensionScores" :key="'t-' + i" :x="getTextPoint(i)[0]" :y="getTextPoint(i)[1]" class="radar-text">
            {{ dim.name.slice(0, 4) }}
          </text>
        </svg>
      </div>
    </div>

    <!-- 专家决策权威权重微调滑块 -->
    <div v-if="pid" class="weights-card">
      <button class="weights-toggle" @click="showWeights = !showWeights">
        {{ showWeights ? '收起专家决策权重 ▾' : '⚙️ 调节专家决策权重 ▸' }}
      </button>
      <div v-if="showWeights" class="weights-box">
        <div v-for="r in roleSliders" :key="r.key" class="weight-row">
          <span class="w-label">{{ r.name }}</span>
          <input
            type="range"
            min="0.5"
            max="3.0"
            step="0.1"
            v-model.number="weights[r.key]"
            @change="saveWeights"
            class="w-slider"
          />
          <span class="w-val">{{ weights[r.key] || 1.0 }}x</span>
        </div>
      </div>
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
          <!-- 专家思维气泡与交锋细节 -->
          <div v-if="ev.payload && ev.payload.thought_bubbles && ev.payload.thought_bubbles.length" class="thought-bubbles">
            <div v-for="(tb, i) in ev.payload.thought_bubbles" :key="i" class="thought-bubble-card">
              <span class="tb-emoji">{{ tb.emoji }}</span>
              <span class="tb-role">{{ tb.role_name }}</span>
              <span class="tb-text">{{ tb.thought }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useWorkflowStore } from '../../stores/workflow'
import { useProjectStore } from '../../stores/project'

const store = useWorkflowStore()
const projectStore = useProjectStore()

const events = computed(() => store.cur.events)
const projectName = computed(() => (projectStore.active ? projectStore.active.name : ''))
const pid = computed(() => projectStore.active && projectStore.active.id)

const showWeights = ref(false)
const weights = ref({
  doctype: 2.0,
  style: 1.5,
  reviewer: 1.5,
  profile: 1.2,
  writer: 1.0,
  knowledge: 1.0,
})

const roleSliders = [
  { key: 'doctype', name: '🏛️ 文种专家' },
  { key: 'style', name: '🎨 风格专家' },
  { key: 'reviewer', name: '🧐 审稿专家' },
  { key: 'profile', name: '👤 画像教练' },
  { key: 'knowledge', name: '📚 知识专家' },
  { key: 'writer', name: '✍️ 主笔专家' },
]

async function saveWeights() {
  if (!pid.value) return
  await store.setWeights(pid.value, weights.value)
}

// 动态雷达图计算
const dimensionScores = computed(() => {
  return (store.cur.review && store.cur.review.dimension_scores) || []
})

const numDims = computed(() => dimensionScores.value.length || 6)

function getAxisPoint(index) {
  const angle = (Math.PI * 2 / numDims.value) * index - Math.PI / 2
  const r = 70
  return [100 + r * Math.cos(angle), 100 + r * Math.sin(angle)]
}

function getTextPoint(index) {
  const angle = (Math.PI * 2 / numDims.value) * index - Math.PI / 2
  const r = 88
  return [100 + r * Math.cos(angle), 100 + r * Math.sin(angle) + 4]
}

function getGridPoints(level) {
  const pts = []
  for (let i = 0; i < numDims.value; i++) {
    const angle = (Math.PI * 2 / numDims.value) * i - Math.PI / 2
    const r = 70 * level
    pts.push(`${100 + r * Math.cos(angle)},${100 + r * Math.sin(angle)}`)
  }
  return pts.join(' ')
}

const scorePoints = computed(() => {
  return dimensionScores.value.map((d, i) => {
    const angle = (Math.PI * 2 / numDims.value) * i - Math.PI / 2
    const scoreVal = Math.max(0, Math.min(100, d.score || 0))
    const r = (scoreVal / 100) * 70
    return [100 + r * Math.cos(angle), 100 + r * Math.sin(angle)]
  })
})

const scorePolygonPoints = computed(() => {
  return scorePoints.value.map((p) => `${p[0]},${p[1]}`).join(' ')
})

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
    case 'draft_chunk': return `正在流式起草输出（已生成 ${p.total_len || 0} 字）`
    case 'retrieval': return `检索到 术语${(p.terms || []).length} · 政策${(p.policies || []).length} · 范文${(p.exemplars || []).length}`
    case 'consult': return `【${roleName(p.role)}】${(p.suggestions || []).slice(0, 1).join('；')}`
    case 'decision': return (p.decision || '').slice(0, 40)
    case 'draft_ready': return `初稿 ${p.word_count} 字`
    case 'multi_doc': return `生成 ${(p.versions || []).length} 个版本`
    case 'review_start': return '开始审查'
    case 'debate': return `【仲裁共识】${(p.consensus || '').slice(0, 45)}`
    case 'healing_start': return `⚡ 启动自主收敛自愈（目标 ${p.target_score} 分）`
    case 'healing_step': return `第 ${p.round} 轮自愈【${p.issue}】：${p.prev_score}分 ➔ ${p.new_score}分 ${p.rolled_back ? '（退化已回滚）' : ''}`
    case 'healing_rollback': return `⚠️ 修复后评分退化（${p.prev_score} ➔ ${p.new_score}），已自动回滚快照保护`
    case 'healing_done': return `⚡ 自愈收敛完成：最终得分 ${p.final_score} 分（共 ${p.rounds_run || 0} 轮）`
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
  display: flex; align-items: center; gap: 6px; padding: 7px 10px;
  border-radius: 8px; border: 1px solid var(--color-border);
  background: var(--color-surface); color: var(--color-text-muted);
  font-size: 12px; cursor: default;
}
.step-nav-item.on {
  border-color: var(--color-primary); color: var(--color-primary);
  background: color-mix(in srgb, var(--color-primary) 10%, transparent); font-weight: 600;
}
.step-nav-item.done { color: var(--color-text); }
.step-nav-item.clickable { cursor: pointer; }
.step-nav-item.clickable:hover { border-color: var(--color-primary); }
.sn-num {
  width: 18px; height: 18px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 11px; background: var(--color-bg); font-weight: 700;
}
.sn-label { font-size: 11px; }

/* 雷达图 */
.radar-card {
  padding: 10px; border-radius: 12px;
  background: var(--color-surface); border: 1px solid var(--color-border);
}
.radar-title { font-size: 12px; font-weight: 700; color: var(--color-text); margin-bottom: 6px; text-align: center; }
.radar-container { display: flex; justify-content: center; align-items: center; }
.radar-svg { width: 180px; height: 180px; }
.radar-grid { fill: none; stroke: var(--color-border); stroke-dasharray: 2,2; }
.radar-axis { stroke: var(--color-border); stroke-width: 1; }
.radar-polygon {
  fill: color-mix(in srgb, var(--color-primary) 25%, transparent);
  stroke: var(--color-primary); stroke-width: 2;
  transition: all 0.5s ease-out;
}
.radar-dot { fill: var(--color-primary); }
.radar-text { font-size: 9px; fill: var(--color-text-muted); text-anchor: middle; }

/* 权重滑块 */
.weights-card {
  padding: 8px 10px; border-radius: 10px;
  background: var(--color-surface); border: 1px solid var(--color-border);
}
.weights-toggle {
  background: none; border: none; font-size: 11px; font-weight: 600;
  color: var(--color-primary); cursor: pointer; width: 100%; text-align: left; padding: 0;
}
.weights-box { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
.weight-row { display: flex; align-items: center; gap: 8px; font-size: 11px; }
.w-label { width: 80px; color: var(--color-text); }
.w-slider { flex: 1; accent-color: var(--color-primary); }
.w-val { width: 32px; text-align: right; color: var(--color-primary); font-weight: 600; }

.timeline { display: flex; flex-direction: column; gap: 12px; }
.timeline-item { display: flex; gap: 10px; position: relative; }
.timeline-dot {
  width: 8px; height: 8px; border-radius: 50%; background: var(--color-primary);
  margin-top: 5px; flex-shrink: 0;
}
.timeline-body { flex: 1; display: flex; flex-direction: column; gap: 3px; }
.timeline-head { display: flex; align-items: center; justify-content: space-between; }
.timeline-step { font-size: 12px; font-weight: 600; color: var(--color-text); }
.timeline-detail { font-size: 12px; color: var(--color-text-muted); line-height: 1.4; word-break: break-word; }

.thought-bubbles {
  display: flex; flex-direction: column; gap: 4px; margin-top: 6px;
}
.thought-bubble-card {
  display: flex; align-items: flex-start; gap: 6px;
  padding: 5px 8px; border-radius: 6px;
  background: color-mix(in srgb, var(--color-primary) 6%, transparent);
  border: 1px dashed color-mix(in srgb, var(--color-primary) 25%, transparent);
  font-size: 11px; line-height: 1.35;
}
.tb-emoji { font-size: 13px; flex-shrink: 0; }
.tb-role { font-weight: 600; color: var(--color-primary); flex-shrink: 0; }
.tb-text { color: var(--color-text); word-break: break-word; }

.badge { font-size: 10px; padding: 1px 6px; border-radius: 10px; font-weight: 600; }
.badge-llm { background: #e0f2fe; color: #0369a1; }
.badge-rule { background: #f1f5f9; color: #64748b; }
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  min-height: 200px; gap: 10px; color: var(--color-text-muted); font-size: 13px; text-align: center;
}
</style>

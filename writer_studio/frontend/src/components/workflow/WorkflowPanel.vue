<template>
  <div class="workflow-panel">
    <!-- 路由阶段 -->
    <div v-if="(cur.state === 'routing' && cur.routing) || (cur.routing && !cur.draft && !cur.plan && !cur.question)" class="animate-enter">
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
    <div v-else-if="(cur.state === 'questioning' && cur.question) || (cur.question && !cur.draft && !cur.plan)" class="animate-enter">
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
    <div v-else-if="(cur.state === 'waiting_approval' && cur.plan) || (cur.plan && !cur.draft && cur.state !== 'completed')" class="animate-enter">
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
        <Button variant="primary" @click="confirm">⚡ 快速起草</Button>
        <Button variant="secondary" @click="startChunkedDraft">📑 分段大纲递进起草</Button>
      </div>
    </div>

    <!-- 写作/审查/自愈阶段 -->
    <div v-else-if="cur.state === 'reviewing' || cur.state === 'reviewed' || cur.draft || (projectStore.active && projectStore.active.draft)" class="animate-enter">
      <div class="panel-header-row">
        <h3 class="step-title">文稿生成与智能审查</h3>
        <div class="view-switchers">
          <button class="view-tab" :class="{ on: viewMode === 'edit' }" @click="viewMode = 'edit'">📝 编辑视图</button>
          <button class="view-tab" :class="{ on: viewMode === 'diff' }" @click="viewMode = 'diff'">🔍 Diff 对比</button>
          <button class="view-tab" :class="{ on: viewMode === 'preview' }" @click="viewMode = 'preview'">🖨️ 公文排版预览</button>
        </div>
      </div>

      <!-- 视图 1: 源码/正文编辑 (带划词 AI 伴写浮条) -->
      <div v-if="viewMode === 'edit'" class="edit-container relative">
        <GlassCard>
          <textarea
            ref="draftTextareaRef"
            class="ios-input draft-textarea"
            v-model="draftEdit"
            rows="14"
            placeholder="文稿内容…"
            @select="onDraftSelect"
            @mouseup="onDraftSelect"
            @keyup="onDraftSelect"
            @input="onDraftInput"
          />
        </GlassCard>

        <!-- 划词 AI 伴写浮动工具条 -->
        <div
          v-if="copilotVisible && selectedText.trim()"
          class="inline-copilot-pill animate-pop"
          :style="{ top: copilotY + 'px', left: copilotX + 'px' }"
        >
          <span class="copilot-label">🤖 划词 AI 伴写：</span>
          <button class="copilot-btn" :disabled="copilotBusy" title="对仗工整，提升立意" @click="runInline('polish')">✨ 金句升华</button>
          <button class="copilot-btn" :disabled="copilotBusy" title="剔除套话，精炼字句" @click="runInline('concise')">✂️ 去套话</button>
          <button class="copilot-btn" :disabled="copilotBusy" title="核验政治术语与法规表述" @click="runInline('verify')">🔍 政策校对</button>
          <button class="copilot-btn" :disabled="copilotBusy" title="转为中青报/融媒体年轻态" @click="runInline('style_youth')">🔄 青年态</button>
          <button class="copilot-btn" :disabled="copilotBusy" title="转为人民日报政论体" @click="runInline('style_renmin')">🏛️ 政论体</button>
          <span v-if="copilotBusy" class="copilot-busy">生成中…</span>
        </div>
      </div>

      <!-- 视图 2: Diff 差异对比视图 -->
      <GlassCard v-else-if="viewMode === 'diff'" class="diff-card">
        <div class="diff-header">
          <span class="diff-tag">版本差异高亮对比</span>
          <span class="diff-hint">绿色为新增内容，红色删除线为已剔除内容</span>
        </div>
        <div class="diff-content" v-html="renderedDiff" />
      </GlassCard>

      <!-- 视图 3: GB/T 9704-2012 国家公文标准排版预览 -->
      <div v-else-if="viewMode === 'preview'" class="official-preview-card">
        <div class="preview-toolbar">
          <div class="tpl-select-wrap">
            <label class="tpl-label">排版规范模板：</label>
            <select class="ios-input tpl-select" v-model="selectedTemplateId">
              <option v-for="t in templates" :key="t.id" :value="t.id">{{ t.name }}</option>
            </select>
          </div>
          <div class="preview-actions">
            <Button variant="secondary" @click="printDoc">🖨️ 打印排版</Button>
            <Button variant="primary" @click="downloadDocx">📥 导出 GB/T 9704 Word (.docx)</Button>
          </div>
        </div>

        <!-- 红头公文标准版心视图 -->
        <div class="gbt9704-paper" id="printable-paper">
          <div v-if="curTemplate && curTemplate.header_text" class="gbt-red-header">
            <h1 class="gbt-header-title">{{ curTemplate.header_text }}</h1>
            <div v-if="curTemplate.doc_code" class="gbt-header-code">{{ curTemplate.doc_code }}</div>
            <div class="gbt-red-line" />
          </div>
          <div class="gbt-doc-title">{{ draftTitle }}</div>
          <div class="gbt-doc-body">
            <p v-for="(p, idx) in draftParagraphs" :key="idx" class="gbt-p" :class="getParagraphClass(p)">
              {{ p }}
            </p>
          </div>
        </div>
      </div>

      <!-- 操作动作栏 -->
      <div class="actions" style="margin-top: 12px;">
        <Button variant="primary" @click="runReview">🔍 对文稿执行智能审查</Button>
        <Button
          v-if="cur.review && (cur.review.score < 85 || (cur.review.findings && cur.review.findings.length))"
          variant="primary"
          :disabled="isHealing"
          @click="triggerAutoHeal"
        >{{ isHealing ? '⚡ 正在自主自愈中…' : '⚡ 一键自愈 (85分+)' }}</Button>
        <Button variant="secondary" @click="toggleRevisions">🕒 时光机版本 ({{ revisions.length }})</Button>
        <Button variant="secondary" @click="triggerRedTeam">👔 模拟领导审签/红蓝军测试</Button>
        <Button @click="finalize">确认无误，完成交付</Button>
      </div>

      <!-- 审查诊断卡片 -->
      <GlassCard v-if="cur.review" style="margin-top: 14px;">
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
            <div class="finding-head">
              <span class="sev" :class="'sev-' + f.severity">{{ sevText(f.severity) }}</span>
              <span class="issue">{{ f.issue }}</span>
              <button
                class="fix-btn"
                :disabled="fixingIdx === i"
                @click="fixFinding(i)"
              >{{ fixingIdx === i ? '修复中…' : '自动修复' }}</button>
            </div>
            <span class="sugg">{{ f.suggestion }}</span>
          </div>
        </div>
        <div v-else class="hint-text">未发现问题</div>
        <div v-if="fixMsg" class="fix-msg" :class="{ error: fixErr }">{{ fixMsg }}</div>
      </GlassCard>

      <!-- 红蓝军审签压力测试卡片 -->
      <GlassCard v-if="redTeamResult" class="red-team-card" style="margin-top: 14px;">
        <div class="rt-head">
          <span class="rt-title">👔 分管领导审签与舆情红蓝军压力测试报告</span>
          <span class="rt-badge" :class="'rt-' + redTeamResult.verdict">{{ redTeamResult.verdict || '通过' }}</span>
        </div>
        <div class="rt-body">
          <div class="rt-critique"><b>领导审签挑刺：</b>{{ redTeamResult.superior_critique }}</div>
          <div class="rt-risks">
            <b>舆情风险排查：</b>
            <ul>
              <li v-for="(r, i) in redTeamResult.pr_risk_points" :key="i">{{ r }}</li>
            </ul>
          </div>
          <div v-if="redTeamResult.actionable_fixes" class="rt-fixes">
            <b>整改建议：</b>{{ redTeamResult.actionable_fixes.join('；') }}
          </div>
        </div>
      </GlassCard>

      <!-- 时光机版本快照抽屉 -->
      <GlassCard v-if="showRevisions" class="revisions-drawer" style="margin-top: 14px;">
        <div class="rev-title">🕒 时光机历史版本快照</div>
        <div v-if="!revisions.length" class="hint-text">暂无历史快照</div>
        <div v-for="r in revisions" :key="r.id" class="rev-item">
          <div class="rev-info">
            <span class="rev-time">{{ r.timestamp }}</span>
            <span v-if="r.score" class="rev-score">{{ r.score }}分</span>
            <span class="rev-summary">{{ r.summary }}</span>
          </div>
          <button class="fix-btn" @click="restoreRev(r.id)">恢复此版本</button>
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

    <!-- 空状态 / 启动引导 -->
    <div v-else class="empty-state animate-enter">
      <div style="font-size: 48px; margin-bottom: 8px;">✍️</div>
      <div style="font-size: 18px; font-weight: 700; margin-bottom: 6px;">
        {{ projectStore.active ? projectStore.active.name : '公文写作工作室' }}
      </div>
      <p class="hint-text" style="max-width: 440px; margin-bottom: 18px; line-height: 1.6;">
        {{ projectStore.active ? (projectStore.active.description || '项目已建立。点击下方按钮启动场景路由、需求问卷与多角色智能协商起草流程。') : '请先在左侧项目列表选择或新建一个公文项目' }}
      </p>
      <Button v-if="projectStore.active" variant="primary" @click="startProjectWorkflow">🚀 启动公文起草工作流</Button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
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
const fixingIdx = ref(-1)
const fixMsg = ref('')
const fixErr = ref(false)

const viewMode = ref('edit') // 'edit' | 'diff' | 'preview'
const selectedTemplateId = ref('default_gbt9704')
const templates = ref([])
const revisions = ref([])
const showRevisions = ref(false)
const redTeamResult = ref(null)

// 划词 AI 伴写浮条状态
const draftTextareaRef = ref(null)
const copilotVisible = ref(false)
const copilotX = ref(20)
const copilotY = ref(20)
const copilotBusy = ref(false)
const selectedText = ref('')
const selStart = ref(0)
const selEnd = ref(0)

const severities = [
  { key: 'critical', label: '严重' },
  { key: 'major', label: '重要' },
  { key: 'minor', label: '轻微' },
  { key: 'suggestion', label: '建议' },
]

const pid = computed(() => projectStore.active && projectStore.active.id)
const draftContent = computed(() => {
  const p = projectStore.active
  return (p && p.draft) || cur.value.draft || '（草稿生成中…）'
})
const versions = computed(() => cur.value.versions)
const modeName = computed(() => (cur.value.plan ? cur.value.plan.writing_mode : ''))
const doctypeOptions = ref([])
const styleOptions = ref([])
const selDocType = ref('')
const selStyle = ref('')

const curTemplate = computed(() => {
  return templates.value.find((t) => t.id === selectedTemplateId.value) || templates.value[0] || {}
})

const draftLines = computed(() => {
  const text = (draftEdit.value || draftContent.value || '').trim()
  return text ? text.split('\n').filter((l) => l.trim()) : []
})

const draftTitle = computed(() => draftLines.value[0] || (projectStore.active && projectStore.active.name) || '公文文稿')
const draftParagraphs = computed(() => draftLines.value.slice(1))

function getParagraphClass(p) {
  if (p.endsWith('：') || p.endsWith(':')) return 'gbt-addressee'
  if (/^[一二三四五六七八九十]+、/.test(p)) return 'gbt-h1'
  if (/^（[一二三四五六七八九十]+）/.test(p)) return 'gbt-h2'
  if (/^\d{4}年\d{1,2}月\d{1,2}日$/.test(p) || (p.length < 18 && /(部|局|厅|办公室|处|院)$/.test(p))) return 'gbt-closing'
  return 'gbt-body'
}

// 划词捕获
function onDraftSelect(e) {
  const el = e.target
  if (!el || typeof el.selectionStart !== 'number') return
  selStart.value = el.selectionStart
  selEnd.value = el.selectionEnd
  const txt = el.value.slice(el.selectionStart, el.selectionEnd).trim()
  selectedText.value = txt
  if (txt.length >= 2) {
    copilotX.value = 16
    copilotY.value = 8
    copilotVisible.value = true
  } else {
    copilotVisible.value = false
  }
}

// 划词 AI 伴写操作
async function runInline(action) {
  if (!selectedText.value || !pid.value || copilotBusy.value) return
  copilotBusy.value = true
  try {
    const res = await store.inlineTransform(pid.value, selectedText.value, action, draftEdit.value)
    if (res && res.result) {
      const before = draftEdit.value.slice(0, selStart.value)
      const after = draftEdit.value.slice(selEnd.value)
      draftEdit.value = before + res.result + after
      saveDraft()
      copilotVisible.value = false
    }
  } catch (e) {
    fixErr.value = true
    fixMsg.value = `划词处理失败：${e.message || e}`
  } finally {
    copilotBusy.value = false
  }
}

// 防抖自动保存
let autoSaveTimer = null
function onDraftInput() {
  clearTimeout(autoSaveTimer)
  autoSaveTimer = setTimeout(() => {
    saveDraft()
  }, 800)
}

// 简易 Diff 计算
const renderedDiff = computed(() => {
  const curText = draftEdit.value || draftContent.value || ''
  const prevRev = revisions.value[0]
  if (!prevRev || !prevRev.draft_snapshot) {
    return `<div class="p-2">${curText.replace(/\n/g, '<br/>')}</div>`
  }
  const oldText = prevRev.draft_snapshot
  if (oldText === curText) {
    return `<div class="p-2 text-muted">当前草稿与上一快照版本完全一致，暂无差异变更。</div>`
  }
  // 简易行级 Diff 渲染
  const oldLines = oldText.split('\n')
  const newLines = curText.split('\n')
  let html = ''
  const max = Math.max(oldLines.length, newLines.length)
  for (let i = 0; i < max; i++) {
    const o = oldLines[i] || ''
    const n = newLines[i] || ''
    if (o === n) {
      html += `<div class="diff-line unchanged">${n || '&nbsp;'}</div>`
    } else {
      if (o) html += `<div class="diff-line del"><del>- ${o}</del></div>`
      if (n) html += `<div class="diff-line ins"><ins>+ ${n}</ins></div>`
    }
  }
  return html
})

async function loadTemplates() {
  try {
    templates.value = await api.get('/knowledge/templates')
  } catch { /* ignore */ }
}

async function loadRevisions() {
  if (!pid.value) return
  try {
    revisions.value = await store.getRevisions(pid.value)
  } catch { /* ignore */ }
}

function toggleRevisions() {
  showRevisions.value = !showRevisions.value
  if (showRevisions.value) loadRevisions()
}

async function restoreRev(revId) {
  if (!pid.value) return
  try {
    await store.restoreRevision(pid.value, revId)
    projectStore.active = await api.get(`/projects/${pid.value}`)
    draftEdit.value = projectStore.active.draft
    showRevisions.value = false
    fixMsg.value = '已恢复到选定历史版本'
  } catch (e) {
    fixErr.value = true
    fixMsg.value = `恢复失败：${e.message || e}`
  }
}

async function startChunkedDraft() {
  if (!pid.value) return
  try {
    await store.chunkedDraft(pid.value)
    projectStore.active = await api.get(`/projects/${pid.value}`)
    draftEdit.value = projectStore.active.draft
  } catch (e) {
    fixErr.value = true
    fixMsg.value = `分段起草失败：${e.message || e}`
  }
}

async function triggerRedTeam() {
  if (!pid.value) return
  try {
    const res = await store.redTeamReview(pid.value)
    redTeamResult.value = res
    projectStore.active = await api.get(`/projects/${pid.value}`)
  } catch (e) {
    fixErr.value = true
    fixMsg.value = `红蓝军压力测试失败：${e.message || e}`
  }
}

function downloadDocx() {
  if (!pid.value) return
  const tplId = selectedTemplateId.value || 'default_gbt9704'
  window.open(`/api/projects/${pid.value}/export/docx?template_id=${tplId}`, '_blank')
}

function printDoc() {
  window.print()
}

async function startProjectWorkflow() {
  const pidVal = projectStore.active && projectStore.active.id
  if (!pidVal) return
  await store.start(pidVal)
  store.attachEvents(pidVal)
}

watch(() => projectStore.active, (p) => {
  if (p) {
    draftEdit.value = p.draft || ''
    redTeamResult.value = p.red_team_result || null
    loadRevisions()
    loadTemplates()
    const s = store.ensure(p.id)
    if (p.draft) {
      s.draft = p.draft
      if (!s.state || s.state === 'idle') s.state = 'reviewing'
      if (p.review_results && p.review_results.length) {
        s.review = p.review_results[p.review_results.length - 1]
      }
      if (p.plan) s.plan = p.plan
    } else if (p.plan) {
      s.plan = p.plan
      if (!s.state || s.state === 'idle') s.state = 'waiting_approval'
      loadPlanOptions()
    }
  }
}, { immediate: true })

watch(() => cur.value.draft, (d) => {
  if (d && !draftEdit.value) draftEdit.value = d
})

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

async function saveDraft() {
  if (pid.value && draftEdit.value !== undefined) {
    await api.patch(`/projects/${pid.value}/draft`, { draft: draftEdit.value })
    projectStore.active = await api.get(`/projects/${pid.value}`)
    loadRevisions()
  }
}

function sevText(s) {
  return { critical: '严重', major: '重要', minor: '轻微', suggestion: '建议' }[s] || s
}

async function fixFinding(i) {
  if (!pid.value) return
  fixingIdx.value = i
  fixMsg.value = ''
  fixErr.value = false
  try {
    const result = await store.fixFinding(pid.value, i)
    if (result && result.fixed) {
      fixMsg.value = `已自动修复（${result.fixed_method === 'llm' ? 'AI 改写' : '规则处理'}），已重新审查`
      projectStore.active = await api.get(`/projects/${pid.value}`)
      draftEdit.value = projectStore.active.draft
      loadRevisions()
    }
  } catch (e) {
    fixErr.value = true
    fixMsg.value = (e && e.message) || '自动修复失败'
  } finally {
    fixingIdx.value = -1
  }
}

const isHealing = ref(false)
async function triggerAutoHeal() {
  if (!pid.value) return
  isHealing.value = true
  fixMsg.value = ''
  fixErr.value = false
  try {
    const res = await store.autoHeal(pid.value)
    projectStore.active = await api.get(`/projects/${pid.value}`)
    draftEdit.value = projectStore.active.draft
    loadRevisions()
    fixMsg.value = `⚡ 自愈收敛完成：得分 ${res.final_score} 分（共 ${res.rounds_run || 0} 轮）`
  } catch (e) {
    fixErr.value = true
    fixMsg.value = (e && e.message) || '自愈执行失败'
  } finally {
    isHealing.value = false
  }
}

onMounted(() => {
  loadTemplates()
  loadRevisions()
})
</script>

<style scoped>
.workflow-panel { display: flex; flex-direction: column; gap: 16px; position: relative; }
.step-title { font-size: 18px; font-weight: 700; }
.panel-header-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.view-switchers { display: flex; gap: 4px; background: var(--glass-highlight); padding: 3px; border-radius: 8px; }
.view-tab {
  padding: 4px 10px; font-size: 12px; font-weight: 600; border-radius: 6px;
  background: transparent; border: none; color: var(--color-ink-muted); cursor: pointer;
  transition: all 0.2s;
}
.view-tab.on { background: var(--color-surface); color: var(--color-primary); box-shadow: 0 1px 3px rgba(0,0,0,0.1); }

.relative { position: relative; }
.draft-textarea { resize: vertical; min-height: 280px; width: 100%; font-family: var(--font-ui); line-height: 1.7; font-size: 14px; }

/* 划词 AI 伴写浮条 */
.inline-copilot-pill {
  position: absolute; z-index: 30;
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; border-radius: 20px;
  background: var(--color-surface); border: 1px solid var(--color-primary);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
}
.copilot-label { font-size: 11px; font-weight: 700; color: var(--color-primary); }
.copilot-btn {
  padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: 600;
  background: color-mix(in srgb, var(--color-primary) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-primary) 30%, transparent);
  color: var(--color-primary); cursor: pointer; transition: all 0.15s;
}
.copilot-btn:hover:not(:disabled) {
  background: var(--color-primary); color: #fff; transform: translateY(-1px);
}
.copilot-busy { font-size: 11px; color: var(--color-accent); font-weight: 600; }

/* Diff 视图 */
.diff-card { max-height: 480px; overflow-y: auto; }
.diff-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-size: 12px; }
.diff-tag { font-weight: 700; color: var(--color-primary); }
.diff-hint { color: var(--color-ink-muted); font-size: 11px; }
.diff-content { font-family: var(--font-mono, monospace); font-size: 13px; line-height: 1.6; }
.diff-line { padding: 2px 6px; }
.diff-line.del { background: rgba(255, 107, 94, 0.15); color: #dc2626; text-decoration: line-through; }
.diff-line.ins { background: rgba(34, 197, 94, 0.15); color: #16a34a; font-weight: 600; }

/* GB/T 9704 红头公文排版预览 */
.official-preview-card { display: flex; flex-direction: column; gap: 12px; }
.preview-toolbar { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.tpl-select-wrap { display: flex; align-items: center; gap: 6px; font-size: 12px; }
.tpl-label { color: var(--color-ink-muted); }
.tpl-select { padding: 4px 8px; font-size: 12px; }
.preview-actions { display: flex; gap: 8px; }

.gbt9704-paper {
  background: #ffffff; color: #000000;
  border-radius: 4px; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  padding: 40px 36px; min-height: 520px; max-height: 600px; overflow-y: auto;
  font-family: 'FangSong', '仿宋_GB2312', '仿宋', serif;
}
.gbt-red-header { text-align: center; margin-bottom: 24px; }
.gbt-header-title { font-family: 'SimSun', '方正小标宋_GB2312', '小标宋', serif; color: #da291c; font-size: 26px; font-weight: 900; margin: 0 0 8px 0; }
.gbt-header-code { font-size: 13px; color: #333; margin-bottom: 8px; }
.gbt-red-line { height: 3px; background: #da291c; width: 100%; }
.gbt-doc-title {
  text-align: center; font-family: 'SimSun', '方正小标宋_GB2312', '小标宋', serif;
  font-size: 20px; font-weight: 700; margin: 16px 0 20px 0; line-height: 1.4; color: #000;
}
.gbt-doc-body { display: flex; flex-direction: column; gap: 6px; }
.gbt-p { margin: 0; line-height: 1.75; font-size: 15px; text-align: justify; }
.gbt-p.gbt-body { text-indent: 2em; }
.gbt-p.gbt-addressee { font-weight: 600; text-indent: 0; margin-bottom: 6px; }
.gbt-p.gbt-h1 { font-family: 'SimHei', '黑体', sans-serif; font-weight: 700; text-indent: 2em; }
.gbt-p.gbt-h2 { font-family: 'KaiTi', '楷体_GB2312', '楷体', serif; font-weight: 600; text-indent: 2em; }
.gbt-p.gbt-closing { text-align: right; text-indent: 0; margin-top: 14px; }

/* 红蓝军压力测试卡片 */
.red-team-card { margin-top: 10px; border: 1px dashed var(--color-accent); }
.rt-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.rt-title { font-size: 13px; font-weight: 700; color: var(--color-accent); }
.rt-badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 700; }
.rt-通过 { background: rgba(34, 197, 94, 0.15); color: #16a34a; }
.rt-需关注 { background: rgba(234, 179, 8, 0.15); color: #ca8a04; }
.rt-严厉整改 { background: rgba(239, 68, 68, 0.15); color: #dc2626; }
.rt-body { display: flex; flex-direction: column; gap: 6px; font-size: 12px; line-height: 1.6; }
.rt-risks ul { margin: 4px 0 0 16px; padding: 0; }

/* 时光机抽屉 */
.revisions-drawer { margin-top: 10px; display: flex; flex-direction: column; gap: 8px; max-height: 240px; overflow-y: auto; }
.rev-title { font-size: 13px; font-weight: 700; color: var(--color-ink-body); margin-bottom: 4px; }
.rev-item { display: flex; justify-content: space-between; align-items: center; padding: 6px 10px; border-radius: 8px; background: var(--glass-highlight); }
.rev-info { display: flex; flex-direction: column; gap: 2px; }
.rev-time { font-size: 11px; font-weight: 600; color: var(--color-ink-body); }
.rev-score { font-size: 10px; color: var(--color-accent); font-weight: 700; margin-right: 6px; }
.rev-summary { font-size: 11px; color: var(--color-ink-muted); }

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
.actions { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
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
.findings { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.finding { padding: 10px; border-radius: 12px; background: var(--glass-highlight); border: 1px solid var(--glass-border); }
.sev { display: inline-block; font-size: 11px; font-weight: 700; padding: 1px 6px; border-radius: 4px; margin-right: 6px; }
.sev-critical { background: rgba(255, 107, 94, 0.2); color: var(--color-danger); }
.sev-major { background: rgba(255, 180, 90, 0.2); color: #FFB45A; }
.sev-minor { background: rgba(167, 139, 250, 0.2); color: #A78BFA; }
.sev-suggestion { background: rgba(140, 160, 180, 0.2); color: var(--color-ink-muted); }
.issue { font-weight: 600; font-size: 13px; }
.sugg { display: block; color: var(--color-ink-muted); font-size: 12px; margin-top: 4px; }
.finding-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.fix-btn {
  margin-left: auto; flex-shrink: 0; font-family: var(--font-ui); font-size: 12px;
  font-weight: 600; color: var(--color-accent); background: rgba(0, 0, 0, 0.12);
  border: 1px solid var(--color-accent-focus); border-radius: 8px; padding: 3px 10px;
  cursor: pointer; transition: transform 0.15s var(--ease-out-expo), opacity 0.15s;
}
.fix-btn:hover:not(:disabled) { transform: translateY(-1px); }
.fix-btn:disabled { opacity: 0.5; cursor: wait; }
.fix-msg {
  margin-top: 10px; padding: 8px 12px; border-radius: 10px; font-size: 12px;
  background: rgba(52, 199, 89, 0.12); color: #34C759; border: 1px solid rgba(52, 199, 89, 0.25);
}
.fix-msg.error { background: rgba(255, 107, 94, 0.1); color: var(--color-danger); border-color: rgba(255, 107, 94, 0.25); }
.multi-doc h4 { font-size: 14px; margin-bottom: 8px; }
.version { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--glass-border); }
.version-name { font-weight: 600; font-size: 13px; }
.version-count { color: var(--color-ink-muted); font-size: 12px; }
@media (max-width: 768px) {
  .plan-grid { grid-template-columns: 1fr; }
  .adjust-row { flex-direction: column; align-items: stretch; }
  .adjust-row select { min-width: 0; }
  .actions { flex-wrap: wrap; }
}
</style>

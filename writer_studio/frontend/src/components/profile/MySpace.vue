<template>
  <div class="myspace">
    <!-- 面包屑 -->
    <div class="crumb">
      <button class="crumb-btn" @click="view = 'list'">🏠 项目</button>
      <template v-if="view === 'project'"><span class="crumb-sep">/</span><span class="crumb-cur">{{ currentProject ? currentProject.name : '' }}</span></template>
    </div>

    <!-- 项目列表 -->
    <div v-if="view === 'list'" class="section">
      <h4 class="sec-title">项目档案</h4>
      <p class="hint-text">每个项目可多次写作，个性化数据（参考文本/要求/审查历史）稳定保留。</p>
      <div v-if="!projects.length" class="hint-text">还没有项目，先在左侧新建</div>
      <div v-for="p in projects" :key="p.id" class="folder-card row-card" @click="openProject(p.id)">
        <div class="fc-icon">📁</div>
        <div class="fc-body">
          <div class="fc-name">{{ p.name }}</div>
          <div class="fc-desc">{{ statusText(p.status) }} · 参考 {{ (p.references || []).length }} 篇 · 审查 {{ (p.review_history || []).length + (p.review_results || []).length }} 次</div>
        </div>
      </div>
    </div>

    <!-- 项目详情 -->
    <div v-else-if="view === 'project' && currentProject" class="section">
      <GlassCard>
        <div class="sec-label">风格要求</div>
        <textarea class="ios-input" v-model="curStyle" rows="2" placeholder="如：多短句、少官方腔…" />
        <div class="sec-label">工作要求</div>
        <textarea class="ios-input" v-model="curWork" rows="2" placeholder="如：面向学工处汇报，突出数据…" />
        <button class="mini-btn" @click="saveProjectReq">保存要求</button>
        <div v-if="currentProject.questionnaire_summary" class="q-summary">
          <div class="sec-label">问卷总结</div>
          <pre class="ref-analysis">{{ currentProject.questionnaire_summary }}</pre>
        </div>
        <div v-if="currentProject.favorite_terms.length || currentProject.favorite_phrases.length" class="q-summary">
          <div class="sec-label">项目收藏（含参考文本自动归纳）</div>
          <div class="chip-row">
            <span v-for="(t, i) in currentProject.favorite_terms" :key="'t' + i" class="chip chip-term">{{ t }}</span>
            <span v-for="(p, i) in currentProject.favorite_phrases" :key="'p' + i" class="chip chip-phrase">{{ p }}</span>
          </div>
        </div>
      </GlassCard>

      <div class="sec-label" style="margin-top: 12px">项目参考文本（AI 解读并自动归纳词汇/句式入收藏）</div>
      <button class="import-btn" @click="showImport = !showImport">＋ 导入参考文本</button>
      <div v-if="showImport" class="ios-card import-box">
        <div class="import-row">
          <input class="ios-input" v-model="importUrl" placeholder="粘贴网页 URL" />
          <button class="mini-btn" @click="importUrlRef">导入网页</button>
        </div>
        <input class="ios-input" v-model="importTitle" placeholder="标题（可选）" />
        <textarea class="ios-input" v-model="importText" rows="3" placeholder="或粘贴文本…" />
        <button class="mini-btn" @click="importTextRef">导入文本</button>
      </div>
      <div v-if="!projectRefs.length" class="hint-text">还没有参考文本</div>
      <div v-for="ref in projectRefs" :key="ref.id" class="k-item" @click="openRef = openRef === ref.id ? '' : ref.id">
        <div class="k-title">{{ ref.title }}<span class="k-meta">{{ ref.source.slice(0, 24) }}</span></div>
        <div v-if="openRef === ref.id" class="k-detail">
          <pre class="ref-analysis">{{ ref.analysis || '（点击解读）' }}</pre>
          <button class="mini-btn danger" @click.stop="deleteRef(ref.id)">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../../api/client'
import { useProjectStore } from '../../stores/project'
import GlassCard from '../ui/GlassCard.vue'

const projectStore = useProjectStore()
const projects = ref([])
const view = ref('list')
const currentProject = ref(null)
const curStyle = ref('')
const curWork = ref('')
const projectRefs = ref([])
const openRef = ref('')
const showImport = ref(false)
const importUrl = ref('')
const importTitle = ref('')
const importText = ref('')

function statusText(s) { return { draft: '草稿', in_progress: '进行中', completed: '已完成', archived: '已归档' }[s] || s }

async function load() {
  const d = await api.get('/profile/overview')
  projects.value = d.projects
}

async function openProject(id) {
  view.value = 'project'
  currentProject.value = await api.get(`/projects/${id}`)
  curStyle.value = currentProject.value.style_requirements || ''
  curWork.value = currentProject.value.work_requirements || ''
  projectRefs.value = currentProject.value.references || []
}

async function saveProjectReq() {
  const p = currentProject.value
  p.style_requirements = curStyle.value
  p.work_requirements = curWork.value
  await api.patch(`/projects/${p.id}`, { name: p.name, description: p.description })
  currentProject.value = await api.get(`/projects/${p.id}`)
  await load()
}

async function importUrlRef() {
  if (!currentProject.value || !importUrl.value.trim()) return
  await api.post(`/projects/${currentProject.value.id}/references/url`, { url: importUrl.value.trim() })
  importUrl.value = ''
  currentProject.value = await api.get(`/projects/${currentProject.value.id}`)
  projectRefs.value = currentProject.value.references || []
}

async function importTextRef() {
  if (!currentProject.value || !importText.value.trim()) return
  await api.post(`/projects/${currentProject.value.id}/references/text`, { title: importTitle.value, content: importText.value })
  importTitle.value = ''
  importText.value = ''
  currentProject.value = await api.get(`/projects/${currentProject.value.id}`)
  projectRefs.value = currentProject.value.references || []
}

async function deleteRef(id) {
  await api.del(`/projects/${currentProject.value.id}/references/${id}`)
  currentProject.value = await api.get(`/projects/${currentProject.value.id}`)
  projectRefs.value = currentProject.value.references || []
}

onMounted(load)
</script>

<style scoped>
.myspace { display: flex; flex-direction: column; gap: 12px; }
.crumb { display: flex; align-items: center; gap: 4px; font-size: 12px; flex-wrap: wrap; }
.crumb-btn { background: none; border: none; color: var(--color-ink-muted); cursor: pointer; font-size: 12px; font-family: var(--font-ui); }
.crumb-btn:hover { color: var(--color-accent); }
.crumb-sep { color: var(--color-ink-muted); }
.crumb-cur { color: var(--color-ink-body); font-weight: 600; }
.section { display: flex; flex-direction: column; gap: 10px; }
.sec-title { font-size: 15px; font-weight: 700; }
.sec-label { font-size: 12px; color: var(--color-ink-muted); margin: 4px 0; }
.hint-text { color: var(--color-ink-muted); font-size: 12px; }
.folder-card { padding: 14px; border-radius: 14px; cursor: pointer; background: var(--glass-highlight); border: 1px solid var(--glass-border); transition: all 0.2s; }
.folder-card:hover { border-color: var(--color-accent); }
.row-card { display: flex; gap: 10px; align-items: center; }
.fc-icon { font-size: 24px; }
.fc-body { flex: 1; }
.fc-name { font-weight: 700; font-size: 14px; }
.fc-desc { color: var(--color-ink-muted); font-size: 11px; margin-top: 2px; }
.import-btn { border: 1px dashed var(--glass-border); background: var(--glass-highlight); color: var(--color-ink-body); padding: 8px; border-radius: 12px; font-size: 13px; font-weight: 600; cursor: pointer; font-family: var(--font-ui); }
.import-btn:hover { border-color: var(--color-accent); }
.import-box { display: flex; flex-direction: column; gap: 8px; }
.import-row { display: flex; gap: 8px; align-items: center; }
.mini-btn { border: 1px solid var(--glass-border); background: none; color: var(--color-ink-body); padding: 3px 10px; border-radius: 8px; font-size: 11px; cursor: pointer; font-family: var(--font-ui); }
.mini-btn:hover { border-color: var(--color-accent); }
.mini-btn.danger { color: var(--color-danger); }
.k-item { padding: 10px 12px; border-radius: 12px; cursor: pointer; background: var(--glass-highlight); border: 1px solid var(--glass-border); }
.k-item:hover { border-color: var(--color-accent-focus); }
.k-title { font-weight: 600; font-size: 13px; }
.k-meta { color: var(--color-ink-muted); font-size: 11px; margin-left: 6px; font-weight: 400; }
.k-detail { margin-top: 8px; display: flex; flex-direction: column; gap: 6px; }
.ref-analysis { white-space: pre-wrap; font-family: var(--font-ui); font-size: 12px; line-height: 1.6; color: var(--color-ink-body); background: rgba(0,0,0,0.15); padding: 8px; border-radius: 8px; }
.q-summary { margin-top: 10px; }
.chip-row { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { padding: 3px 10px; border-radius: 999px; font-size: 12px; background: var(--glass-highlight); border: 1px solid var(--glass-border); }
.chip-term { color: var(--color-accent); }
.chip-phrase { color: var(--color-ink-body); }
</style>

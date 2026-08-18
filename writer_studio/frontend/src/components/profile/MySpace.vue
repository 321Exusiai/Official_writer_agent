<template>
  <div class="myspace">
    <!-- 面包屑 -->
    <div class="crumb">
      <button class="crumb-btn" @click="gotoRoot">🏠 我的空间</button>
      <template v-for="(p, i) in path" :key="i">
        <span class="crumb-sep">/</span>
        <button class="crumb-btn" @click="backTo(i)">{{ p.label }}</button>
      </template>
    </div>

    <!-- 根视图：三个文件夹 -->
    <div v-if="view === 'root'" class="folder-grid">
      <div class="folder-card" @click="view = 'profile'">
        <div class="fc-icon">👤</div>
        <div class="fc-name">用户画像</div>
        <div class="fc-desc">偏好 · 弱点 · bias · 收藏</div>
      </div>
      <div class="folder-card" @click="view = 'refs'">
        <div class="fc-icon">📚</div>
        <div class="fc-name">参考文本库</div>
        <div class="fc-desc">{{ profile.reference_articles.length }} 篇 · 智能解读</div>
      </div>
      <div class="folder-card" @click="view = 'projects'">
        <div class="fc-icon">📁</div>
        <div class="fc-name">项目</div>
        <div class="fc-desc">{{ projects.length }} 个 · 逐层查看</div>
      </div>
    </div>

    <!-- 用户画像 -->
    <div v-else-if="view === 'profile'" class="section">
      <h4 class="sec-title">用户画像</h4>
      <GlassCard>
        <div class="sec-label">写作偏好</div>
        <div class="chip-row">
          <span v-for="(pref, i) in profile.preferences" :key="i" class="chip">{{ pref }}</span>
          <button v-if="!addingPref" class="mini-add" @click="addingPref = true">＋</button>
        </div>
        <div v-if="addingPref" class="inline-add">
          <input class="ios-input" v-model="newPref" placeholder="如：喜欢短句" @keyup.enter="addPref" />
          <button class="mini-btn" @click="addPref">添加</button>
        </div>

        <div class="sec-label" style="margin-top: 14px">弱点与 bias（AI 分析）</div>
        <button v-if="!analysis" class="mini-btn" @click="runAnalysis">运行画像分析</button>
        <template v-else>
          <div v-for="(w, i) in analysis.weaknesses" :key="'w' + i" class="analysis-line">⚠️ {{ w }}</div>
          <div v-for="(b, i) in analysis.bias_warnings" :key="'b' + i" class="analysis-line">🧭 {{ b }}</div>
          <div class="analysis-sum">{{ analysis.summary }}</div>
        </template>

        <div class="sec-label" style="margin-top: 14px">收藏的词汇 / 句子</div>
        <div class="chip-row">
          <span v-for="(t, i) in profile.favorite_terms" :key="'t' + i" class="chip chip-term">{{ t }}
            <button class="chip-x" @click="removeFav('term', t)">×</button>
          </span>
          <span v-for="(p, i) in profile.favorite_phrases" :key="'p' + i" class="chip chip-phrase">{{ p }}
            <button class="chip-x" @click="removeFav('phrase', p)">×</button>
          </span>
        </div>
        <div class="inline-add">
          <input class="ios-input" v-model="newFav" placeholder="收藏词汇或句子" @keyup.enter="addFav" />
          <select class="ios-input fav-kind" v-model="favKind"><option value="term">词汇</option><option value="phrase">句子</option></select>
          <button class="mini-btn" @click="addFav">收藏</button>
        </div>
      </GlassCard>
    </div>

    <!-- 参考文本库（用户级） -->
    <div v-else-if="view === 'refs'" class="section">
      <h4 class="sec-title">参考文本库</h4>
      <button class="import-btn" @click="showImport = !showImport">＋ 导入参考文本</button>
      <div v-if="showImport" class="ios-card import-box">
        <div class="import-row">
          <input class="ios-input" v-model="importUrl" placeholder="粘贴网页 URL" @keyup.enter="importUrlRef" />
          <button class="mini-btn" @click="importUrlRef">导入网页</button>
        </div>
        <input class="ios-input" v-model="importTitle" placeholder="标题（可选）" />
        <textarea class="ios-input" v-model="importText" rows="4" placeholder="或粘贴文本…" />
        <button class="mini-btn" @click="importTextRef">导入文本</button>
      </div>
      <div v-if="!profile.reference_articles.length" class="hint-text">还没有参考文本，导入后会智能解读词汇、句式与表达方式</div>
      <div v-for="ref in profile.reference_articles" :key="ref.id" class="k-item" @click="openRef = openRef === ref.id ? '' : ref.id">
        <div class="k-title">{{ ref.title }}<span class="k-meta">{{ ref.source.slice(0, 24) }}</span></div>
        <div v-if="openRef === ref.id" class="k-detail">
          <pre class="ref-analysis">{{ ref.analysis || '（点击解读）' }}</pre>
          <button class="mini-btn" @click.stop="analyzeRef(ref.id)">重新解读</button>
          <button class="mini-btn danger" @click.stop="deleteRef(ref.id)">删除</button>
        </div>
      </div>
    </div>

    <!-- 项目列表 -->
    <div v-else-if="view === 'projects'" class="section">
      <h4 class="sec-title">我的项目</h4>
      <div v-if="!projects.length" class="hint-text">还没有项目</div>
      <div v-for="p in projects" :key="p.id" class="folder-card row-card" @click="openProject(p.id)">
        <div class="fc-icon">📁</div>
        <div class="fc-body">
          <div class="fc-name">{{ p.name }}</div>
          <div class="fc-desc">{{ statusText(p.status) }} · {{ p.questionnaire_summary ? '问卷已总结' : '未完成问卷' }}</div>
        </div>
      </div>
    </div>

    <!-- 项目详情 -->
    <div v-else-if="view === 'project'" class="section">
      <h4 class="sec-title">{{ currentProject ? currentProject.name : '' }}</h4>
      <GlassCard>
        <div class="sec-label">风格要求</div>
        <textarea class="ios-input" v-model="curStyle" rows="2" placeholder="如：多短句、少官方腔…" />
        <div class="sec-label">工作要求</div>
        <textarea class="ios-input" v-model="curWork" rows="2" placeholder="如：面向学工处汇报，突出数据…" />
        <button class="mini-btn" @click="saveProjectReq">保存要求</button>
        <div v-if="currentProject && currentProject.questionnaire_summary" class="q-summary">
          <div class="sec-label">问卷总结</div>
          <pre class="ref-analysis">{{ currentProject.questionnaire_summary }}</pre>
        </div>
      </GlassCard>
      <div class="sec-label" style="margin-top: 12px">项目参考文本</div>
      <button class="import-btn" @click="showProjImport = !showProjImport">＋ 导入</button>
      <div v-if="showProjImport" class="ios-card import-box">
        <div class="import-row">
          <input class="ios-input" v-model="projImportUrl" placeholder="粘贴网页 URL" />
          <button class="mini-btn" @click="importProjUrl">导入</button>
        </div>
        <textarea class="ios-input" v-model="projImportText" rows="3" placeholder="或粘贴文本…" />
        <button class="mini-btn" @click="importProjText">导入文本</button>
      </div>
      <div v-if="projectRefs.length" v-for="ref in projectRefs" :key="ref.id" class="k-item" @click="openProjRef = openProjRef === ref.id ? '' : ref.id">
        <div class="k-title">{{ ref.title }}</div>
        <div v-if="openProjRef === ref.id" class="k-detail">
          <pre class="ref-analysis">{{ ref.content.slice(0, 300) }}</pre>
          <button class="mini-btn danger" @click.stop="deleteProjRef(ref.id)">删除</button>
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
const profile = ref({ favorite_terms: [], favorite_phrases: [], preferences: [], reference_articles: [] })
const projects = ref([])
const analysis = ref(null)
const view = ref('root')
const path = ref([])
const openRef = ref('')
const openProjRef = ref('')
const addingPref = ref(false)
const newPref = ref('')
const newFav = ref('')
const favKind = ref('term')
const showImport = ref(false)
const importUrl = ref('')
const importTitle = ref('')
const importText = ref('')
const currentProject = ref(null)
const curStyle = ref('')
const curWork = ref('')
const showProjImport = ref(false)
const projImportUrl = ref('')
const projImportText = ref('')
const projectRefs = ref([])

function statusText(s) { return { draft: '草稿', in_progress: '进行中', completed: '已完成', archived: '已归档' }[s] || s }

async function loadOverview() {
  const d = await api.get('/profile/overview')
  profile.value = d.profile
  projects.value = d.projects
  analysis.value = d.analysis
}

function gotoRoot() { view.value = 'root'; path.value = [] }
function backTo(i) { path.value = path.value.slice(0, i + 1) }

async function addPref() {
  if (!newPref.value.trim()) return
  profile.value.preferences.push(newPref.value.trim())
  newPref.value = ''
  addingPref.value = false
  await api.post('/profile/preferences', { preferences: profile.value.preferences })
}

async function addFav() {
  if (!newFav.value.trim()) return
  await api.post('/profile/favorites', { kind: favKind.value, value: newFav.value.trim() })
  newFav.value = ''
  await loadOverview()
}

async function removeFav(kind, value) {
  await api.del(`/profile/favorites?kind=${kind}&value=${encodeURIComponent(value)}`)
  await loadOverview()
}

async function runAnalysis() {
  analysis.value = await api.post('/profile/analyze')
}

async function importUrlRef() {
  if (!importUrl.value.trim()) return
  await api.post('/profile/references/url', { url: importUrl.value.trim() })
  importUrl.value = ''
  await loadOverview()
}

async function importTextRef() {
  if (!importText.value.trim()) return
  await api.post('/profile/references/text', { title: importTitle.value, content: importText.value })
  importTitle.value = ''
  importText.value = ''
  await loadOverview()
}

async function analyzeRef(id) {
  await api.post(`/profile/references/${id}/analyze`)
  await loadOverview()
}

async function deleteRef(id) {
  await api.del(`/profile/references/${id}`)
  await loadOverview()
}

async function openProject(id) {
  view.value = 'project'
  path.value = [{ label: '项目' }, { label: '详情' }]
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
  await loadOverview()
}

async function importProjUrl() {
  if (!currentProject.value || !projImportUrl.value.trim()) return
  await api.post(`/projects/${currentProject.value.id}/references/url`, { url: projImportUrl.value.trim() })
  projImportUrl.value = ''
  currentProject.value = await api.get(`/projects/${currentProject.value.id}`)
  projectRefs.value = currentProject.value.references || []
}

async function importProjText() {
  if (!currentProject.value || !projImportText.value.trim()) return
  await api.post(`/projects/${currentProject.value.id}/references/text`, { title: '项目参考', content: projImportText.value })
  projImportText.value = ''
  currentProject.value = await api.get(`/projects/${currentProject.value.id}`)
  projectRefs.value = currentProject.value.references || []
}

async function deleteProjRef(id) {
  await api.del(`/projects/${currentProject.value.id}/references/${id}`)
  currentProject.value = await api.get(`/projects/${currentProject.value.id}`)
  projectRefs.value = currentProject.value.references || []
}

onMounted(loadOverview)
</script>

<style scoped>
.myspace { display: flex; flex-direction: column; gap: 12px; }
.crumb { display: flex; align-items: center; gap: 4px; font-size: 12px; flex-wrap: wrap; }
.crumb-btn { background: none; border: none; color: var(--color-ink-muted); cursor: pointer; font-size: 12px; font-family: var(--font-ui); }
.crumb-btn:hover { color: var(--color-accent); }
.crumb-sep { color: var(--color-ink-muted); }
.folder-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.folder-card {
  padding: 16px; border-radius: 16px; cursor: pointer;
  background: var(--glass-highlight); border: 1px solid var(--glass-border);
  transition: all 0.2s;
}
.folder-card:hover { border-color: var(--color-accent); transform: translateY(-2px); }
.fc-icon { font-size: 26px; }
.fc-name { font-weight: 700; font-size: 14px; margin-top: 6px; }
.fc-desc { color: var(--color-ink-muted); font-size: 11px; margin-top: 2px; }
.row-card { display: flex; gap: 10px; align-items: center; padding: 12px; }
.fc-body { flex: 1; }
.section { display: flex; flex-direction: column; gap: 10px; }
.sec-title { font-size: 15px; font-weight: 700; }
.sec-label { font-size: 12px; color: var(--color-ink-muted); margin: 4px 0; }
.chip-row { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { padding: 3px 10px; border-radius: 999px; font-size: 12px; background: var(--glass-highlight); border: 1px solid var(--glass-border); }
.chip-term { color: var(--color-accent); }
.chip-phrase { color: var(--color-ink-body); }
.chip-x { background: none; border: none; color: var(--color-ink-muted); cursor: pointer; margin-left: 4px; }
.mini-add { background: none; border: 1px dashed var(--glass-border); color: var(--color-ink-muted); border-radius: 999px; width: 24px; height: 24px; cursor: pointer; }
.inline-add { display: flex; gap: 6px; margin-top: 8px; align-items: center; }
.fav-kind { flex: 0 0 80px; }
.mini-btn { border: 1px solid var(--glass-border); background: none; color: var(--color-ink-body); padding: 3px 10px; border-radius: 8px; font-size: 11px; cursor: pointer; font-family: var(--font-ui); }
.mini-btn:hover { border-color: var(--color-accent); }
.mini-btn.danger { color: var(--color-danger); }
.analysis-line { font-size: 12px; color: var(--color-ink-body); margin: 3px 0; }
.analysis-sum { font-size: 11px; color: var(--color-ink-muted); margin-top: 6px; }
.import-btn { border: 1px dashed var(--glass-border); background: var(--glass-highlight); color: var(--color-ink-body); padding: 8px; border-radius: 12px; font-size: 13px; font-weight: 600; cursor: pointer; font-family: var(--font-ui); }
.import-btn:hover { border-color: var(--color-accent); }
.import-box { display: flex; flex-direction: column; gap: 8px; }
.import-row { display: flex; gap: 8px; align-items: center; }
.k-item { padding: 10px 12px; border-radius: 12px; cursor: pointer; background: var(--glass-highlight); border: 1px solid var(--glass-border); }
.k-item:hover { border-color: var(--color-accent-focus); }
.k-title { font-weight: 600; font-size: 13px; }
.k-meta { color: var(--color-ink-muted); font-size: 11px; margin-left: 6px; font-weight: 400; }
.k-detail { margin-top: 8px; display: flex; flex-direction: column; gap: 6px; }
.ref-analysis { white-space: pre-wrap; font-family: var(--font-ui); font-size: 12px; line-height: 1.6; color: var(--color-ink-body); background: rgba(0,0,0,0.15); padding: 8px; border-radius: 8px; }
.hint-text { color: var(--color-ink-muted); font-size: 12px; }
.q-summary { margin-top: 10px; }
</style>

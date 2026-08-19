<template>
  <div class="profile-panel">
    <div class="pp-head">
      <h3 class="pp-title">👤 用户画像</h3>
      <Button variant="secondary" @click="runAnalysis">重新分析</Button>
    </div>

    <div v-if="loading" class="skeleton-row">
      <div class="skeleton sk-line w60"></div>
      <div class="skeleton sk-line w80"></div>
      <div class="skeleton sk-block"></div>
      <div class="skeleton sk-line w40"></div>
    </div>

    <!-- 总览 -->
    <div v-else-if="analysis" class="pp-overview">
      <span class="ov-item">📁 {{ (projects || []).length }} 个项目</span>
      <span class="ov-item">⚠️ {{ ((analysis && analysis.weaknesses) || []).length }} 项弱点</span>
      <span class="ov-item">🧭 {{ ((analysis && analysis.bias_warnings) || []).length }} 条 bias 预警</span>
      <span class="ov-item">⭐ {{ ((profile && profile.favorite_terms) || []).length + ((profile && profile.favorite_phrases) || []).length }} 条收藏</span>
    </div>

    <div class="pp-grid">
      <!-- 偏好 -->
      <div class="ios-card pp-card">
        <div class="pp-label">写作偏好</div>
        <label class="mem-toggle" :class="{ on: profile && profile.memory_enabled }">
          <input type="checkbox" v-model="profile.memory_enabled" @change="toggleMemory" />
          <span class="mem-switch"></span>
          <span class="mem-text">助手长期记忆：自动从对话提炼偏好</span>
        </label>
        <div class="chip-row">
          <span v-for="(pref, i) in (profile && profile.preferences) || []" :key="i" class="chip">{{ pref }}</span>
          <button v-if="!addingPref" class="mini-add" @click="addingPref = true">＋</button>
        </div>
        <div v-if="addingPref" class="inline-add">
          <input class="ios-input" v-model="newPref" placeholder="如：喜欢短句" @keyup.enter="addPref" />
          <button class="mini-btn" @click="addPref">添加</button>
        </div>
      </div>

      <!-- 弱点与 bias -->
      <div class="ios-card pp-card">
        <div class="pp-label">弱点与 bias（AI 分析）</div>
        <div v-if="!analysis || !((analysis.weaknesses && analysis.weaknesses.length) || (analysis.bias_warnings && analysis.bias_warnings.length))" class="hint-text">完成写作后会基于审查历史自动分析</div>
        <template v-else>
          <div v-for="(w, i) in (analysis.weaknesses || [])" :key="'w' + i" class="analysis-line">⚠️ {{ w }}</div>
          <div v-for="(b, i) in (analysis.bias_warnings || [])" :key="'b' + i" class="analysis-line">🧭 {{ b }}</div>
          <div v-if="analysis.summary" class="analysis-sum">{{ analysis.summary }}</div>
        </template>
      </div>

      <!-- 综合收藏夹 -->
      <div class="ios-card pp-card">
        <div class="pp-label">综合收藏夹 <span class="hint-text">（Ctrl+Shift+K 随时收藏）</span></div>
        <div class="chip-row">
          <span v-for="(t, i) in (profile && profile.favorite_terms) || []" :key="'t' + i" class="chip chip-term">{{ t }}
            <button class="chip-x" @click="removeFav('term', t)">×</button>
          </span>
          <span v-for="(p, i) in (profile && profile.favorite_phrases) || []" :key="'p' + i" class="chip chip-phrase">{{ p }}
            <button class="chip-x" @click="removeFav('phrase', p)">×</button>
          </span>
        </div>
        <div class="inline-add">
          <input class="ios-input" v-model="newFav" placeholder="收藏词汇或句子" @keyup.enter="addFav" />
          <select class="ios-input fav-kind" v-model="favKind"><option value="term">词汇</option><option value="phrase">句子</option></select>
          <button class="mini-btn" @click="addFav">收藏</button>
        </div>
      </div>

      <!-- 项目概览 -->
      <div class="ios-card pp-card">
        <div class="pp-label">项目概览</div>
        <div v-if="!projects.length" class="hint-text">还没有项目</div>
        <div v-for="p in projects" :key="p.id" class="proj-row" @click="openProject(p.id)">
          <span class="proj-icon">📁</span>
          <div class="proj-body">
            <div class="proj-name">{{ p.name }}</div>
            <div class="proj-desc">{{ statusText(p.status) }} · {{ p.questionnaire_summary ? '问卷已总结' : '未完成问卷' }}</div>
          </div>
          <span class="proj-arrow">›</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../../api/client'
import { useProjectStore } from '../../stores/project'
import Button from '../ui/Button.vue'

const projectStore = useProjectStore()
const profile = ref({ preferences: [], favorite_terms: [], favorite_phrases: [] })
const projects = ref([])
const analysis = ref(null)
const loading = ref(true)
const addingPref = ref(false)
const newPref = ref('')
const newFav = ref('')
const favKind = ref('term')

function statusText(s) { return { draft: '草稿', in_progress: '进行中', completed: '已完成', archived: '已归档' }[s] || s }

async function load() {
  loading.value = true
  try {
    const d = await api.get('/profile/overview')
    profile.value = d.profile
    projects.value = d.projects
    analysis.value = d.analysis
  } finally {
    loading.value = false
  }
}

async function addPref() {
  if (!newPref.value.trim()) return
  profile.value.preferences.push(newPref.value.trim())
  newPref.value = ''
  addingPref.value = false
  await api.post('/profile/preferences', { preferences: profile.value.preferences })
}

async function toggleMemory() {
  await api.post('/profile/memory', { enabled: !!profile.value.memory_enabled })
}

async function addFav() {
  if (!newFav.value.trim()) return
  await api.post('/profile/favorites', { kind: favKind.value, value: newFav.value.trim() })
  newFav.value = ''
  await load()
}

async function removeFav(kind, value) {
  await api.del(`/profile/favorites?kind=${kind}&value=${encodeURIComponent(value)}`)
  await load()
}

async function runAnalysis() {
  analysis.value = await api.post('/profile/analyze')
}

async function openProject(id) {
  projectStore.select(await api.get(`/projects/${id}`))
  projectStore.active = await api.get(`/projects/${id}`)
}

onMounted(load)
</script>

<style scoped>
.profile-panel { display: flex; flex-direction: column; gap: 14px; }
.pp-head { display: flex; justify-content: space-between; align-items: center; }
.pp-title { font-size: 18px; font-weight: 700; }
.pp-overview { display: flex; gap: 16px; flex-wrap: wrap; color: var(--color-ink-muted); font-size: 13px; }
.ov-item { display: inline-flex; align-items: center; gap: 4px; }
.pp-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
@media (max-width: 1100px) { .pp-grid { grid-template-columns: 1fr; } }
.pp-card { display: flex; flex-direction: column; gap: 10px; }
.pp-label { font-size: 13px; font-weight: 700; color: var(--color-ink-body); }
.chip-row { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { padding: 4px 12px; border-radius: 999px; font-size: 12px; background: var(--glass-highlight); border: 1px solid var(--glass-border); }
.chip-term { color: var(--color-accent); }
.chip-phrase { color: var(--color-ink-body); }
.chip-x { background: none; border: none; color: var(--color-ink-muted); cursor: pointer; margin-left: 4px; }
.mini-add { background: none; border: 1px dashed var(--glass-border); color: var(--color-ink-muted); border-radius: 999px; width: 24px; height: 24px; cursor: pointer; }
.inline-add { display: flex; gap: 6px; align-items: center; }
.fav-kind { flex: 0 0 80px; }
.mini-btn { border: 1px solid var(--glass-border); background: none; color: var(--color-ink-body); padding: 3px 10px; border-radius: 8px; font-size: 11px; cursor: pointer; font-family: var(--font-ui); }
.mini-btn:hover { border-color: var(--color-accent); }
.analysis-line { font-size: 13px; color: var(--color-ink-body); margin: 3px 0; }
.analysis-sum { font-size: 12px; color: var(--color-ink-muted); margin-top: 6px; }
.hint-text { color: var(--color-ink-muted); font-size: 12px; }
.proj-row { display: flex; gap: 10px; align-items: center; padding: 8px; border-radius: 10px; cursor: pointer; }
.proj-row:hover { background: var(--glass-highlight); }
.proj-icon { font-size: 20px; }
.proj-body { flex: 1; }
.proj-name { font-weight: 600; font-size: 13px; }
.proj-desc { color: var(--color-ink-muted); font-size: 11px; }
.proj-arrow { color: var(--color-ink-muted); }
.mem-toggle { display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 12px; color: var(--color-ink-muted); }
.mem-toggle input { display: none; }
.mem-switch {
  width: 38px; height: 22px; border-radius: 999px; background: var(--glass-highlight);
  border: 1px solid var(--glass-border); position: relative; transition: all 0.25s var(--ease-out-expo); flex-shrink: 0;
}
.mem-switch::after {
  content: ""; position: absolute; top: 2px; left: 2px; width: 16px; height: 16px;
  border-radius: 50%; background: var(--color-ink-muted); transition: all 0.25s var(--ease-out-expo);
}
.mem-toggle.on .mem-switch { background: var(--color-accent); border-color: var(--color-accent); }
.mem-toggle.on .mem-switch::after { left: 18px; background: #1D1D1F; }
:root[data-theme="apple"] .mem-toggle.on .mem-switch::after { background: #fff; }
.mem-toggle.on .mem-text { color: var(--color-ink-body); }
</style>

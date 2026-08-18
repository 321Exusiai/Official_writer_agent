<template>
  <div class="knowledge-panel">
    <div class="k-tabs">
      <button v-for="t in tabs" :key="t.id" class="k-tab" :class="{ on: tab === t.id }" @click="tab = t.id">{{ t.label }}</button>
    </div>

    <p class="hint-text">内置知识库 · 导入外部资料请到「我的 → 项目档案」</p>

    <input v-if="['exemplars', 'terminology', 'policy'].includes(tab)" v-model="query" class="ios-input" placeholder="搜索…" />

    <!-- 范文 -->
    <div v-if="tab === 'exemplars'" class="k-list">
      <div v-for="e in filteredExemplars" :key="e.id" class="k-item" @click="toggle(e.id)">
        <div class="k-title">《{{ e.title }}》<span class="k-meta">{{ e.source }} · {{ e.doc_type }}</span></div>
        <div v-if="open === e.id" class="k-detail">
          <div class="k-label">结构骨架</div>
          <div class="k-text">{{ e.structure_skeleton }}</div>
          <div class="k-label">关键句式</div>
          <div class="k-text">{{ (e.key_sentences || []).slice(0, 3).join('；') }}</div>
        </div>
      </div>
      <div v-if="!filteredExemplars.length" class="hint-text">无匹配范文</div>
    </div>

    <!-- 术语 -->
    <div v-else-if="tab === 'terminology'" class="k-list">
      <div v-for="(t, name) in filteredTerms" :key="name" class="k-item" @click="toggle(name)">
        <div class="k-title">{{ name }}<span class="k-meta">{{ t.category }}</span></div>
        <div v-if="open === name" class="k-detail">
          <div class="k-text">{{ t.definition }}</div>
          <div class="k-label">常见误用</div>
          <div class="k-text">{{ t.common_misuse }}</div>
        </div>
      </div>
    </div>

    <!-- 过渡句 -->
    <div v-else-if="tab === 'transitions'" class="k-list">
      <div v-for="(phrases, style) in transitions" :key="style" class="k-item">
        <div class="k-title">{{ style }}</div>
        <div class="k-text">{{ phrases.join(' / ') }}</div>
      </div>
    </div>

    <!-- 格式化用语 -->
    <div v-else-if="tab === 'formulaic'" class="k-list">
      <div v-for="(v, doc) in formulaic" :key="doc" class="k-item">
        <div class="k-title">{{ doc }}</div>
        <div class="k-text">{{ Object.values(v).filter(x => typeof x === 'string').slice(0, 3).join('；') }}</div>
      </div>
    </div>

    <!-- 政策/讲话/规范表述 -->
    <div v-else-if="tab === 'policy'" class="k-list">
      <div v-for="p in filteredPolicies" :key="p.text" class="k-item" @click="toggle(p.text)">
        <div class="k-title">{{ p.text.slice(0, 40) }}<span class="k-meta">{{ p.topic }}</span></div>
        <div v-if="open === p.text" class="k-detail">
          <div class="k-label">{{ p.category === 'policy' ? '政策表述' : p.category === 'quote' ? '讲话金句' : '规范用语' }}</div>
          <div class="k-text">{{ p.source }}</div>
          <div class="k-label">用法</div>
          <div class="k-text">{{ p.usage }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../../api/client'
import { useProjectStore } from '../../stores/project'

const projectStore = useProjectStore()

const tabs = [
  { id: 'exemplars', label: '范文' },
  { id: 'terminology', label: '术语' },
  { id: 'policy', label: '政策讲话' },
  { id: 'transitions', label: '过渡句' },
  { id: 'formulaic', label: '格式化' },
]
const tab = ref('exemplars')
const query = ref('')
const open = ref('')
const exemplars = ref([])
const terms = ref({})
const transitions = ref({})
const formulaic = ref({})
const policies = ref([])

const filteredPolicies = computed(() => {
  const kw = query.value
  if (!kw) return policies.value
  return policies.value.filter((p) => (p.text + p.topic).includes(kw))
})

const filteredExemplars = computed(() => {
  const kw = query.value.toLowerCase()
  if (!kw) return exemplars.value
  return exemplars.value.filter((e) => (e.title + e.source + e.doc_type).toLowerCase().includes(kw))
})
const filteredTerms = computed(() => {
  const kw = query.value
  if (!kw) return terms.value
  return Object.fromEntries(Object.entries(terms.value).filter(([k]) => k.includes(kw)))
})

function toggle(id) { open.value = open.value === id ? '' : id }

onMounted(async () => {
  exemplars.value = await api.get('/knowledge/exemplars')
  terms.value = await api.get('/knowledge/terminology')
  transitions.value = await api.get('/knowledge/transitions')
  formulaic.value = await api.get('/knowledge/formulaic')
  policies.value = await api.get('/knowledge/policy')
})
</script>

<style scoped>
.knowledge-panel { display: flex; flex-direction: column; gap: 10px; }
.k-tabs { display: flex; gap: 4px; }
.k-tab {
  flex: 1; border: 1px solid var(--glass-border); background: none;
  color: var(--color-ink-muted); padding: 5px 0; border-radius: 8px;
  font-size: 12px; font-weight: 600; cursor: pointer; font-family: var(--font-ui);
}
.k-tab.on { background: var(--color-accent); color: #1D1D1F; border-color: transparent; }
.k-list { display: flex; flex-direction: column; gap: 8px; max-height: 60vh; overflow-y: auto; }
.k-item {
  padding: 10px 12px; border-radius: 12px; cursor: pointer;
  background: var(--glass-highlight); border: 1px solid var(--glass-border);
  transition: border-color 0.2s;
}
.k-item:hover { border-color: var(--color-accent-focus); }
.k-title { font-weight: 600; font-size: 13px; }
.k-meta { color: var(--color-ink-muted); font-size: 11px; margin-left: 6px; font-weight: 400; }
.k-detail { margin-top: 8px; }
.k-label { color: var(--color-accent); font-size: 11px; margin: 6px 0 2px; }
.k-text { color: var(--color-ink-body); font-size: 12px; line-height: 1.6; }
.hint-text { color: var(--color-ink-muted); font-size: 12px; }
.hint-text.ok { color: #4ADE80; }
.import-btn {
  border: 1px dashed var(--glass-border); background: var(--glass-highlight);
  color: var(--color-ink-body); padding: 8px; border-radius: 12px;
  font-size: 13px; font-weight: 600; cursor: pointer; font-family: var(--font-ui);
  transition: border-color 0.2s;
}
.import-btn:hover { border-color: var(--color-accent); }
.import-box { display: flex; flex-direction: column; gap: 8px; }
.import-row { display: flex; gap: 8px; align-items: center; }
.import-divider { text-align: center; color: var(--color-ink-muted); font-size: 11px; }
.ref-del {
  margin-top: 8px; border: none; background: var(--color-danger-soft);
  color: var(--color-danger); padding: 4px 10px; border-radius: 8px;
  font-size: 12px; cursor: pointer; font-family: var(--font-ui);
}
</style>

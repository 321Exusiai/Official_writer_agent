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

    <!-- 单位专有知识库（动态扩充） -->
    <div v-else-if="tab === 'custom'" class="k-list">
      <div class="custom-add-box">
        <input v-model="newCustom.title" class="ios-input" placeholder="条目标题（如：本厅2026数字化转型工作要点）" />
        <textarea v-model="newCustom.content" class="ios-input" rows="3" placeholder="政策表述/领导讲话/规范要求正文…" />
        <div class="add-row">
          <select v-model="newCustom.category" class="ios-input cat-select">
            <option value="policy">单位政策</option>
            <option value="speech">领导讲话</option>
            <option value="rule">工作规范</option>
          </select>
          <input v-model="newCustom.source" class="ios-input" placeholder="出处/文件号" />
          <button class="add-btn" :disabled="!newCustom.title || !newCustom.content" @click="addCustomItem">➕ 添加到单位库</button>
        </div>
      </div>
      <div v-for="c in customItems" :key="c.id" class="k-item">
        <div class="k-title flex-between">
          <span>{{ c.title }}<span class="k-meta">{{ c.category }} · {{ c.source || '单位专有' }}</span></span>
          <button class="del-btn" @click.stop="deleteCustomItem(c.id)">删除</button>
        </div>
        <div class="k-text mt-1">{{ c.content }}</div>
      </div>
      <div v-if="!customItems.length" class="hint-text">暂无单位专有知识，上方输入即可沉淀</div>
    </div>

    <!-- 公文排版模板库 -->
    <div v-else-if="tab === 'templates'" class="k-list">
      <div v-for="t in templates" :key="t.id" class="k-item">
        <div class="k-title">{{ t.name }}<span class="k-meta">{{ t.is_builtin ? '国家标准' : '自定义模板' }}</span></div>
        <div class="k-text">字体：{{ t.body_font }} {{ t.body_font_size }}pt · 行距：{{ t.line_spacing_pt }}pt · 缩进：{{ t.indent_chars }}字符</div>
        <div v-if="t.header_text" class="k-meta text-red">红头标头：{{ t.header_text }}（{{ t.doc_code || '发文字号' }}）</div>
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
  { id: 'custom', label: '🏢 单位专有库' },
  { id: 'templates', label: '📄 排版模板' },
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

const customItems = ref([])
const templates = ref([])
const newCustom = ref({
  title: '',
  content: '',
  category: 'policy',
  source: '',
})

async function loadCustom() {
  try {
    customItems.value = await api.get('/knowledge/custom')
  } catch { /* ignore */ }
}

async function loadTemplates() {
  try {
    templates.value = await api.get('/knowledge/templates')
  } catch { /* ignore */ }
}

async function addCustomItem() {
  if (!newCustom.value.title || !newCustom.value.content) return
  await api.post('/knowledge/custom', newCustom.value)
  newCustom.value.title = ''
  newCustom.value.content = ''
  newCustom.value.source = ''
  await loadCustom()
}

async function deleteCustomItem(id) {
  await api.delete(`/knowledge/custom/${id}`)
  await loadCustom()
}

function toggle(id) { open.value = open.value === id ? '' : id }

onMounted(async () => {
  exemplars.value = await api.get('/knowledge/exemplars')
  terms.value = await api.get('/knowledge/terminology')
  transitions.value = await api.get('/knowledge/transitions')
  formulaic.value = await api.get('/knowledge/formulaic')
  policies.value = await api.get('/knowledge/policy')
  await loadCustom()
  await loadTemplates()
})
</script>

<style scoped>
.knowledge-panel { display: flex; flex-direction: column; gap: 10px; }
.k-tabs { display: flex; gap: 4px; flex-wrap: wrap; }
.k-tab {
  flex: 1; min-width: 65px; border: 1px solid var(--glass-border); background: none;
  color: var(--color-ink-muted); padding: 5px 4px; border-radius: 8px;
  font-size: 11px; font-weight: 600; cursor: pointer; font-family: var(--font-ui);
  text-align: center;
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

.custom-add-box {
  display: flex; flex-direction: column; gap: 6px; padding: 10px;
  border-radius: 12px; background: var(--glass-highlight); border: 1px dashed var(--color-accent);
}
.add-row { display: flex; gap: 6px; align-items: center; }
.cat-select { width: 90px; }
.add-btn {
  padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 700;
  background: var(--color-accent); color: #1D1D1F; border: none; cursor: pointer;
  white-space: nowrap;
}
.add-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.flex-between { display: flex; justify-content: space-between; align-items: center; }
.del-btn {
  border: none; background: rgba(255, 107, 94, 0.15); color: #dc2626;
  padding: 2px 8px; border-radius: 6px; font-size: 11px; cursor: pointer;
}
.text-red { color: #da291c; }
.mt-1 { margin-top: 4px; }
</style>

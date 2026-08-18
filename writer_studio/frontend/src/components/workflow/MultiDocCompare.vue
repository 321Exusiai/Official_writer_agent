<template>
  <div class="md-compare">
    <div class="mc-head">
      <span class="mc-label">版本对比</span>
      <select class="ios-input mc-select" v-model="aId">
        <option v-for="v in versions" :key="v.doc_type" :value="v.doc_type">{{ v.doc_type_name }}</option>
      </select>
      <span class="mc-vs">↔</span>
      <select class="ios-input mc-select" v-model="bId">
        <option v-for="v in versions" :key="v.doc_type" :value="v.doc_type">{{ v.doc_type_name }}</option>
      </select>
    </div>
    <div class="mc-panes">
      <div class="mc-pane">
        <div class="mc-pane-title">{{ aTitle }}（{{ aCount }}字）</div>
        <div class="mc-lines">
          <div v-for="(row, i) in rows" :key="i" class="mc-line" :class="row.type === 'diff' ? 'diff-a' : ''">
            {{ row.a }}
          </div>
        </div>
      </div>
      <div class="mc-pane">
        <div class="mc-pane-title">{{ bTitle }}（{{ bCount }}字）</div>
        <div class="mc-lines">
          <div v-for="(row, i) in rows" :key="i" class="mc-line" :class="row.type === 'diff' ? 'diff-b' : ''">
            {{ row.b }}
          </div>
        </div>
      </div>
    </div>
    <div class="mc-legend">
      <span class="lg lg-a">● 仅 A 有</span>
      <span class="lg lg-b">● 仅 B 有</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({ versions: { type: Array, default: () => [] } })

const aId = ref('')
const bId = ref('')

watch(
  () => props.versions,
  (v) => {
    if (v.length >= 2 && !aId.value) {
      aId.value = v[0].doc_type
      bId.value = v[1].doc_type
    }
  },
  { immediate: true },
)

function getVersion(id) {
  return props.versions.find((v) => v.doc_type === id) || props.versions[0] || { content: '', doc_type_name: '', word_count: 0 }
}

const aTitle = computed(() => getVersion(aId.value).doc_type_name || '')
const bTitle = computed(() => getVersion(bId.value).doc_type_name || '')
const aCount = computed(() => getVersion(aId.value).word_count || 0)
const bCount = computed(() => getVersion(bId.value).word_count || 0)

const rows = computed(() => {
  const a = (getVersion(aId.value).content || '').split('\n')
  const b = (getVersion(bId.value).content || '').split('\n')
  const max = Math.max(a.length, b.length)
  const out = []
  for (let i = 0; i < max; i++) {
    const la = a[i] || ''
    const lb = b[i] || ''
    out.push(la === lb ? { type: 'same', a: la, b: lb } : { type: 'diff', a: la, b: lb })
  }
  return out
})
</script>

<style scoped>
.md-compare { display: flex; flex-direction: column; gap: 10px; }
.mc-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.mc-label { font-size: 13px; font-weight: 700; }
.mc-select { flex: 1; min-width: 90px; }
.mc-vs { color: var(--color-ink-muted); }
.mc-panes { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.mc-pane { border: 1px solid var(--glass-border); border-radius: 12px; overflow: hidden; background: rgba(0,0,0,0.15); }
.mc-pane-title { font-size: 12px; font-weight: 700; padding: 8px 10px; border-bottom: 1px solid var(--glass-border); }
.mc-lines { max-height: 320px; overflow-y: auto; padding: 6px 10px; }
.mc-line { font-size: 12px; line-height: 1.7; white-space: pre-wrap; padding: 1px 4px; border-radius: 3px; color: var(--color-ink-body); }
.diff-a { background: rgba(255, 107, 94, 0.25); color: var(--color-danger); }
.diff-b { background: rgba(74, 222, 128, 0.2); color: #4ADE80; }
.mc-legend { display: flex; gap: 14px; font-size: 11px; color: var(--color-ink-muted); }
.lg-a { color: var(--color-danger); }
.lg-b { color: #4ADE80; }
</style>

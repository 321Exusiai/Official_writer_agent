<template>
  <Teleport to="body">
    <div v-if="visible" class="fav-overlay" @click.self="close">
      <div class="fav-panel ios-card animate-enter">
        <div class="fav-head">
          <h4 class="fav-title">⚡ 快捷收藏</h4>
          <button class="fav-close" @click="close">×</button>
        </div>
        <p v-if="selectedText" class="selected-text">已选中：<span class="sel">{{ selectedText.slice(0, 60) }}</span></p>
        <textarea class="ios-input" v-model="value" rows="2" placeholder="要收藏的词汇或句子（自动带入选中文本）" />
        <div class="fav-kind">
          <label class="kind-opt"><input type="radio" value="term" v-model="kind" /> 词汇</label>
          <label class="kind-opt"><input type="radio" value="phrase" v-model="kind" /> 句子</label>
        </div>
        <select class="ios-input" v-model="target">
          <option value="">📌 综合收藏夹</option>
          <option v-for="p in projects" :key="p.id" :value="p.id">📁 {{ p.name }}</option>
        </select>
        <div class="fav-actions">
          <Button @click="save">添加收藏</Button>
          <Button variant="secondary" @click="close">取消</Button>
        </div>
        <p v-if="msg" class="msg" :class="{ ok: msgOk }">{{ msg }}</p>
        <p class="hint-text">快捷键 Ctrl+Shift+K 随时呼出</p>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref } from 'vue'
import { api } from '../../api/client'
import { useProjectStore } from '../../stores/project'
import Button from '../ui/Button.vue'

const projectStore = useProjectStore()
const visible = ref(false)
const value = ref('')
const kind = ref('term')
const target = ref('')
const projects = ref([])
const selectedText = ref('')
const msg = ref('')
const msgOk = ref(false)

function open() {
  // 自动带入页面选中文本
  const sel = (window.getSelection() && window.getSelection().toString()) || ''
  selectedText.value = sel.trim()
  value.value = sel.trim()
  kind.value = sel.trim().length > 12 ? 'phrase' : 'term'
  target.value = projectStore.active ? projectStore.active.id : ''
  projects.value = projectStore.projects
  msg.value = ''
  visible.value = true
}

function close() { visible.value = false }

async function save() {
  if (!value.value.trim()) return
  try {
    const r = await api.post('/profile/favorites', { kind: kind.value, value: value.value.trim(), project_id: target.value })
    msg.value = `已收藏${kind.value === 'term' ? '词汇' : '句子'}${target.value ? '到项目' : '到综合收藏夹'}`
    msgOk.value = true
    value.value = ''
    if (target.value) {
      const p = await api.get(`/projects/${target.value}`)
      projectStore.projects = projectStore.projects.map((x) => (x.id === p.id ? p : x))
    }
    setTimeout(close, 800)
  } catch (e) {
    msg.value = '收藏失败：' + e.message
    msgOk.value = false
  }
}

defineExpose({ open, close })
</script>

<style scoped>
.fav-overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0, 0, 0, 0.4); backdrop-filter: blur(4px);
  display: flex; align-items: flex-start; justify-content: flex-end;
  padding: 80px 24px 0 0;
}
.fav-panel { width: 360px; display: flex; flex-direction: column; gap: 10px; padding: 18px; }
.fav-head { display: flex; justify-content: space-between; align-items: center; }
.fav-title { font-size: 15px; font-weight: 700; }
.fav-close { background: none; border: none; color: var(--color-ink-muted); font-size: 20px; cursor: pointer; }
.selected-text { font-size: 12px; color: var(--color-ink-muted); }
.sel { color: var(--color-accent); }
.fav-kind { display: flex; gap: 14px; font-size: 13px; }
.kind-opt { display: flex; align-items: center; gap: 4px; cursor: pointer; }
.fav-actions { display: flex; gap: 8px; }
.msg { font-size: 13px; color: var(--color-danger); }
.msg.ok { color: #4ADE80; }
.hint-text { color: var(--color-ink-muted); font-size: 11px; text-align: right; }
</style>

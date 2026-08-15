<template>
  <div class="project-browser">
    <div class="browser-toolbar">
      <input class="ios-input" v-model="query" placeholder="搜索项目…" />
      <Button @click="showCreate = !showCreate">＋ 新建</Button>
    </div>

    <div v-if="showCreate" class="ios-card animate-enter create-box">
      <input class="ios-input" v-model="newName" placeholder="项目名称（如：智能研学总结报告）" @keyup.enter="create" />
      <input class="ios-input" v-model="newDesc" placeholder="描述（可选）" @keyup.enter="create" />
      <div class="create-actions">
        <Button @click="create">保存</Button>
        <Button variant="secondary" @click="showCreate = false">取消</Button>
      </div>
    </div>

    <div v-if="!filtered.length" class="empty-state">
      <div style="font-size: 40px">📂</div>
      <div>还没有项目，点击「＋ 新建」开始写作</div>
    </div>

    <div class="browser-grid">
      <div
        v-for="p in filtered"
        :key="p.id"
        class="folder"
        :class="{ active: active && active.id === p.id }"
        @click="select(p)"
      >
        <div class="folder-top">
          <span class="folder-icon">📁</span>
          <button class="folder-del" title="删除" @click.stop="remove(p)">×</button>
        </div>
        <div class="folder-name">{{ p.name }}</div>
        <div class="folder-desc">{{ p.description || '无描述' }}</div>
        <div class="folder-meta">
          <span :class="'badge badge-' + (p.status === 'completed' ? 'llm' : 'rule')">{{ statusText(p.status) }}</span>
          <span class="folder-date">{{ (p.updated_at || '').slice(0, 16) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useProjectStore } from '../../stores/project'
import Button from '../ui/Button.vue'

const store = useProjectStore()
const query = ref('')
const showCreate = ref(false)
const newName = ref('')
const newDesc = ref('')

const filtered = computed(() => store.filtered(query.value))
const active = computed(() => store.active)

function statusText(s) {
  return { draft: '草稿', in_progress: '进行中', completed: '已完成', archived: '已归档' }[s] || s
}

async function create() {
  if (!newName.value.trim()) return
  await store.create(newName.value.trim(), newDesc.value.trim())
  newName.value = ''
  newDesc.value = ''
  showCreate.value = false
}

function select(p) { store.select(p) }
function remove(p) { store.remove(p.id) }

onMounted(() => store.fetch())
</script>

<style scoped>
.browser-toolbar { display: flex; gap: 8px; margin-bottom: 12px; }
.create-box { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.create-actions { display: flex; gap: 8px; }
.browser-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
.folder {
  background: var(--glass-highlight);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  padding: 14px;
  cursor: pointer;
  transition: all 0.2s var(--ease-out-expo);
}
.folder:hover { border-color: var(--color-accent-focus); transform: translateY(-2px); }
.folder.active { border-color: var(--color-accent); }
.folder-top { display: flex; justify-content: space-between; align-items: center; }
.folder-icon { font-size: 28px; }
.folder-del {
  background: none; border: none; color: var(--color-ink-muted);
  font-size: 18px; cursor: pointer; opacity: 0; transition: opacity 0.2s;
}
.folder:hover .folder-del { opacity: 1; }
.folder-del:hover { color: var(--color-danger); }
.folder-name { font-weight: 600; margin-top: 6px; font-size: 14px; word-break: break-all; }
.folder-desc { color: var(--color-ink-muted); font-size: 12px; margin-top: 4px; min-height: 16px; }
.folder-meta { display: flex; justify-content: space-between; align-items: center; margin-top: 10px; }
.folder-date { font-size: 11px; color: var(--color-ink-muted); }
</style>

<template>
  <div class="config-panel">
    <h3 class="config-title">API 配置</h3>
    <p class="hint-text">支持多个 API 配置，一键切换启用；未启用 LLM 时系统走规则模式并明确标注。</p>

    <!-- 工具行 -->
    <div class="toolbar">
      <Button variant="secondary" @click="startNew">＋ 新增配置</Button>
      <select class="ios-input tpl-select" v-model="tplKey" @change="applyTemplate">
        <option value="">快捷模板…</option>
        <option v-for="(t, k) in templates" :key="k" :value="k">{{ t.name }}</option>
      </select>
    </div>

    <!-- 配置列表 -->
    <div class="cfg-list">
      <div
        v-for="(c, i) in configs"
        :key="i"
        class="cfg-card"
        :class="{ active: i === activeIndex, editing: i === editingIndex }"
        @click="startEdit(i)"
      >
        <div class="cfg-head">
          <span class="cfg-name">{{ c.name }}</span>
          <span class="badge" :class="i === activeIndex ? 'badge-llm' : 'badge-rule'">{{ i === activeIndex ? '启用中' : '未启用' }}</span>
        </div>
        <div class="cfg-meta">{{ providerLabel(c.provider) }} · {{ c.model || '未填模型' }}</div>
        <div class="cfg-actions">
          <button class="mini-btn" :disabled="i === activeIndex" @click.stop="switchTo(i)">设为启用</button>
          <button class="mini-btn danger" @click.stop="remove(i)">删除</button>
        </div>
      </div>
    </div>

    <!-- 编辑面板 -->
    <div v-if="editingIndex >= -1" class="ios-card edit-box animate-enter">
      <h4 class="edit-title">{{ editingIndex === -1 ? '新增配置' : '编辑配置' }}</h4>
      <input class="ios-input" v-model="form.name" placeholder="配置名称（如 DeepSeek）" />
      <input class="ios-input" v-model="form.api_base" placeholder="API Base URL（如 https://api.deepseek.com/v1）" />
      <input class="ios-input" v-model="form.api_key" type="password" placeholder="API Key（留空保留原值）" />
      <input class="ios-input" v-model="form.model" placeholder="模型名（如 deepseek-chat）" />
      <div class="config-row">
        <label class="config-label">温度</label>
        <input class="ios-input" v-model.number="form.temperature" type="number" step="0.1" min="0" max="2" />
      </div>
      <div class="config-row">
        <label class="config-label">最大 Token</label>
        <input class="ios-input" v-model.number="form.max_tokens" type="number" step="500" min="500" max="32000" />
      </div>
      <label class="toggle-row">
        <input type="checkbox" v-model="form.enabled" />
        <span>启用该配置</span>
      </label>
      <div class="config-divider">联网搜索（可选）</div>
      <select class="ios-input" v-model="form.search_provider">
        <option value="tavily">Tavily</option>
        <option value="boya">博查 Boya</option>
      </select>
      <input class="ios-input" v-model="form.search_api_key" type="password" placeholder="搜索 API Key（可选）" />
      <div class="actions">
        <Button @click="save">保存</Button>
        <Button variant="secondary" @click="test">测试连接</Button>
      </div>
      <p v-if="msg" class="msg" :class="{ ok: msgOk }">{{ msg }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../../api/client'
import Button from '../ui/Button.vue'

const configs = ref([])
const activeIndex = ref(-1)
const templates = ref({})
const tplKey = ref('')
const editingIndex = ref(-2) // -2 不编辑 / -1 新建 / >=0 编辑第 i 个
const form = ref(emptyForm())
const msg = ref('')
const msgOk = ref(false)

function emptyForm() {
  return { name: '', provider: 'openai', api_base: '', api_key: '', model: '', temperature: 0.7, max_tokens: 8000, enabled: false, search_provider: 'tavily', search_api_key: '' }
}

function providerLabel(p) {
  return { deepseek: 'DeepSeek', qwen: '通义千问', openai: 'OpenAI', zhipu: '智谱', anthropic: 'Anthropic', ollama: '本地 Ollama' }[p] || p
}

async function load() {
  const d = await api.get('/config')
  configs.value = d.configs
  activeIndex.value = d.active_index
  templates.value = d.templates || {}
}

function startNew() {
  editingIndex.value = -1
  form.value = emptyForm()
  msg.value = ''
}

function startEdit(i) {
  editingIndex.value = i
  const c = configs.value[i]
  form.value = { ...emptyForm(), ...c }
  msg.value = ''
}

function applyTemplate() {
  if (!tplKey.value) return
  const t = templates.value[tplKey.value]
  if (!t) return
  form.value = { ...emptyForm(), ...t, name: t.name }
  if (editingIndex.value < -1) editingIndex.value = -1
  tplKey.value = ''
}

async function save() {
  try {
    const r = await api.post('/config/save', { ...form.value, index: editingIndex.value })
    msg.value = '已保存'
    msgOk.value = true
    editingIndex.value = -2
    await load()
  } catch (e) {
    msg.value = '保存失败：' + e.message
    msgOk.value = false
  }
}

async function remove(i) {
  const r = await api.post('/config/delete', { index: i })
  if (r.message) { msg.value = r.message; msgOk.value = false } else { msg.value = '' }
  await load()
}

async function switchTo(i) {
  await api.post('/config/switch', { index: i })
  await load()
}

async function test() {
  msg.value = '测试中…'
  msgOk.value = false
  try {
    const r = await api.post('/config/test', form.value)
    msg.value = r.message
    msgOk.value = r.ok
  } catch (e) {
    msg.value = '测试失败：' + e.message
    msgOk.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.config-panel { display: flex; flex-direction: column; gap: 10px; }
.config-title { font-size: 15px; font-weight: 700; }
.hint-text { color: var(--color-ink-muted); font-size: 12px; line-height: 1.6; }
.toolbar { display: flex; gap: 8px; }
.tpl-select { flex: 1; }
.cfg-list { display: flex; flex-direction: column; gap: 8px; }
.cfg-card {
  padding: 12px; border-radius: 14px; cursor: pointer;
  background: var(--glass-highlight); border: 1px solid var(--glass-border);
  transition: border-color 0.2s;
}
.cfg-card:hover { border-color: var(--color-accent-focus); }
.cfg-card.active { border-color: var(--color-accent); }
.cfg-card.editing { border-color: var(--color-accent); box-shadow: 0 0 0 3px var(--color-accent-focus); }
.cfg-head { display: flex; justify-content: space-between; align-items: center; }
.cfg-name { font-weight: 700; font-size: 14px; }
.cfg-meta { color: var(--color-ink-muted); font-size: 12px; margin-top: 4px; }
.cfg-actions { display: flex; gap: 6px; margin-top: 8px; }
.mini-btn {
  border: 1px solid var(--glass-border); background: none; color: var(--color-ink-body);
  padding: 3px 10px; border-radius: 8px; font-size: 11px; cursor: pointer; font-family: var(--font-ui);
}
.mini-btn:hover { border-color: var(--color-accent); }
.mini-btn.danger { color: var(--color-danger); }
.mini-btn.danger:hover { border-color: var(--color-danger); }
.mini-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.edit-box { display: flex; flex-direction: column; gap: 8px; }
.edit-title { font-size: 14px; font-weight: 700; }
.config-row { display: flex; align-items: center; gap: 10px; }
.config-label { font-size: 13px; color: var(--color-ink-muted); width: 80px; flex-shrink: 0; }
.toggle-row { display: flex; align-items: center; gap: 8px; font-size: 14px; cursor: pointer; }
.config-divider { margin-top: 4px; padding-top: 8px; border-top: 1px solid var(--glass-border); font-size: 13px; font-weight: 700; color: var(--color-ink-body); }
.actions { display: flex; gap: 8px; }
.msg { font-size: 13px; color: var(--color-danger); }
.msg.ok { color: #4ADE80; }
</style>

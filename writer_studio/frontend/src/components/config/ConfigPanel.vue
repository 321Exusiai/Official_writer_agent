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

    <!-- 辅助轨道（Copilot / 随叫随到助手） -->
    <div class="ios-card edit-box assistant-box">
      <div class="assistant-head">
        <h4 class="edit-title">⚙️ 辅助轨道 API 配置</h4>
        <select class="ios-input tpl-select-mini" v-model="assistantTplKey" @change="applyAssistantTemplate">
          <option value="">快捷模板…</option>
          <option value="zhipu">智谱 GLM-4-Flash（免费推荐）</option>
          <option value="deepseek">DeepSeek Chat</option>
          <option value="qwen">通义千问 Turbo</option>
          <option value="openai">OpenAI GPT-4o-mini</option>
          <option value="ollama">本地 Ollama (qwen2.5)</option>
        </select>
      </div>
      <p class="hint-text">负责资料整理、全局搜索、画像分析、备忘录置顶、国标速查等随叫随到轻任务；<b>文章起草与深度审查走上方主 API</b>。</p>
      
      <input class="ios-input" v-model="assistant.name" placeholder="辅助配置名称（如 智谱 GLM-4-Flash）" />
      <div class="config-row">
        <label class="config-label">供应商</label>
        <select class="ios-input" v-model="assistant.provider">
          <option value="zhipu">智谱 GLM</option>
          <option value="deepseek">DeepSeek</option>
          <option value="qwen">通义千问</option>
          <option value="openai">OpenAI</option>
          <option value="ollama">本地 Ollama</option>
        </select>
      </div>
      <input class="ios-input" v-model="assistant.api_base" placeholder="API Base URL（如 https://open.bigmodel.cn/api/paas/v4）" />
      <input class="ios-input" v-model="assistant.api_key" type="password" placeholder="API Key（留空保留原值）" />
      <input class="ios-input" v-model="assistant.model" placeholder="模型名（如 glm-4-flash / deepseek-chat）" />
      
      <div class="config-row">
        <label class="config-label">温度</label>
        <input class="ios-input" v-model.number="assistant.temperature" type="number" step="0.1" min="0" max="2" />
      </div>
      <div class="config-row">
        <label class="config-label">最大 Token</label>
        <input class="ios-input" v-model.number="assistant.max_tokens" type="number" step="500" min="500" max="16000" />
      </div>

      <label class="toggle-row">
        <input type="checkbox" v-model="assistant.enabled" />
        <span>启用辅助轨道</span>
      </label>

      <div class="actions">
        <Button @click="saveAssistant">保存辅助配置</Button>
        <Button variant="secondary" @click="testAssistant">测试连接</Button>
      </div>
      <p v-if="assistantMsg" class="msg" :class="{ ok: assistantOk }">{{ assistantMsg }}</p>
    </div>

    <!-- 备份与恢复 -->
    <div class="ios-card edit-box backup-box">
      <h4 class="edit-title">💾 备份与恢复</h4>
      <p class="hint-text">一键导出全部数据（项目、画像、参考文本、配置与密钥），换机或误操作后可完整恢复。</p>
      <div class="actions">
        <Button variant="secondary" @click="exportBackup">导出备份</Button>
        <Button variant="secondary" @click="pickBackup">导入备份</Button>
        <input ref="fileInput" type="file" accept=".json" style="display:none" @change="importBackup" />
      </div>
      <p v-if="backupMsg" class="msg" :class="{ ok: backupOk }">{{ backupMsg }}</p>
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
const assistantTplKey = ref('')
const editingIndex = ref(-2) // -2 不编辑 / -1 新建 / >=0 编辑第 i 个
const form = ref(emptyForm())
const msg = ref('')
const msgOk = ref(false)
const assistant = ref({
  name: '智谱 GLM-4-Flash',
  enabled: false,
  provider: 'zhipu',
  api_base: 'https://open.bigmodel.cn/api/paas/v4',
  api_key: '',
  model: 'glm-4-flash',
  temperature: 0.3,
  max_tokens: 2000,
})
const assistantMsg = ref('')
const assistantOk = ref(false)
const fileInput = ref(null)
const backupMsg = ref('')
const backupOk = ref(false)

const ASSISTANT_PRESETS = {
  zhipu: { name: '智谱 GLM-4-Flash (免费)', provider: 'zhipu', api_base: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-flash', temperature: 0.3, max_tokens: 2000 },
  deepseek: { name: 'DeepSeek Chat', provider: 'deepseek', api_base: 'https://api.deepseek.com/v1', model: 'deepseek-chat', temperature: 0.3, max_tokens: 2000 },
  qwen: { name: '通义千问 Turbo', provider: 'qwen', api_base: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-turbo', temperature: 0.3, max_tokens: 2000 },
  openai: { name: 'OpenAI GPT-4o-mini', provider: 'openai', api_base: 'https://api.openai.com/v1', model: 'gpt-4o-mini', temperature: 0.3, max_tokens: 2000 },
  ollama: { name: '本地 Ollama (qwen2.5)', provider: 'ollama', api_base: 'http://localhost:11434/v1', model: 'qwen2.5:7b', temperature: 0.3, max_tokens: 2000 },
}

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
  if (d.assistant) assistant.value = { ...assistant.value, ...d.assistant }
}

function applyAssistantTemplate() {
  if (!assistantTplKey.value) return
  const t = ASSISTANT_PRESETS[assistantTplKey.value]
  if (!t) return
  const curKey = assistant.value.api_key
  const curEnabled = assistant.value.enabled
  assistant.value = { ...assistant.value, ...t, api_key: curKey, enabled: curEnabled }
  assistantTplKey.value = ''
}

async function saveAssistant() {
  try {
    await api.post('/config/assistant', assistant.value)
    assistantMsg.value = '辅助轨道配置已保存'
    assistantOk.value = true
    await load()
  } catch (e) {
    assistantMsg.value = '保存失败：' + e.message
    assistantOk.value = false
  }
}

async function testAssistant() {
  assistantMsg.value = '测试连接中…'
  assistantOk.value = false
  try {
    const r = await api.post('/config/assistant/test', assistant.value)
    assistantMsg.value = r.message
    assistantOk.value = r.ok
  } catch (e) {
    assistantMsg.value = '测试失败：' + e.message
    assistantOk.value = false
  }
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
    await api.post('/config/save', { ...form.value, index: editingIndex.value })
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

async function exportBackup() {
  try {
    const data = await api.get('/backup/export')
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `writer_studio_backup_${(data.exported_at || '').replace(/[-: ]/g, '')}.json`
    a.click()
    URL.revokeObjectURL(a.href)
    backupMsg.value = '备份已导出（含项目、画像、配置与密钥）'
    backupOk.value = true
  } catch (e) {
    backupMsg.value = '导出失败：' + e.message
    backupOk.value = false
  }
}

function pickBackup() {
  if (fileInput.value) fileInput.value.click()
}

async function importBackup(e) {
  const file = e.target.files && e.target.files[0]
  e.target.value = ''
  if (!file) return
  if (!window.confirm('导入备份将覆盖当前全部数据（项目、画像、配置）。确定继续？')) return
  try {
    const text = await file.text()
    const data = JSON.parse(text)
    const r = await api.post('/backup/import', { backup: data })
    backupMsg.value = `已恢复 ${r.files.length} 个数据文件`
    backupOk.value = true
  } catch (err) {
    backupMsg.value = '导入失败：' + err.message
    backupOk.value = false
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
.tpl-select-mini { width: 170px; font-size: 12px; padding: 4px 8px; }
.assistant-head { display: flex; justify-content: space-between; align-items: center; }
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
.assistant-box { margin-top: 4px; border-color: var(--color-accent-focus); }
.backup-box { margin-top: 4px; }
.edit-title { font-size: 14px; font-weight: 700; }
.config-row { display: flex; align-items: center; gap: 10px; }
.config-label { font-size: 13px; color: var(--color-ink-muted); width: 80px; flex-shrink: 0; }
.toggle-row { display: flex; align-items: center; gap: 8px; font-size: 14px; cursor: pointer; }
.config-divider { margin-top: 4px; padding-top: 8px; border-top: 1px solid var(--glass-border); font-size: 13px; font-weight: 700; color: var(--color-ink-body); }
.actions { display: flex; gap: 8px; }
.msg { font-size: 13px; color: var(--color-danger); }
.msg.ok { color: #4ADE80; }
</style>

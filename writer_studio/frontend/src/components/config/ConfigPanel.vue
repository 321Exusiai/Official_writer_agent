<template>
  <div class="config-panel">
    <h3 class="config-title">LLM 接口配置</h3>
    <p class="hint-text">配置 OpenAI 兼容 API（DeepSeek / 通义千问 / 本地 Ollama 等）。未配置时系统走规则模式并明确标注。</p>

    <input class="ios-input" v-model="form.api_base" placeholder="API Base URL（如 https://api.deepseek.com/v1）" />
    <input class="ios-input" v-model="form.api_key" type="password" placeholder="API Key" />
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
      <span>启用 LLM</span>
    </label>

    <div class="config-divider">联网搜索（可选）</div>
    <p class="hint-text">填写搜索 API Key（Tavily / 博查）后，写作时会实时联网检索最新政策与讲话。留空则只用内置语料库。</p>
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
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../../api/client'
import Button from '../ui/Button.vue'

const form = ref({ api_base: '', api_key: '', model: '', temperature: 0.7, max_tokens: 8000, enabled: false, provider: 'openai', search_provider: 'tavily', search_api_key: '' })
const msg = ref('')
const msgOk = ref(false)

onMounted(async () => {
  try { form.value = { ...form.value, ...(await api.get('/config')) } } catch { /* ignore */ }
})

async function save() {
  try {
    await api.post('/config', form.value)
    msg.value = '已保存'
    msgOk.value = true
  } catch (e) {
    msg.value = '保存失败：' + e.message
    msgOk.value = false
  }
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
</script>

<style scoped>
.config-panel { display: flex; flex-direction: column; gap: 10px; }
.config-title { font-size: 15px; font-weight: 700; }
.hint-text { color: var(--color-ink-muted); font-size: 12px; line-height: 1.6; }
.config-row { display: flex; align-items: center; gap: 10px; }
.config-label { font-size: 13px; color: var(--color-ink-muted); width: 80px; flex-shrink: 0; }
.toggle-row { display: flex; align-items: center; gap: 8px; font-size: 14px; cursor: pointer; }
.actions { display: flex; gap: 8px; }
.config-divider { margin-top: 6px; padding-top: 10px; border-top: 1px solid var(--glass-border); font-size: 13px; font-weight: 700; color: var(--color-ink-body); }
.msg { font-size: 13px; color: var(--color-danger); }
.msg.ok { color: #4ADE80; }
</style>

<template>
  <div class="assistant-panel">
    <div class="ap-head">
      <h4 class="ap-title">🤖 辅助智能体</h4>
      <span class="badge" :class="available ? 'badge-llm' : 'badge-rule'">{{ available ? 'GLM 已启用' : '规则模式' }}</span>
    </div>
    <p class="hint-text">问答 + 帮你整理资料 / 分析画像 / 管理收藏 / 全局搜索 / 导出（不参与写作流程）</p>
    <div v-if="projectStore.active" class="ap-ctx">当前项目：<b>{{ projectStore.active.name }}</b>（助手会结合该项目作答）</div>

    <!-- 快捷规则 -->
    <div class="quick-row">
      <button v-for="q in quicks" :key="q.cmd" class="quick-btn" :title="q.desc" @click="quickSend(q)">{{ q.label }}</button>
    </div>

    <div class="ap-messages">
      <div v-for="(m, i) in messages" :key="i" class="ap-msg" :class="m.role">
        <div class="ap-bubble">
          <div v-if="m.tools && m.tools.length" class="ap-tools">
            <span v-for="(t, j) in m.tools" :key="j" class="tool-tag">🔧 {{ t.name }}</span>
          </div>
          <div class="ap-text">{{ m.content }}</div>
          <div v-if="m.mode" class="ap-mode">{{ m.mode === 'llm' ? 'LLM' : '规则' }}</div>
        </div>
      </div>
      <div v-if="busy" class="ap-msg assistant"><div class="ap-bubble typing">思考中…</div></div>
      <div v-if="!messages.length" class="ap-empty">
        你好，我是你的公文写作小帮手。可以问我：
        <br />· 「分析我的画像弱点」
        <br />· 「新质生产力是什么意思」
        <br />· 「有哪些项目，帮我看看」
        <br />· 「解读这段参考文本：…」
      </div>
    </div>

    <div class="ap-input">
      <textarea class="ios-input" v-model="input" rows="2" placeholder="问我问题，或让我帮你整理资料、分析画像…（Ctrl+Enter 发送）" @keydown.ctrl.enter="send" />
      <Button @click="send" :disabled="busy || !input.trim()">发送</Button>
    </div>

    <div v-if="tools.length" class="ap-capabilities">
      <div class="cap-title">我能帮你：</div>
      <div class="cap-list">
        <span v-for="t in tools" :key="t.name" class="cap-tag" :title="t.description">{{ t.name }}</span>
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
const messages = ref([])
const history = ref([])
const input = ref('')
const busy = ref(false)
const tools = ref([])
const available = ref(false)

const quicks = [
  { label: '📊 画像', cmd: '/画像', desc: '分析我的写作弱点与 bias' },
  { label: '📁 项目', cmd: '/项目', desc: '列出所有项目' },
  { label: '⭐ 收藏', cmd: '/收藏', desc: '查看综合收藏夹' },
  { label: '📚 资料', cmd: '/资料', desc: '检索知识库（输入关键词）' },
  { label: '🔎 搜索', cmd: '/搜索', desc: '全局搜索' },
  { label: '📤 导出', cmd: '/导出', desc: '导出当前项目 Markdown' },
]

function quickSend(q) {
  input.value = q.cmd + (q.needInput ? ' ' : '')
  if (!q.needInput) send()
}

async function send() {
  const text = input.value.trim()
  if (!text || busy.value) return
  input.value = ''
  messages.value.push({ role: 'user', content: text })
  busy.value = true
  try {
    const pid = projectStore.active && projectStore.active.id
    const r = await api.post('/assistant/chat', { message: text, history: history.value, project_id: pid || '' })
    messages.value.push({ role: 'assistant', content: r.reply, mode: r.mode, tools: r.tool_calls })
    history.value.push({ role: 'user', content: text })
    history.value.push({ role: 'assistant', content: r.reply })
    available.value = r.mode === 'llm'
  } catch (e) {
    messages.value.push({ role: 'assistant', content: '出错了：' + e.message, mode: 'error' })
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  try {
    const r = await api.get('/assistant/tools')
    tools.value = r.tools
    available.value = r.available
  } catch { /* ignore */ }
})
</script>

<style scoped>
.assistant-panel { display: flex; flex-direction: column; gap: 10px; height: 100%; }
.ap-head { display: flex; justify-content: space-between; align-items: center; }
.ap-title { font-size: 15px; font-weight: 700; }
.hint-text { color: var(--color-ink-muted); font-size: 12px; line-height: 1.5; }
.ap-ctx { font-size: 11px; color: var(--color-ink-muted); background: var(--glass-highlight); border: 1px solid var(--glass-border); border-radius: 8px; padding: 4px 8px; }
.quick-row { display: flex; flex-wrap: wrap; gap: 4px; }
.quick-btn { font-size: 11px; padding: 3px 8px; border-radius: 8px; border: 1px solid var(--glass-border); background: none; color: var(--color-ink-body); cursor: pointer; font-family: var(--font-ui); }
.quick-btn:hover { border-color: var(--color-accent); color: var(--color-accent); }
.ap-messages { flex: 1; display: flex; flex-direction: column; gap: 10px; overflow-y: auto; min-height: 220px; max-height: 50vh; padding: 4px 2px; }
.ap-msg { display: flex; }
.ap-msg.user { justify-content: flex-end; }
.ap-msg.assistant { justify-content: flex-start; }
.ap-bubble { max-width: 88%; padding: 10px 12px; border-radius: 16px; font-size: 13px; line-height: 1.7; }
.ap-msg.user .ap-bubble { background: var(--color-accent); color: #1D1D1F; border-bottom-right-radius: 4px; }
.ap-msg.assistant .ap-bubble { background: var(--glass-highlight); border: 1px solid var(--glass-border); color: var(--color-ink-body); border-bottom-left-radius: 4px; }
.ap-text { white-space: pre-wrap; }
.ap-tools { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 6px; }
.tool-tag { font-size: 10px; padding: 1px 6px; border-radius: 6px; background: rgba(167, 139, 250, 0.2); color: #A78BFA; }
.ap-mode { font-size: 10px; color: var(--color-ink-muted); margin-top: 4px; }
.typing { color: var(--color-ink-muted); font-style: italic; }
.ap-empty { color: var(--color-ink-muted); font-size: 12px; line-height: 1.8; padding: 10px; }
.ap-input { display: flex; gap: 8px; align-items: flex-end; }
.ap-input .ios-input { resize: vertical; }
.ap-capabilities { border-top: 1px solid var(--glass-border); padding-top: 8px; }
.cap-title { font-size: 11px; font-weight: 700; color: var(--color-ink-muted); margin-bottom: 6px; }
.cap-list { display: flex; flex-wrap: wrap; gap: 4px; }
.cap-tag { font-size: 10px; padding: 2px 8px; border-radius: 999px; background: var(--glass-highlight); border: 1px solid var(--glass-border); color: var(--color-ink-muted); }
</style>

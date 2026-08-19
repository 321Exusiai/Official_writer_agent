<template>
  <div class="assistant-panel">
    <!-- 头部 -->
    <div class="ap-head">
      <div class="ap-title-wrap">
        <span class="ap-orb">🤖</span>
        <div>
          <h4 class="ap-title">辅助智能体</h4>
          <span class="ap-sub">随叫随到的小帮手</span>
        </div>
      </div>
      <span class="badge" :class="available ? 'badge-llm' : 'badge-rule'">
        {{ available ? 'GLM 已启用' : '规则模式' }}
      </span>
    </div>

    <div v-if="projectStore.active" class="ap-ctx">
      <span class="ctx-dot" />当前项目：<b>{{ projectStore.active.name }}</b>
    </div>

    <!-- 快捷规则 -->
    <div class="quick-row">
      <button v-for="q in quicks" :key="q.cmd" class="quick-btn" :title="q.desc" @click="quickSend(q)">
        {{ q.label }}
      </button>
    </div>

    <!-- 消息区 -->
    <div ref="msgBox" class="ap-messages">
      <div v-for="(m, i) in messages" :key="i" class="ap-msg" :class="m.role">
        <span v-if="m.role === 'assistant'" class="ap-avatar">🤖</span>
        <div class="ap-bubble" :class="m.role">
          <div v-if="m.tools && m.tools.length" class="ap-tools">
            <span v-for="(t, j) in m.tools" :key="j" class="tool-tag">🔧 {{ t.name }}</span>
          </div>
          <div class="ap-text">{{ m.content }}</div>
          <div v-if="m.mode" class="ap-mode">{{ m.mode === 'llm' ? 'LLM' : '规则' }}</div>
        </div>
        <span v-if="m.role === 'user'" class="ap-avatar user">我</span>
      </div>

      <div v-if="busy" class="ap-msg assistant">
        <span class="ap-avatar">🤖</span>
        <div class="ap-bubble assistant typing">
          <span class="dot" /><span class="dot" /><span class="dot" />
        </div>
      </div>

      <!-- 空状态：给一个明确的下一步 -->
      <div v-if="!messages.length" class="ap-empty">
        <div class="ap-empty-orb">💬</div>
        <div class="ap-empty-title">有什么可以帮你？</div>
        <div class="ap-empty-hint">试试问我：</div>
        <div class="ap-suggests">
          <button v-for="(s, i) in suggests" :key="i" class="suggest-chip" @click="ask(s)">{{ s }}</button>
        </div>
      </div>
    </div>

    <!-- 动态情境动作胶囊 -->
    <div v-if="contextActions.length" class="context-actions">
      <button
        v-for="act in contextActions"
        :key="act.label"
        class="context-pill"
        :title="act.hint || act.label"
        @click="handleAction(act)"
      >
        <span>{{ act.icon || '⚡' }}</span>
        <span>{{ act.label }}</span>
      </button>
    </div>

    <!-- 输入区：胶囊容器 -->
    <div class="ap-input">
      <textarea
        ref="taRef"
        class="ap-textarea"
        v-model="input"
        rows="1"
        placeholder="问点什么，或让我整理资料、分析画像…（Enter 发送）"
        @input="autoGrow"
        @keydown.ctrl.enter="send"
        @keydown.enter.exact.prevent="send"
      />
      <button class="ap-send" :disabled="busy || !input.trim()" title="发送" @click="send">➤</button>
    </div>

    <!-- 能力清单（可折叠） -->
    <details class="ap-capabilities">
      <summary class="cap-title">我能帮你 · {{ tools.length }} 项能力</summary>
      <div class="cap-list">
        <span v-for="t in tools" :key="t.name" class="cap-tag" :title="t.description">{{ t.name }}</span>
      </div>
    </details>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, watch } from 'vue'
import { api } from '../../api/client'
import { useProjectStore } from '../../stores/project'

const projectStore = useProjectStore()
const messages = ref([])
const history = ref([])
const input = ref('')
const busy = ref(false)
const tools = ref([])
const available = ref(false)
const msgBox = ref(null)
const taRef = ref(null)

const quicks = [
  { label: '📊 画像', cmd: '/画像', desc: '分析我的写作弱点与 bias' },
  { label: '📁 项目', cmd: '/项目', desc: '列出所有项目' },
  { label: '⭐ 收藏', cmd: '/收藏', desc: '查看综合收藏夹' },
  { label: '📚 资料', cmd: '/资料', desc: '检索知识库（输入关键词）' },
  { label: '🔎 搜索', cmd: '/搜索', desc: '全局搜索' },
  { label: '🌐 联网', cmd: '帮我联网搜索', desc: '实时检索最新政策/讲话（需配置搜索 Key）' },
]

const suggests = [
  '分析我的画像弱点',
  '新质生产力是什么意思',
  '联网搜索最新政策',
  '解读这段参考文本：…',
]

function ask(text) {
  if (text === '解读这段参考文本：…') {
    input.value = '解读这段参考文本：'
    return
  }
  input.value = text
  send()
}

function quickSend(q) {
  input.value = q.cmd + (q.needInput ? ' ' : '')
  if (!q.needInput) send()
}

async function send() {
  const text = input.value.trim()
  if (!text || busy.value) return
  input.value = ''
  nextTick(autoGrow) // 发送后收回单行高度
  messages.value.push({ role: 'user', content: text })
  busy.value = true
  scrollBottom()
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
    scrollBottom()
  }
}

function scrollBottom() {
  nextTick(() => {
    if (msgBox.value) msgBox.value.scrollTop = msgBox.value.scrollHeight
  })
}

const TA_MAX = 110 // 自动增高上限（px），超过后内部滚动（滚动条已隐藏）
function autoGrow() {
  const el = taRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, TA_MAX) + 'px'
}

const contextActions = ref([])

async function loadContextActions() {
  try {
    const pid = (projectStore.active && projectStore.active.id) || ''
    const r = await api.get(`/assistant/actions?project_id=${pid}`)
    contextActions.value = r.actions || []
  } catch {
    contextActions.value = []
  }
}

watch(() => projectStore.active, () => {
  loadContextActions()
}, { immediate: true })

async function handleAction(act) {
  if (act.action === 'auto_heal') {
    const pid = projectStore.active && projectStore.active.id
    if (!pid) return
    messages.value.push({ role: 'user', content: '⚡ 启动自主收敛自愈（目标 85+ 分）' })
    busy.value = true
    scrollBottom()
    try {
      const res = await api.post(`/projects/${pid}/workflow/auto_heal`)
      messages.value.push({
        role: 'assistant',
        content: `⚡ 自愈收敛完成！最终得分：${res.final_score}分（共执行 ${res.rounds_run} 轮自动辩论与定向修复）。已更新审查状态。`,
        mode: 'llm',
      })
      loadContextActions()
    } catch (e) {
      messages.value.push({ role: 'assistant', content: `自愈执行失败：${e.message || e}`, mode: 'error' })
    } finally {
      busy.value = false
      scrollBottom()
    }
    return
  }
  if (act.cmd) {
    input.value = act.cmd
    send()
  }
}

onMounted(async () => {
  try {
    const r = await api.get('/assistant/tools')
    tools.value = r.tools
    available.value = r.available
    loadContextActions()
  } catch { /* ignore */ }
})
</script>

<style scoped>
.assistant-panel {
  display: flex; flex-direction: column;
  gap: 10px;
  height: 100%;
  min-height: 0;
}

.context-actions {
  display: flex; flex-wrap: wrap; gap: 6px;
  padding: 4px 2px;
}
.context-pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 9px; border-radius: 12px;
  background: color-mix(in srgb, var(--color-primary) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--color-primary) 30%, transparent);
  color: var(--color-primary); font-size: 11px; font-weight: 600;
  cursor: pointer; transition: all 0.2s ease;
}
.context-pill:hover {
  background: color-mix(in srgb, var(--color-primary) 20%, transparent);
  border-color: var(--color-primary);
  transform: translateY(-1px);
}

/* ── 头部 ── */
.ap-head { display: flex; justify-content: space-between; align-items: center; }
.ap-title-wrap { display: flex; align-items: center; gap: 10px; }
.ap-orb {
  width: 36px; height: 36px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px;
  background: var(--glass-highlight);
  border: 1px solid var(--glass-border);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
.ap-title { font-size: 15px; font-weight: 700; line-height: 1.2; }
.ap-sub { font-size: 11px; color: var(--color-ink-muted); }

/* ── 项目上下文条 ── */
.ap-ctx {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; color: var(--color-ink-muted);
  background: var(--glass-highlight);
  border: 1px solid var(--glass-border);
  border-radius: 10px; padding: 6px 10px;
}
.ctx-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--color-accent); flex-shrink: 0; }

/* ── 快捷规则 ── */
.quick-row { display: flex; flex-wrap: wrap; gap: 5px; }
.quick-btn {
  font-size: 11px; padding: 5px 10px; border-radius: 999px;
  border: 1px solid var(--glass-border);
  background: var(--glass-highlight);
  color: var(--color-ink-body);
  cursor: pointer; font-family: var(--font-ui);
  transition: transform 0.15s var(--ease-out-expo), border-color 0.15s, color 0.15s;
}
.quick-btn:hover { border-color: var(--color-accent); color: var(--color-accent); transform: translateY(-1px); }
.quick-btn:active { transform: scale(0.96); }

/* ── 消息区 ── */
.ap-messages {
  flex: 1; min-height: 0;
  display: flex; flex-direction: column; gap: 10px;
  overflow-y: auto;
  padding: 6px 2px;
}
.ap-msg { display: flex; align-items: flex-end; gap: 6px; }
.ap-msg.user { justify-content: flex-end; }
.ap-avatar {
  width: 26px; height: 26px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px;
  background: var(--glass-highlight);
  border: 1px solid var(--glass-border);
}
.ap-avatar.user {
  font-size: 10px; font-weight: 700; color: #1D1D1F;
  background: var(--color-accent);
  border-color: var(--color-accent);
}
:root[data-theme="apple"] .ap-avatar.user { color: #fff; }

.ap-bubble {
  max-width: 82%;
  padding: 9px 13px;
  border-radius: 16px;
  font-size: 13px; line-height: 1.7;
  word-break: break-word;
}
.ap-bubble.assistant {
  background: var(--glass-bg);
  backdrop-filter: var(--blur-glass);
  -webkit-backdrop-filter: var(--blur-glass);
  border: 1px solid var(--glass-border);
  color: var(--color-ink-body);
  border-bottom-left-radius: 4px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.12);
}
.ap-bubble.user {
  background: var(--color-accent);
  color: #1D1D1F;
  border-bottom-right-radius: 4px;
}
:root[data-theme="apple"] .ap-bubble.user { color: #fff; }
.ap-text { white-space: pre-wrap; }

/* 工具标签 */
.ap-tools { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 6px; }
.tool-tag {
  font-size: 10px; padding: 2px 8px; border-radius: 999px;
  background: rgba(167, 139, 250, 0.18); color: #A78BFA;
  border: 1px solid rgba(167, 139, 250, 0.25);
}

/* 模式角标 */
.ap-mode {
  font-size: 10px; color: var(--color-ink-muted);
  margin-top: 4px; opacity: 0.8;
}

/* 打字指示 */
.typing { display: flex; align-items: center; gap: 4px; padding: 12px 14px; }
.dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--color-ink-muted);
  animation: typing-bounce 1.2s ease-in-out infinite;
}
.dot:nth-child(2) { animation-delay: 0.15s; }
.dot:nth-child(3) { animation-delay: 0.3s; }
@keyframes typing-bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}

/* ── 空状态：给一个明确的下一步 ── */
.ap-empty {
  margin: auto;
  display: flex; flex-direction: column; align-items: center;
  text-align: center; gap: 8px;
  padding: 24px 8px;
}
.ap-empty-orb {
  width: 48px; height: 48px; border-radius: 16px;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px;
  background: var(--glass-highlight);
  border: 1px solid var(--glass-border);
  animation: smooth-enter 0.3s var(--ease-out-expo);
}
.ap-empty-title { font-size: 14px; font-weight: 700; color: var(--color-ink-body); }
.ap-empty-hint { font-size: 12px; color: var(--color-ink-muted); }
.ap-suggests { display: flex; flex-wrap: wrap; gap: 6px; justify-content: center; }
.suggest-chip {
  font-size: 11px; padding: 5px 12px; border-radius: 999px;
  border: 1px solid var(--color-accent-focus);
  background: rgba(0, 0, 0, 0.1);
  color: var(--color-accent);
  cursor: pointer; font-family: var(--font-ui);
  transition: transform 0.15s var(--ease-out-expo), background 0.15s;
}
.suggest-chip:hover { background: var(--color-accent-focus); transform: translateY(-1px); }

/* ── 输入区：胶囊容器 ── */
.ap-input {
  display: flex; align-items: flex-end; gap: 6px;
  background: var(--glass-bg);
  backdrop-filter: var(--blur-glass);
  -webkit-backdrop-filter: var(--blur-glass);
  border: 1px solid var(--glass-border);
  border-radius: 20px;
  padding: 6px 6px 6px 14px;
  box-shadow: inset 0 1px 0 var(--glass-highlight);
}
.ap-textarea {
  flex: 1;
  border: none; background: transparent;
  color: var(--color-ink);
  font-family: var(--font-ui); font-size: 13px; line-height: 1.5;
  outline: none; resize: none;
  max-height: 110px;
  padding: 6px 0;
  /* 隐藏系统默认滚动条（白色轨道+滑块），长文本时仅滚轮滚动 */
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.ap-textarea::-webkit-scrollbar { display: none; width: 0; height: 0; }
.ap-textarea::placeholder { color: var(--color-ink-muted); }
.ap-send {
  width: 34px; height: 34px; border-radius: 50%; flex-shrink: 0;
  border: none; cursor: pointer;
  background: var(--color-accent); color: #1D1D1F;
  font-size: 15px; display: flex; align-items: center; justify-content: center;
  transition: transform 0.15s var(--ease-out-expo), opacity 0.15s;
}
:root[data-theme="apple"] .ap-send { color: #fff; }
.ap-send:hover:not(:disabled) { transform: scale(1.06); }
.ap-send:disabled { opacity: 0.35; cursor: not-allowed; }

/* ── 能力清单（可折叠） ── */
.ap-capabilities { border-top: 1px solid var(--glass-border); padding-top: 6px; }
.cap-title {
  font-size: 11px; font-weight: 600; color: var(--color-ink-muted);
  cursor: pointer; user-select: none; list-style: none;
  padding: 2px 0;
}
.cap-title::-webkit-details-marker { display: none; }
.cap-title::before { content: "▸ "; color: var(--color-accent); }
details[open] .cap-title::before { content: "▾ "; }
.cap-list { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.cap-tag {
  font-size: 10px; padding: 2px 8px; border-radius: 999px;
  background: var(--glass-highlight);
  border: 1px solid var(--glass-border);
  color: var(--color-ink-muted);
}

@media (prefers-reduced-motion: reduce) {
  .dot { animation: none; }
}
</style>

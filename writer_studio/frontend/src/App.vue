<template>
  <div class="app-shell">
    <!-- 背景层：星月夜 / 经典流光 / 苹果极简 -->
    <div class="app-bg" :class="{ fluid: theme.theme === 'classic', minimal: theme.theme === 'apple' }">
      <svg v-if="theme.theme === 'starry'" viewBox="0 0 1000 1000" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <rect width="1000" height="1000" fill="#0D162B" />
        <rect width="1000" height="1000" fill="url(#sky)" />
        <defs>
          <radialGradient id="sky" cx="50%" cy="20%" r="90%">
            <stop offset="0%" stop-color="#1C3765" />
            <stop offset="50%" stop-color="#0D162B" />
            <stop offset="100%" stop-color="#0D1917" />
          </radialGradient>
        </defs>
        <g fill="none" stroke="#4F7EA4" opacity="0.35">
          <ellipse cx="300" cy="320" rx="160" ry="55" stroke-width="34">
            <animateTransform attributeName="transform" type="rotate" from="0 300 320" to="360 300 320" dur="45s" repeatCount="indefinite" />
          </ellipse>
          <ellipse cx="320" cy="330" rx="120" ry="40" stroke-width="18" stroke="#648BA8">
            <animateTransform attributeName="transform" type="rotate" from="360 320 330" to="0 320 330" dur="38s" repeatCount="indefinite" />
          </ellipse>
          <ellipse cx="700" cy="280" rx="190" ry="65" stroke-width="30">
            <animateTransform attributeName="transform" type="rotate" from="0 700 280" to="-360 700 280" dur="55s" repeatCount="indefinite" />
          </ellipse>
          <ellipse cx="720" cy="300" rx="130" ry="42" stroke-width="16" stroke="#8DB3C3">
            <animateTransform attributeName="transform" type="rotate" from="-360 720 300" to="0 720 300" dur="42s" repeatCount="indefinite" />
          </ellipse>
        </g>
        <circle cx="810" cy="190" r="55" fill="#DFCB5C" opacity="0.95" />
        <circle cx="830" cy="175" r="55" fill="#0D162B" opacity="0.35" />
        <circle cx="790" cy="200" r="8" fill="#E3D896" opacity="0.7" />
        <g fill="#E7D674">
          <circle cx="120" cy="140" r="4"><animate attributeName="opacity" values="1;0.3;1" dur="3s" repeatCount="indefinite" /></circle>
          <circle cx="520" cy="110" r="3"><animate attributeName="opacity" values="1;0.4;1" dur="4s" repeatCount="indefinite" /></circle>
          <circle cx="400" cy="180" r="5"><animate attributeName="opacity" values="1;0.3;1" dur="3.5s" repeatCount="indefinite" /></circle>
          <circle cx="640" cy="500" r="3"><animate attributeName="opacity" values="1;0.4;1" dur="5s" repeatCount="indefinite" /></circle>
          <circle cx="200" cy="600" r="4"><animate attributeName="opacity" values="1;0.3;1" dur="4.2s" repeatCount="indefinite" /></circle>
          <circle cx="880" cy="620" r="4"><animate attributeName="opacity" values="1;0.35;1" dur="3.8s" repeatCount="indefinite" /></circle>
        </g>
      </svg>
    </div>

    <!-- 标题栏 -->
    <header class="title-bar">
      <div class="brand">
        <span class="brand-dot" />
        <h1>公文写作工作室</h1>
      </div>
      <div class="theme-switch">
        <button v-for="t in themes" :key="t.id" class="theme-btn" :class="{ on: theme.theme === t.id }" @click="theme.setTheme(t.id)">
          {{ t.label }}
        </button>
      </div>
    </header>

    <!-- 三栏 -->
    <div class="layout">
      <aside class="pane">
        <h2 class="pane-title">项目</h2>
        <ProjectBrowser />
      </aside>

      <main class="pane workspace">
        <div v-if="!projectStore.active" class="empty-state">
          <div style="font-size: 48px">✍️</div>
          <div>在左侧选择或新建一个项目，开始沉浸式写作</div>
        </div>
        <template v-else>
          <div class="ws-head">
            <h2 class="ws-title">{{ projectStore.active.name }}</h2>
            <Button variant="secondary" @click="startWorkflow">开始写作</Button>
          </div>
          <WorkflowPanel />
        </template>
      </main>

      <aside class="pane">
        <div class="pane-tabs">
          <button class="pane-tab" :class="{ on: !showConfig }" @click="showConfig = false">过程</button>
          <button class="pane-tab" :class="{ on: showConfig }" @click="showConfig = true">设置</button>
        </div>
        <ProcessPanel v-if="!showConfig" />
        <ConfigPanel v-else />
      </aside>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'
import { useThemeStore } from './stores/theme'
import { useProjectStore } from './stores/project'
import { useWorkflowStore } from './stores/workflow'
import ProjectBrowser from './components/project/ProjectBrowser.vue'
import WorkflowPanel from './components/workflow/WorkflowPanel.vue'
import ProcessPanel from './components/workflow/ProcessPanel.vue'
import ConfigPanel from './components/config/ConfigPanel.vue'
import Button from './components/ui/Button.vue'

const theme = useThemeStore()
const projectStore = useProjectStore()
const workflow = useWorkflowStore()
const showConfig = ref(false)

const themes = [
  { id: 'starry', label: '星月夜' },
  { id: 'classic', label: '经典流光' },
  { id: 'apple', label: '苹果极简' },
]

let unsubscribe = null

async function startWorkflow() {
  const pid = projectStore.active && projectStore.active.id
  if (!pid) return
  workflow.reset()
  await workflow.start(pid)
  if (unsubscribe) unsubscribe()
  unsubscribe = workflow.attachEvents(pid)
}

onMounted(() => {
  theme.apply()
  projectStore.fetch()
})

onBeforeUnmount(() => {
  if (unsubscribe) unsubscribe()
})
</script>

<style scoped>
.app-shell { position: relative; min-height: 100vh; }
.title-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 24px;
  backdrop-filter: var(--blur-glass);
  -webkit-backdrop-filter: var(--blur-glass);
  border-bottom: 1px solid var(--glass-border);
  position: sticky; top: 0; z-index: 10;
}
.brand { display: flex; align-items: center; gap: 10px; }
.brand-dot {
  width: 10px; height: 10px; border-radius: 50%;
  background: var(--color-accent); box-shadow: 0 0 12px var(--color-accent);
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.brand h1 { font-size: 16px; font-weight: 700; letter-spacing: 0.5px; }
.theme-switch {
  display: flex; gap: 4px; background: var(--glass-highlight);
  border: 1px solid var(--glass-border); border-radius: 12px; padding: 3px;
}
.theme-btn {
  border: none; background: none; color: var(--color-ink-muted);
  padding: 6px 12px; border-radius: 9px; font-size: 12px; font-weight: 600;
  cursor: pointer; font-family: var(--font-ui);
}
.theme-btn.on { background: var(--color-accent); color: #1D1D1F; }
:root[data-theme="apple"] .theme-btn.on { color: #fff; }
.pane-title { font-size: 14px; font-weight: 700; margin-bottom: 12px; color: var(--color-ink-muted); }
.pane-tabs { display: flex; gap: 4px; margin-bottom: 14px; background: var(--glass-highlight); border: 1px solid var(--glass-border); border-radius: 10px; padding: 3px; }
.pane-tab { flex: 1; border: none; background: none; color: var(--color-ink-muted); padding: 6px 0; border-radius: 7px; font-size: 13px; font-weight: 600; cursor: pointer; font-family: var(--font-ui); }
.pane-tab.on { background: var(--color-accent); color: #1D1D1F; }
:root[data-theme="apple"] .pane-tab.on { color: #fff; }
.workspace { display: flex; flex-direction: column; gap: 16px; }
.ws-head { display: flex; justify-content: space-between; align-items: center; }
.ws-title { font-size: 18px; font-weight: 700; }
</style>

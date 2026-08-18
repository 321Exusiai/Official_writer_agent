<template>
  <div class="app-shell">
    <!-- 背景层：星月夜 / 经典流光 / 苹果极简 -->
    <div class="app-bg" :class="{ fluid: theme.theme === 'classic', minimal: theme.theme === 'apple' }">
      <svg v-if="theme.theme === 'starry'" viewBox="0 0 1000 1000" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <defs>
          <filter id="blurLg"><feGaussianBlur stdDeviation="24"/></filter>
          <filter id="blurMd"><feGaussianBlur stdDeviation="12"/></filter>
          <filter id="blurSm"><feGaussianBlur stdDeviation="6"/></filter>
          <radialGradient id="swirlLight" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#4F7EA4" stop-opacity="0.8"/>
            <stop offset="100%" stop-color="#003153" stop-opacity="0"/>
          </radialGradient>
          <radialGradient id="swirlMid" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#2a6a9b" stop-opacity="0.7"/>
            <stop offset="100%" stop-color="#00213B" stop-opacity="0"/>
          </radialGradient>
          <radialGradient id="swirlDark" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#005085" stop-opacity="0.6"/>
            <stop offset="100%" stop-color="#05101a" stop-opacity="0"/>
          </radialGradient>
          <radialGradient id="starHalo" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#DFCB5C" stop-opacity="0.95"/>
            <stop offset="20%" stop-color="#DFCB5C" stop-opacity="0.6"/>
            <stop offset="50%" stop-color="#1C3765" stop-opacity="0.3"/>
            <stop offset="100%" stop-color="#1C3765" stop-opacity="0"/>
          </radialGradient>
          <radialGradient id="moonHalo" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stop-color="#E7D674" stop-opacity="1"/>
            <stop offset="15%" stop-color="#DFCB5C" stop-opacity="0.8"/>
            <stop offset="40%" stop-color="#648BA8" stop-opacity="0.4"/>
            <stop offset="100%" stop-color="#1C3765" stop-opacity="0"/>
          </radialGradient>
        </defs>

        <rect width="100%" height="100%" fill="#00172D"/>

        <!-- 背景星点 -->
        <g fill="#FFF">
          <circle cx="100" cy="200" r="1.5" opacity="0.8"/><circle cx="250" cy="80" r="1" opacity="0.6"/>
          <circle cx="450" cy="150" r="2" opacity="0.9"/><circle cx="650" cy="90" r="1.5" opacity="0.5"/>
          <circle cx="850" cy="120" r="2.5" opacity="0.8"/><circle cx="950" cy="250" r="1" opacity="0.7"/>
          <circle cx="150" cy="350" r="2" opacity="0.9"/><circle cx="350" cy="450" r="1.5" opacity="0.6"/>
          <circle cx="550" cy="350" r="2.5" opacity="0.8"/><circle cx="750" cy="480" r="1" opacity="0.5"/>
          <circle cx="920" cy="380" r="2" opacity="0.7"/><circle cx="50" cy="550" r="1.5" opacity="0.8"/>
          <circle cx="250" cy="650" r="2" opacity="0.6"/><circle cx="450" cy="750" r="1" opacity="0.9"/>
          <circle cx="650" cy="650" r="2.5" opacity="0.5"/><circle cx="850" cy="750" r="1.5" opacity="0.8"/>
          <circle cx="950" cy="600" r="1" opacity="0.7"/><circle cx="150" cy="850" r="2" opacity="0.9"/>
          <circle cx="350" cy="950" r="1.5" opacity="0.6"/><circle cx="550" cy="850" r="2.5" opacity="0.8"/>
          <circle cx="750" cy="950" r="1" opacity="0.5"/><circle cx="920" cy="880" r="2" opacity="0.7"/>
        </g>

        <!-- 流动漩涡 -->
        <g>
          <animateTransform attributeName="transform" type="rotate" from="0 300 300" to="360 300 300" dur="45s" repeatCount="indefinite"/>
          <ellipse cx="300" cy="300" rx="450" ry="200" fill="url(#swirlLight)" filter="url(#blurLg)" transform="rotate(30 300 300)"/>
          <ellipse cx="300" cy="300" rx="300" ry="150" fill="url(#swirlMid)" filter="url(#blurMd)" transform="rotate(-20 300 300)"/>
        </g>
        <g>
          <animateTransform attributeName="transform" type="rotate" from="360 750 400" to="0 750 400" dur="60s" repeatCount="indefinite"/>
          <ellipse cx="750" cy="400" rx="500" ry="250" fill="url(#swirlMid)" filter="url(#blurLg)" transform="rotate(-45 750 400)"/>
          <ellipse cx="750" cy="400" rx="200" ry="400" fill="url(#swirlLight)" filter="url(#blurMd)" transform="rotate(15 750 400)"/>
        </g>
        <g>
          <animateTransform attributeName="transform" type="rotate" from="0 400 800" to="360 400 800" dur="50s" repeatCount="indefinite"/>
          <ellipse cx="400" cy="800" rx="400" ry="250" fill="url(#swirlDark)" filter="url(#blurLg)" transform="rotate(60 400 800)"/>
        </g>

        <!-- 月亮 -->
        <g>
          <animateTransform attributeName="transform" type="rotate" from="0 850 200" to="360 850 200" dur="30s" repeatCount="indefinite"/>
          <circle cx="850" cy="200" r="180" fill="url(#moonHalo)" filter="url(#blurSm)"/>
          <ellipse cx="850" cy="200" rx="140" ry="70" fill="url(#swirlLight)" opacity="0.3" filter="url(#blurSm)" transform="rotate(45 850 200)"/>
        </g>

        <!-- 星晕 -->
        <g>
          <animateTransform attributeName="transform" type="rotate" from="360 200 150" to="0 200 150" dur="25s" repeatCount="indefinite"/>
          <circle cx="200" cy="150" r="120" fill="url(#starHalo)" filter="url(#blurSm)"/>
          <ellipse cx="200" cy="150" rx="90" ry="40" fill="url(#swirlLight)" opacity="0.4" filter="url(#blurSm)" transform="rotate(-30 200 150)"/>
        </g>
        <g>
          <animateTransform attributeName="transform" type="rotate" from="0 150 550" to="360 150 550" dur="22s" repeatCount="indefinite"/>
          <circle cx="150" cy="550" r="100" fill="url(#starHalo)" filter="url(#blurSm)"/>
        </g>
        <g>
          <animateTransform attributeName="transform" type="rotate" from="360 500 450" to="0 500 450" dur="35s" repeatCount="indefinite"/>
          <circle cx="500" cy="450" r="80" fill="url(#starHalo)" filter="url(#blurSm)" opacity="0.8"/>
        </g>
        <g>
          <animateTransform attributeName="transform" type="rotate" from="0 750 750" to="360 750 750" dur="28s" repeatCount="indefinite"/>
          <circle cx="750" cy="750" r="110" fill="url(#starHalo)" filter="url(#blurSm)"/>
          <ellipse cx="750" cy="750" rx="80" ry="30" fill="url(#swirlLight)" opacity="0.3" filter="url(#blurSm)" transform="rotate(70 750 750)"/>
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
          <button class="pane-tab" :class="{ on: rightTab === 'process' }" @click="rightTab = 'process'">过程</button>
          <button class="pane-tab" :class="{ on: rightTab === 'mine' }" @click="rightTab = 'mine'">我的</button>
          <button class="pane-tab" :class="{ on: rightTab === 'knowledge' }" @click="rightTab = 'knowledge'">知识库</button>
          <button class="pane-tab" :class="{ on: rightTab === 'config' }" @click="rightTab = 'config'">设置</button>
        </div>
        <ProcessPanel v-if="rightTab === 'process'" />
        <MySpace v-else-if="rightTab === 'mine'" />
        <KnowledgePanel v-else-if="rightTab === 'knowledge'" />
        <ConfigPanel v-else />
      </aside>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useThemeStore } from './stores/theme'
import { useProjectStore } from './stores/project'
import { useWorkflowStore } from './stores/workflow'
import ProjectBrowser from './components/project/ProjectBrowser.vue'
import WorkflowPanel from './components/workflow/WorkflowPanel.vue'
import ProcessPanel from './components/workflow/ProcessPanel.vue'
import ConfigPanel from './components/config/ConfigPanel.vue'
import KnowledgePanel from './components/knowledge/KnowledgePanel.vue'
import MySpace from './components/profile/MySpace.vue'
import Button from './components/ui/Button.vue'

const theme = useThemeStore()
const projectStore = useProjectStore()
const workflow = useWorkflowStore()
const rightTab = ref('process')

const themes = [
  { id: 'starry', label: '星月夜' },
  { id: 'classic', label: '经典流光' },
  { id: 'apple', label: '苹果极简' },
]

async function startWorkflow() {
  const pid = projectStore.active && projectStore.active.id
  if (!pid) return
  await workflow.start(pid)
  workflow.attachEvents(pid)
}

// 切换项目时：隔离工作流状态 + 订阅该项目 SSE
watch(
  () => projectStore.active && projectStore.active.id,
  (pid) => {
    if (pid) {
      workflow.setActive(pid)
      workflow.attachEvents(pid)
    }
  },
)

onMounted(() => {
  theme.apply()
  projectStore.fetch()
})

onBeforeUnmount(() => {
  if (workflow.unsub) workflow.unsub()
})
</script>

<style scoped>
.app-shell { position: relative; min-height: 100vh; }
.title-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 24px;
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

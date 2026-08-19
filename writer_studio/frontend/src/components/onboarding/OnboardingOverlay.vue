<template>
  <div v-if="visible" class="ob-overlay">
    <div class="ob-card animate-enter">
      <div class="ob-head">
        <span class="ob-logo">📝</span>
        <h2>欢迎来到公文写作工作室</h2>
        <p class="ob-sub">三步上手，开始你的第一篇公文</p>
      </div>

      <div class="ob-steps">
        <div v-for="(s, i) in steps" :key="i" class="ob-step" :class="{ on: i === cur }">
          <span class="ob-dot">{{ i + 1 }}</span>
          <span class="ob-step-name">{{ s.name }}</span>
        </div>
      </div>

      <transition name="fade" mode="out-in">
        <div :key="cur" class="ob-body">
          <div class="ob-illus" v-html="steps[cur].illus"></div>
          <h3 class="ob-title">{{ steps[cur].title }}</h3>
          <p class="ob-desc">{{ steps[cur].desc }}</p>
          <p class="ob-tip">{{ steps[cur].tip }}</p>
        </div>
      </transition>

      <div class="ob-actions">
        <button class="ob-skip" @click="finish">跳过引导</button>
        <div class="ob-nav">
          <Button v-if="cur > 0" variant="secondary" @click="cur--">上一步</Button>
          <Button @click="next">{{ cur < steps.length - 1 ? '下一步' : '开始使用' }}</Button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import Button from '../ui/Button.vue'

const KEY = 'writer_studio_onboarded_v1'
const visible = ref(false)
const cur = ref(0)

const steps = [
  {
    name: '布局',
    title: '三栏工作台',
    desc: '左侧「项目」管理你的所有写作任务，像文件夹一样归类；中间是写作主舞台；右侧随时切换助手、过程、我的、知识库与设置。',
    tip: '写作全程的每一步都会在「过程」面板实时可见，你始终掌握主动权。',
    illus: `<div class="ob-layout"><span></span><span class="mid"></span><span></span></div>`,
  },
  {
    name: '创建项目',
    title: '新建项目，开始写作',
    desc: '点击左侧「＋ 新建」创建项目，再点「开始写作」。跟随场景路由与需求问卷回答几个问题，系统会生成写作方案，你可以调整文种与风格后确认。',
    tip: '参考文本、写作偏好、审查历史都会沉淀在项目里，同一任务可反复打磨多次。',
    illus: `<div class="ob-write"><span class="ob-w-folder">📁</span><span class="ob-w-arrow">→</span><span class="ob-w-doc">📄</span></div>`,
  },
  {
    name: '助手',
    title: '智能助手随时待命',
    desc: '右侧「助手」标签可随时提问、查政策、找范文、管理收藏。全局收藏快捷键 Ctrl+Shift+K 一键呼出，写作灵感随取随用。',
    tip: '助手只回答它真实检索到的内容，绝不编造——这是我们对你的承诺。',
    illus: `<div class="ob-assist"><span class="ob-a-bubble">💬</span><span class="ob-a-spark">✨</span></div>`,
  },
]

function next() {
  if (cur.value < steps.length - 1) cur.value++
  else finish()
}

function finish() {
  localStorage.setItem(KEY, '1')
  visible.value = false
}

onMounted(() => {
  if (!localStorage.getItem(KEY)) visible.value = true
})
</script>

<style scoped>
.ob-overlay {
  position: fixed; inset: 0; z-index: 999;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(6px);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.ob-card {
  width: min(440px, 92vw);
  background: var(--glass-bg); backdrop-filter: var(--blur-glass);
  border: 1px solid var(--glass-border); border-radius: 24px;
  padding: 28px 26px 20px;
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.4);
}
.ob-head { text-align: center; }
.ob-logo { font-size: 34px; }
.ob-head h2 { font-size: 19px; font-weight: 700; margin: 8px 0 4px; }
.ob-sub { font-size: 13px; color: var(--color-ink-muted); margin: 0; }

.ob-steps { display: flex; justify-content: center; gap: 6px; margin: 20px 0 16px; }
.ob-step { display: flex; align-items: center; gap: 5px; opacity: 0.45; transition: opacity 0.25s; }
.ob-step.on { opacity: 1; }
.ob-dot {
  width: 22px; height: 22px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700;
  background: var(--glass-highlight); border: 1px solid var(--glass-border);
  transition: all 0.25s var(--ease-out-expo);
}
.ob-step.on .ob-dot { background: var(--color-accent); color: #1D1D1F; border-color: var(--color-accent); }
:root[data-theme="apple"] .ob-step.on .ob-dot { color: #fff; }
.ob-step-name { font-size: 12px; font-weight: 600; }

.ob-body { text-align: center; min-height: 230px; display: flex; flex-direction: column; }
.ob-illus { margin: 6px auto 14px; }
.ob-layout { display: flex; gap: 6px; height: 72px; width: 220px; }
.ob-layout span { flex: 1; border-radius: 10px; background: var(--glass-highlight); border: 1px solid var(--glass-border); }
.ob-layout .mid { background: var(--color-accent); opacity: 0.85; border-color: var(--color-accent); }
.ob-write { display: flex; align-items: center; gap: 14px; justify-content: center; font-size: 40px; height: 72px; }
.ob-w-arrow { font-size: 24px; color: var(--color-accent); animation: obPulse 1.4s ease-in-out infinite; }
@keyframes obPulse { 0%, 100% { transform: translateX(0); opacity: 1; } 50% { transform: translateX(6px); opacity: 0.5; } }
.ob-assist { position: relative; height: 72px; font-size: 44px; display: flex; align-items: center; justify-content: center; }
.ob-a-spark {
  position: absolute; font-size: 20px; top: 4px; right: 60px;
  animation: obSpin 3s linear infinite;
}
@keyframes obSpin { to { transform: rotate(360deg); } }
.ob-title { font-size: 16px; font-weight: 700; margin: 0 0 8px; }
.ob-desc { font-size: 13px; line-height: 1.8; color: var(--color-ink-body); margin: 0; }
.ob-tip {
  font-size: 12px; line-height: 1.7; color: var(--color-accent);
  background: rgba(0, 0, 0, 0.1); border-radius: 10px; padding: 8px 12px; margin: 12px 0 0;
}

.ob-actions { display: flex; justify-content: space-between; align-items: center; margin-top: 18px; }
.ob-skip {
  background: none; border: none; color: var(--color-ink-muted);
  font-size: 13px; cursor: pointer; font-family: var(--font-ui);
}
.ob-skip:hover { color: var(--color-ink-body); }
.ob-nav { display: flex; gap: 8px; }

.fade-enter-active, .fade-leave-active { transition: opacity 0.2s, transform 0.2s; }
.fade-enter-from { opacity: 0; transform: translateY(8px); }
.fade-leave-to { opacity: 0; transform: translateY(-8px); }
</style>

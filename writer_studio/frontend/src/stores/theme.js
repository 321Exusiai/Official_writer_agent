import { defineStore } from 'pinia'

const KEY = 'ws-theme'

export const useThemeStore = defineStore('theme', {
  state: () => ({ theme: localStorage.getItem(KEY) || 'starry' }),
  actions: {
    apply() {
      document.documentElement.setAttribute('data-theme', this.theme === 'starry' ? '' : this.theme)
    },
    setTheme(t) {
      this.theme = t
      localStorage.setItem(KEY, t)
      this.apply()
    },
  },
})

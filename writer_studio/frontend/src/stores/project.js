import { defineStore } from 'pinia'
import { api } from '../api/client'

export const useProjectStore = defineStore('project', {
  state: () => ({
    projects: [],
    active: null,
    loading: false,
  }),
  getters: {
    filtered(state) {
      return (q) => {
        if (!q) return state.projects
        const kw = q.toLowerCase()
        return state.projects.filter((p) => (p.name + p.description).toLowerCase().includes(kw))
      }
    },
  },
  actions: {
    async fetch() {
      this.loading = true
      try { this.projects = await api.get('/projects') } finally { this.loading = false }
    },
    async create(name, description = '') {
      const p = await api.post('/projects', { name, description })
      this.projects.unshift(p)
      return p
    },
    async remove(id) {
      await api.del(`/projects/${id}`)
      this.projects = this.projects.filter((p) => p.id !== id)
      if (this.active && this.active.id === id) this.active = null
    },
    async select(p) {
      // 列表返回精简摘要；选中时拉取全量详情（含草稿/参考/审查历史）
      this.active = p
      try {
        this.active = await api.get(`/projects/${p.id}`)
      } catch (e) {
        this.active = p
      }
    },
  },
})

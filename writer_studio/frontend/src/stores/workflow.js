import { defineStore } from 'pinia'
import { api } from '../api/client'
import { subscribeProject } from '../api/events'

function emptyItem() {
  return {
    state: 'idle',
    events: [],
    routing: null,
    question: null,
    plan: null,
    draft: '',
    versions: [],
    review: null,
    answers: [], // 问卷已答回顾 [{question, answer}]
    busy: false,
    error: null,
  }
}

export const useWorkflowStore = defineStore('workflow', {
  state: () => ({
    activePid: null,
    items: {}, // { pid: item }
    unsub: null, // 当前 SSE 订阅清理函数
  }),
  getters: {
    cur(state) {
      return state.items[state.activePid] || emptyItem()
    },
  },
  actions: {
    ensure(pid) {
      if (!this.items[pid]) this.items[pid] = emptyItem()
      this.activePid = pid
      return this.items[pid]
    },
    setActive(pid) {
      this.activePid = pid
      if (!this.items[pid]) this.items[pid] = emptyItem()
    },
    async start(pid) {
      const s = this.ensure(pid)
      Object.assign(s, emptyItem())
      s.busy = true
      s.routing = await api.post(`/projects/${pid}/workflow/start`)
      s.state = 'routing'
      s.busy = false
    },
    async answer(pid, text) {
      const s = this.ensure(pid)
      s.busy = true
      s.error = null
      // 记录已答（问卷进度回顾）
      if (s.question && s.question.index) {
        s.answers.push({ question: s.question.question, answer: text })
      }
      const result = await api.post(`/projects/${pid}/workflow/answer`, { text })
      this.applyResult(s, result)
      s.busy = false
    },
    applyResult(s, result) {
      if (!result) return
      if (result.options) {
        s.routing = result; s.question = null; s.state = 'routing'
      } else if (result.index) {
        s.question = result; s.routing = null; s.state = 'questioning'
      } else if (result.doc_type || result.writing_mode) {
        s.plan = result; s.state = 'waiting_approval'
      }
    },
    async confirm(pid) {
      const s = this.ensure(pid)
      s.busy = true
      s.draft = await api.post(`/projects/${pid}/workflow/confirm`)
      s.state = 'reviewing'
      s.busy = false
    },
    async review(pid) {
      const s = this.ensure(pid)
      s.busy = true
      s.review = await api.post(`/projects/${pid}/workflow/review`)
      s.state = 'reviewed'
      s.busy = false
    },
    async fixFinding(pid, index) {
      const s = this.ensure(pid)
      s.busy = true
      s.error = null
      try {
        s.review = await api.post(`/projects/${pid}/workflow/review/fix`, { index })
        s.state = 'reviewed'
        return s.review
      } catch (e) {
        s.error = (e && e.message) || '自动修复失败'
        throw e
      } finally {
        s.busy = false
      }
    },
    async autoHeal(pid) {
      const s = this.ensure(pid)
      s.busy = true
      s.error = null
      try {
        const res = await api.post(`/projects/${pid}/workflow/auto_heal`)
        await this.review(pid)
        return res
      } catch (e) {
        s.error = (e && e.message) || '自愈执行失败'
        throw e
      } finally {
        s.busy = false
      }
    },
    async chunkedDraft(pid) {
      const s = this.ensure(pid)
      s.busy = true
      s.error = null
      try {
        const res = await api.post(`/projects/${pid}/workflow/chunked_draft`)
        s.draft = res.draft
        s.state = 'reviewing'
        return res
      } catch (e) {
        s.error = (e && e.message) || '分段起草失败'
        throw e
      } finally {
        s.busy = false
      }
    },
    async redTeamReview(pid) {
      const s = this.ensure(pid)
      s.busy = true
      s.error = null
      try {
        const res = await api.post(`/projects/${pid}/workflow/red_team`)
        return res
      } catch (e) {
        s.error = (e && e.message) || '红蓝军压力测试失败'
        throw e
      } finally {
        s.busy = false
      }
    },
    async inlineTransform(pid, selection, action, context = '') {
      return await api.post(`/projects/${pid}/workflow/inline_transform`, {
        selection,
        action,
        context,
      })
    },
    async setWeights(pid, weights) {
      return await api.post(`/projects/${pid}/workflow/weights`, { weights })
    },
    async getRevisions(pid) {
      return await api.get(`/projects/${pid}/revisions`)
    },
    async restoreRevision(pid, revId) {
      const s = this.ensure(pid)
      s.busy = true
      try {
        const p = await api.post(`/projects/${pid}/revisions/${revId}/restore`)
        s.draft = p.draft
        return p
      } finally {
        s.busy = false
      }
    },
    async finalize(pid) {
      const s = this.ensure(pid)
      s.busy = true
      const r = await api.post(`/projects/${pid}/workflow/finalize`)
      s.versions = r.versions || []
      s.state = 'completed'
      s.busy = false
      return r
    },
    async rollback(pid, step) {
      const s = this.ensure(pid)
      const r = await api.post(`/projects/${pid}/workflow/rollback`, { step })
      if (step === 'routing' || step === 'questioning') {
        s.plan = null; s.draft = ''; s.versions = []; s.review = null
      } else if (step === 'planning' || step === 'writing') {
        s.draft = ''; s.versions = []; s.review = null
      } else if (step === 'reviewing') {
        s.review = null
      }
      s.routing = null; s.question = null
      s.state = r.state
      if (step === 'routing') this.start(pid)
    },
    attachEvents(pid) {
      if (this.unsub) this.unsub()
      const s = this.ensure(pid)
      this.unsub = subscribeProject(pid, (ev) => {
        s.events.push(ev)
        this.handleEvent(s, ev)
      })
    },
    handleEvent(s, ev) {
      switch (ev.type) {
        case 'routing':
          s.routing = ev.payload
          s.state = 'routing'
          break
        case 'routing_complete':
          s.state = 'questioning'
          break
        case 'question':
          s.question = ev.payload
          s.state = 'questioning'
          break
        case 'plan':
          s.plan = ev.payload
          s.state = 'waiting_approval'
          break
        case 'draft_ready':
          s.draft = (ev.payload && ev.payload.draft) || ev.payload
          s.state = 'reviewing'
          break
        case 'multi_doc':
          s.versions = ev.payload.versions || []
          break
        case 'review_done':
          s.review = ev.payload
          s.state = 'reviewed'
          break
        case 'finalize':
          s.state = 'completed'
          break
        case 'rollback':
          break
        case 'error':
          s.error = ev.payload.message
          break
      }
    },
  },
})

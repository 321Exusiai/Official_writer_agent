import { defineStore } from 'pinia'
import { api } from '../api/client'
import { subscribeProject } from '../api/events'

export const useWorkflowStore = defineStore('workflow', {
  state: () => ({
    state: 'idle',
    events: [],
    routing: null,      // 当前路由问题
    question: null,     // 当前问卷问题
    plan: null,         // 生成的方案
    draft: '',          // 初稿
    versions: [],       // 一文多体
    review: null,       // 审查结果
    busy: false,
    error: null,
  }),
  actions: {
    reset() {
      this.state = 'idle'; this.events = []; this.routing = null
      this.question = null; this.plan = null; this.draft = ''
      this.versions = []; this.review = null; this.error = null
    },
    async start(pid) {
      this.reset()
      this.busy = true
      this.routing = await api.post(`/projects/${pid}/workflow/start`)
      this.state = 'routing'
      this.busy = false
    },
    async answer(pid, text) {
      this.busy = true
      this.error = null
      const result = await api.post(`/projects/${pid}/workflow/answer`, { text })
      this.applyResult(result)
      this.busy = false
    },
    applyResult(result) {
      if (!result) return
      if (result.options) {
        // 路由问题（含 node/question/options）
        this.routing = result; this.question = null; this.state = 'routing'
      } else if (result.index) {
        // 问卷问题（含 index/total/question/why_ask/hint）
        this.question = result; this.routing = null; this.state = 'questioning'
      } else if (result.doc_type || result.writing_mode) {
        // 方案（plan）
        this.plan = result; this.state = 'waiting_approval'
      }
    },
    async confirm(pid) {
      this.busy = true
      this.draft = await api.post(`/projects/${pid}/workflow/confirm`)
      this.state = 'reviewing'
      this.busy = false
    },
    async review(pid) {
      this.busy = true
      this.review = await api.post(`/projects/${pid}/workflow/review`)
      this.state = 'reviewed'
      this.busy = false
    },
    async finalize(pid) {
      this.busy = true
      const r = await api.post(`/projects/${pid}/workflow/finalize`)
      this.versions = r.versions || []
      this.state = 'completed'
      this.busy = false
      return r
    },
    attachEvents(pid) {
      return subscribeProject(pid, (ev) => {
        this.events.push(ev)
        this.handleEvent(ev)
      })
    },
    handleEvent(ev) {
      switch (ev.type) {
        case 'routing': this.routing = ev.payload; this.state = 'routing'; break
        case 'routing_complete': this.state = 'questioning'; break
        case 'question': this.question = ev.payload; break
        case 'plan': this.plan = ev.payload; this.state = 'waiting_approval'; break
        case 'draft_ready': this.draft = ev.payload.word_count; break
        case 'multi_doc': this.versions = ev.payload.versions || []; break
        case 'review_done': this.review = ev.payload; this.state = 'reviewed'; break
        case 'finalize': this.state = 'completed'; break
        case 'error': this.error = ev.payload.message; break
      }
    },
  },
})

// SSE 事件流客户端（EventSource + 断线重连）
export function subscribeProject(projectId, onEvent, { onError } = {}) {
  let es = null
  let closed = false

  function connect() {
    es = new EventSource(`/api/projects/${projectId}/events`)
    es.onmessage = (msg) => {
      try { onEvent(JSON.parse(msg.data)) } catch { /* ignore malformed */ }
    }
    es.onerror = () => {
      if (!closed) {
        // EventSource 会自动重连；这里仅报告，稍后由浏览器重试
        onError && onError()
      }
    }
  }

  connect()
  return () => { closed = true; es && es.close() }
}

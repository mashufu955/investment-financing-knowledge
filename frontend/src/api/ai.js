import request from './request'

/**
 * SSE 流式问答。
 * @param {string} question
 * @param {string|null} sessionId
 * @param {{ onEvent: (event: string, data: any) => void }} handlers
 */
export async function chatStream(question, sessionId, handlers) {
  const token = localStorage.getItem('access_token')
  const resp = await fetch('/api/ai/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: token ? `Bearer ${token}` : '',
    },
    body: JSON.stringify({ question, session_id: sessionId }),
  })
  if (!resp.ok) {
    let message = `请求失败（HTTP ${resp.status}）`
    try {
      const body = await resp.json()
      if (body && body.detail) message = String(body.detail)
    } catch (_) { /* 响应体非 JSON 时保留默认提示 */ }
    handlers.onEvent('error', { message })
    return
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const events = buffer.split('\n\n')
    buffer = events.pop() || ''
    for (const evt of events) {
      const lines = evt.split('\n')
      let event = 'message'
      let data = ''
      for (const line of lines) {
        if (line.startsWith('event:')) event = line.slice(6).trim()
        else if (line.startsWith('data:')) data += line.slice(5).trim()
      }
      try {
        handlers.onEvent(event, JSON.parse(data || '{}'))
      } catch (_) {
        handlers.onEvent(event, data)
      }
    }
  }
}

/** 历史对话会话列表 */
export function listHistorySessions() {
  return request.get('/ai/sessions')
}

/** 单会话消息列表 */
export function listSessionMessages(sessionId) {
  return request.get(`/ai/sessions/${sessionId}/messages`)
}
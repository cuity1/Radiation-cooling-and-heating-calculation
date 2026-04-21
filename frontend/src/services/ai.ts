/**
 * AI 问答服务层
 *
 * SSE + JSON 帧（data: {...}\\n\\n），在 start() 中循环读 fetch body，
 * 避免依赖 ReadableStreamDefaultController 对 pull 的重复调度（否则易首包卡住、只收到 done）。
 */

export type ChatRole = 'user' | 'assistant' | 'system'

export type ContentBlock =
  | { type: 'text'; text: string }
  | { type: 'image_url'; image_url: { url: string } }

export interface ChatMessage {
  role: ChatRole
  content: string | ContentBlock[]
}

export function exportChatAsMarkdown(messages: ChatMessage[]): void {
  const lines: string[] = [
    '# AI 问答记录',
    '',
    `> 导出时间：${new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}`,
    '',
  ]
  for (const msg of messages) {
    const roleLabel = msg.role === 'user' ? '**用户**' : msg.role === 'assistant' ? '**AI 助手**' : '**系统**'
    lines.push(`## ${roleLabel}`)
    lines.push('')
    lines.push(msg.content)
    lines.push('')
    lines.push('---')
    lines.push('')
  }

  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `ai-chat-${Date.now()}.md`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ---------------------------------------------------------------------------
// SSE：按 \\n\\n 分帧
// ---------------------------------------------------------------------------

function parseSseEvents(buffer: string): { rest: string; events: string[] } {
  const normalized = buffer.replace(/\r\n/g, '\n')
  const events: string[] = []
  let rest = normalized
  while (true) {
    const sep = rest.indexOf('\n\n')
    if (sep === -1) break
    events.push(rest.slice(0, sep))
    rest = rest.slice(sep + 2)
  }
  return { rest, events }
}

function parseJsonPayload(payload: string): Record<string, unknown> | null {
  try {
    return JSON.parse(payload) as Record<string, unknown>
  } catch {
    return null
  }
}

/** 从 JSON 事件中取出增量文本（兼容 text / content 等字段） */
function deltaTextFromEvent(obj: Record<string, unknown>): string | undefined {
  const t = obj.type
  if (t !== 'delta' && t !== 'chunk') return undefined
  const raw = obj.text ?? obj.content
  if (typeof raw === 'string') return raw
  return undefined
}

function handleDataLine(
  line: string,
  controller: ReadableStreamDefaultController<string>,
  reader: ReadableStreamDefaultReader<Uint8Array>,
): 'done' | 'error' | 'continue' {
  const trimmed = line.replace(/^\uFEFF/, '').trimStart()
  if (!trimmed.startsWith('data:')) return 'continue'
  const payload = trimmed.slice(5).trimStart()

  if (payload === '[DONE]') {
    controller.close()
    void reader.cancel()
    return 'done'
  }
  if (payload.startsWith('[ERROR]')) {
    controller.error(new Error(payload.slice(7).trim()))
    return 'error'
  }

  const obj = parseJsonPayload(payload)
  if (obj) {
    const delta = deltaTextFromEvent(obj)
    if (delta !== undefined) {
      controller.enqueue(delta)
      return 'continue'
    }
    if (obj.type === 'done') {
      controller.close()
      void reader.cancel()
      return 'done'
    }
    if (obj.type === 'error') {
      const msg = obj.message
      controller.error(new Error(typeof msg === 'string' ? msg : 'AI 错误'))
      return 'error'
    }
    return 'continue'
  }

  if (payload) {
    controller.enqueue(payload)
  }
  return 'continue'
}

function dispatchEventBlock(
  block: string,
  controller: ReadableStreamDefaultController<string>,
  reader: ReadableStreamDefaultReader<Uint8Array>,
): 'done' | 'error' | 'continue' {
  for (const ln of block.split('\n')) {
    const t = ln.trim()
    if (!t) continue
    const r = handleDataLine(t, controller, reader)
    if (r !== 'continue') return r
  }
  return 'continue'
}

function flushBuffer(
  buffer: string,
  controller: ReadableStreamDefaultController<string>,
  reader: ReadableStreamDefaultReader<Uint8Array>,
): { rest: string; stop: boolean } {
  const { rest, events } = parseSseEvents(buffer)
  for (const ev of events) {
    const r = dispatchEventBlock(ev, controller, reader)
    if (r !== 'continue') return { rest, stop: true }
  }
  return { rest, stop: false }
}

/** 处理连接结束时可能缺少末尾 \\n\\n 的半行 */
function flushTailLines(
  rest: string,
  controller: ReadableStreamDefaultController<string>,
  reader: ReadableStreamDefaultReader<Uint8Array>,
): boolean {
  const normalized = rest.replace(/\r\n/g, '\n').trim()
  if (!normalized) return false
  for (const line of normalized.split('\n')) {
    const t = line.trim()
    if (!t) continue
    const r = handleDataLine(t, controller, reader)
    if (r !== 'continue') return true
  }
  return false
}

/**
 * 发送消息并返回文本增量流。
 */
export async function streamChat(messages: ChatMessage[]): Promise<ReadableStream<string>> {
  const response = await fetch('/api/ai/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages }),
    credentials: 'include',
  })

  if (!response.ok) {
    const detail = await response.text().catch(() => '')
    throw new Error(`请求失败 (${response.status})：${detail}`)
  }

  if (!response.body) {
    throw new Error('响应体为空')
  }

  const networkReader = response.body.getReader()

  return new ReadableStream<string>({
    async start(controller) {
      const decoder = new TextDecoder('utf-8')
      let buffer = ''
      try {
        while (true) {
          const { done, value } = await networkReader.read()
          if (done) {
            buffer += decoder.decode()
            const { rest, stop } = flushBuffer(buffer, controller, networkReader)
            if (stop) return
            if (flushTailLines(rest, controller, networkReader)) return
            controller.close()
            return
          }

          buffer += decoder.decode(value, { stream: true })
          const { rest, stop } = flushBuffer(buffer, controller, networkReader)
          buffer = rest
          if (stop) return
        }
      } catch (e) {
        controller.error(e instanceof Error ? e : new Error(String(e)))
      }
    },
    cancel() {
      networkReader.cancel()
    },
  })
}

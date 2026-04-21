import { useState, useRef, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Send, Trash2, Download, BotMessageSquare, User, Image as ImageIcon, X } from 'lucide-react'
import clsx from 'clsx'
import Button from '../components/ui/Button'
import { streamChat, exportChatAsMarkdown, type ChatMessage, type ContentBlock } from '../services/ai'
import { useAuth } from '../context/AuthContext'
import { MdRenderer, normalizeLatexDisplayDelimiters } from '../help/mdRenderer'

interface PendingImage {
  id: string
  url: string   // 预览用的 object URL
  base64: string
}

// 限制：最多 5 张，单张 ≤ 5MB
const MAX_IMAGES = 5
const MAX_SIZE_MB = 5

export default function AIChatPage() {
  const { t } = useTranslation()
  const { user } = useAuth()

  // ---------------------------------------------------------------------------
  // 对话状态
  // ---------------------------------------------------------------------------
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  // 消息列表滚动引用
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // ---------------------------------------------------------------------------
  // 图片上传状态
  // ---------------------------------------------------------------------------
  const [pendingImages, setPendingImages] = useState<PendingImage[]>([])

  // ---------------------------------------------------------------------------
  // 图片处理
  // ---------------------------------------------------------------------------
  const addImages = useCallback((files: FileList | null) => {
    if (!files || files.length === 0) return
    const remaining = MAX_IMAGES - pendingImages.length
    if (remaining <= 0) {
      setErrorMsg(`最多上传 ${MAX_IMAGES} 张图片`)
      return
    }
    const toProcess = Array.from(files).slice(0, remaining)

    toProcess.forEach(file => {
      if (file.size > MAX_SIZE_MB * 1024 * 1024) {
        setErrorMsg(`${file.name} 超过 ${MAX_SIZE_MB}MB 限制`)
        return
      }
      if (!file.type.startsWith('image/')) {
        setErrorMsg(`${file.name} 不是图片`)
        return
      }
      const reader = new FileReader()
      reader.onload = (e) => {
        const dataUrl = e.target?.result as string
        const base64 = dataUrl.split(',')[1]
        setPendingImages(prev => [
          ...prev,
          { id: Math.random().toString(36).slice(2), url: dataUrl, base64 },
        ])
      }
      reader.readAsDataURL(file)
    })
  }, [pendingImages.length])

  const removeImage = (id: string) => {
    setPendingImages(prev => {
      const img = prev.find(p => p.id === id)
      if (img) URL.revokeObjectURL(img.url)
      return prev.filter(p => p.id !== id)
    })
  }

  // ---------------------------------------------------------------------------
  // 辅助函数
  // ---------------------------------------------------------------------------
  const scrollToBottom = () => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  // ---------------------------------------------------------------------------
  // 发送消息 → 调用流式 API → 逐 token 追加 AI 回复
  // ---------------------------------------------------------------------------
  const handleSend = useCallback(async () => {
    const trimmed = input.trim()
    if (!trimmed && pendingImages.length === 0) return
    if (isGenerating) return

    setErrorMsg(null)

    // 构建消息内容：文本 + 图片块
    const contentBlocks: ContentBlock[] = trimmed
      ? [{ type: 'text', text: trimmed }]
      : []
    pendingImages.forEach(img => {
      contentBlocks.push({
        type: 'image_url',
        image_url: { url: `data:image/jpeg;base64,${img.base64}` },
      })
    })

    const userMsg: ChatMessage = { role: 'user', content: contentBlocks }
    let assistantIdx = 0
    const historyForApi: ChatMessage[] = [...messages, userMsg]

    setMessages(prev => {
      const next: ChatMessage[] = [...prev, userMsg, { role: 'assistant', content: '' }]
      assistantIdx = next.length - 1
      return next
    })
    setInput('')
    setPendingImages([])
    scrollToBottom()

    setIsGenerating(true)

    try {
      const stream = await streamChat(historyForApi)
      const reader = stream.getReader()

      let accumulated = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        // ai.ts 返回的 ReadableStream<string>，value 已经是解析后的文本
        accumulated += value

        // 4. 流式更新 AI 消息内容
        setMessages(prev => {
          const updated = [...prev]
          updated[assistantIdx] = { role: 'assistant' as const, content: accumulated }
          return updated
        })
      }
    } catch (e: unknown) {
      const err = e instanceof Error ? e.message : String(e)
      // 检测认证失效
      if (err.includes('401')) {
        setErrorMsg('登录已过期，请刷新页面后重新登录')
      } else {
        setErrorMsg(err)
      }
      // 仅移除仍为空的占位助手消息，已流式写入的内容保留
      setMessages(prev => {
        const last = prev[prev.length - 1]
        if (last?.role === 'assistant' && last.content === '') {
          return prev.slice(0, -1)
        }
        return prev
      })
    } finally {
      setIsGenerating(false)
    }
  }, [input, messages, isGenerating])

  // ---------------------------------------------------------------------------
  // 新建对话（清空历史）
  // ---------------------------------------------------------------------------
  const handleNewChat = () => {
    setMessages([])
    setErrorMsg(null)
    setInput('')
    inputRef.current?.focus()
  }

  // ---------------------------------------------------------------------------
  // 导出对话为 Markdown 文件
  // ---------------------------------------------------------------------------
  const handleExport = () => {
    if (messages.length === 0) return
    exportChatAsMarkdown(messages)
  }

  // ---------------------------------------------------------------------------
  // 自动聚焦 + 发送后滚动
  // ---------------------------------------------------------------------------
  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // ---------------------------------------------------------------------------
  // 粘贴图片（Ctrl+V / Cmd+V）
  // ---------------------------------------------------------------------------
  useEffect(() => {
    const textarea = inputRef.current
    if (!textarea) return
    const onPaste = (e: ClipboardEvent) => {
      const items = e.clipboardData?.items
      if (!items) return
      const imageFiles: File[] = []
      for (const item of items) {
        if (item.kind === 'file' && item.type.startsWith('image/')) {
          const file = item.getAsFile()
          if (file) imageFiles.push(file)
        }
      }
      if (imageFiles.length > 0) {
        e.preventDefault()
        addImages(imageFiles)
      }
    }
    textarea.addEventListener('paste', onPaste)
    return () => textarea.removeEventListener('paste', onPaste)
  }, [addImages])

  // Enter 发送，Shift+Enter 换行
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // ---------------------------------------------------------------------------
  // 渲染
  // ---------------------------------------------------------------------------
  return (
    <div className="flex flex-col h-full" style={{ height: 'calc(100vh - 180px)', minHeight: '400px' }}>

      {/* 顶部栏：标题 + 操作按钮 */}
      <div className="flex items-center justify-between mb-4 gap-3 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent-soft text-accent shadow-glow border border-border-accent">
            <BotMessageSquare size={18} />
          </div>
          <div>
            <div className="text-base font-semibold text-text-primary tracking-tight">{t('aiChat.title')}</div>
            <div className="text-xs text-text-muted">{user?.username}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleExport}
            disabled={messages.length === 0}
            title={t('aiChat.export')}
          >
            <Download size={14} />
            <span className="hidden sm:inline">{t('aiChat.export')}</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleNewChat}
            disabled={isGenerating || messages.length === 0}
            title={t('aiChat.newChat')}
          >
            <Trash2 size={14} />
            <span className="hidden sm:inline">{t('aiChat.newChat')}</span>
          </Button>
        </div>
      </div>

      {/* 错误提示 */}
      {errorMsg && (
        <div className="mb-3 rounded-lg border border-danger-border bg-danger-soft px-3 py-2 text-xs text-text-danger flex-shrink-0">
          {errorMsg}
        </div>
      )}

      {/* 消息列表（可滚动） */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1 scroll-smooth">

        {/* 空状态引导语 */}
        {messages.length === 0 && !isGenerating && (
          <div className="flex flex-col items-center justify-center h-full min-h-[200px] text-center select-none pointer-events-none">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent-soft text-accent shadow-glow border border-border-accent mb-4">
              <BotMessageSquare size={28} />
            </div>
            <div className="text-base font-semibold text-text-primary mb-1">{t('aiChat.emptyTitle')}</div>
            <div className="text-sm text-text-muted max-w-sm leading-relaxed">
              {t('aiChat.emptyDesc')}
            </div>
          </div>
        )}

        {/* 消息气泡 */}
        {messages.map((msg, idx) => (
          <MessageBubble
            key={idx}
            message={msg}
            asPlainText={
              isGenerating &&
              idx === messages.length - 1 &&
              msg.role === 'assistant'
            }
          />
        ))}

        {/* 仅在尚无增量文本时显示加载动画，避免与流式正文叠在一起 */}
        {isGenerating &&
          messages[messages.length - 1]?.role === 'assistant' &&
          messages[messages.length - 1]?.content === '' && (
          <div className="flex items-start gap-2.5">
            <div className="flex-shrink-0 flex h-8 w-8 items-center justify-center rounded-full bg-accent-soft text-accent border border-border-accent mt-0.5">
              <BotMessageSquare size={14} />
            </div>
            <div className="flex-shrink-0 rounded-2xl bg-bg-elevated border border-border px-4 py-3">
              <GeneratingDots />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* 图片预览区 */}
      {pendingImages.length > 0 && (
        <div className="flex-shrink-0 flex items-center gap-2 mb-2 overflow-x-auto pb-1">
          {pendingImages.map(img => (
            <div key={img.id} className="relative flex-shrink-0 group">
              <img
                src={img.url}
                alt="preview"
                className="h-16 w-16 object-cover rounded-lg border border-border"
              />
              <button
                onClick={() => removeImage(img.id)}
                className="absolute -top-1.5 -right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-white opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <X size={10} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* 输入区（固定在底部） */}
      <div className="flex-shrink-0 mt-2">
        <div className="flex items-end gap-2 rounded-field border border-border bg-bg-elevated px-3 py-2.5 focus-within:border-border-accent transition-all duration-150">
          {/* 图片上传按钮 */}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isGenerating || pendingImages.length >= MAX_IMAGES}
            className={clsx(
              'flex-shrink-0 rounded-lg p-1.5 transition-all duration-150',
              pendingImages.length >= MAX_IMAGES
                ? 'text-text-muted cursor-not-allowed'
                : 'text-text-secondary hover:bg-bg-elevated/80',
            )}
            title="上传图片"
          >
            <ImageIcon size={16} />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={e => addImages(e.target.files)}
            onClick={e => { (e.target as HTMLInputElement).value = '' }}
          />
          <textarea
            ref={inputRef}
            rows={1}
            className="flex-1 bg-transparent text-sm text-text-primary placeholder:text-text-muted resize-none focus:outline-none max-h-[120px] overflow-y-auto"
            placeholder={t('aiChat.placeholder')}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isGenerating}
          />
          <button
            className={clsx(
              'flex-shrink-0 rounded-lg p-1.5 transition-all duration-150',
              isGenerating || (!input.trim() && pendingImages.length === 0)
                ? 'text-text-muted cursor-not-allowed'
                : 'text-accent hover:bg-accent-soft',
            )}
            onClick={handleSend}
            disabled={isGenerating || (!input.trim() && pendingImages.length === 0)}
            title={t('aiChat.send')}
          >
            <Send size={16} />
          </button>
        </div>
        <div className="mt-1.5 text-center text-[11px] text-text-tertiary">
          {t('aiChat.hint')}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// 消息气泡组件
// ---------------------------------------------------------------------------

function MessageBubble({
  message,
  asPlainText = false,
}: {
  message: ChatMessage
  /** 流式生成中避免每 token 全量 MD+KaTeX 重算导致主线程卡死 */
  asPlainText?: boolean
}) {
  const isUser = message.role === 'user'

  // 消息内容：字符串 或 ContentBlock[]
  const blocks: ContentBlock[] =
    typeof message.content === 'string'
      ? [{ type: 'text', text: message.content }]
      : message.content

  return (
    <div className="flex items-start gap-2.5">
      {/* 头像始终在左侧 */}
      <div
        className={clsx(
          'flex-shrink-0 flex h-8 w-8 items-center justify-center rounded-full border mt-0.5',
          isUser
            ? 'bg-bg-elevated text-text-muted border-border order-2'
            : 'bg-accent-soft text-accent border-border-accent order-1',
        )}
      >
        {isUser ? <User size={14} /> : <BotMessageSquare size={14} />}
      </div>

      {/* 消息内容气泡：用户消息靠右，AI 消息靠左 */}
      <div
        className={clsx(
          'max-w-[76%] rounded-2xl px-4 py-3 flex flex-col gap-2',
          isUser
            ? 'bg-accent text-white rounded-tr-sm order-1 ml-auto'
            : 'bg-bg-elevated text-text-primary border border-border rounded-tl-sm order-2 mr-auto',
        )}
      >
        {blocks.map((block, i) => {
          if (block.type === 'image_url') {
            return (
              <img
                key={i}
                src={block.image_url.url}
                alt="user image"
                className="max-w-full rounded-lg object-contain"
                style={{ maxHeight: '20rem' }}
              />
            )
          }
          if (asPlainText) {
            return (
              <span key={i} className="whitespace-pre-wrap break-words text-sm leading-relaxed text-inherit">
                {block.text}
              </span>
            )
          }
          if (typeof block.text === 'string') {
            return (
              <div
                key={i}
                className="text-sm leading-relaxed break-words min-w-0"
              >
                <MdRenderer md={normalizeLatexDisplayDelimiters(block.text)} />
              </div>
            )
          }
          return null
        })}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// AI 生成中动画
// ---------------------------------------------------------------------------

function GeneratingDots() {
  return (
    <div className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-bg-elevated border border-border">
      <span className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: '0ms' }} />
      <span className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: '150ms' }} />
      <span className="w-1.5 h-1.5 rounded-full bg-accent animate-bounce" style={{ animationDelay: '300ms' }} />
    </div>
  )
}
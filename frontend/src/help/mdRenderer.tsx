import React, { useCallback, useEffect, useRef, useState, useMemo } from 'react'
import katex from 'katex'

// ─── Types ────────────────────────────────────────────────────────────────────

type InlineToken =
  | { kind: 'text'; text: string }
  | { kind: 'code'; text: string }
  | { kind: 'link'; text: string; href: string }
  | { kind: 'math'; text: string }
  | { kind: 'bold'; text: string }
  | { kind: 'italic'; text: string }

type BlockKind =
  | 'heading'
  | 'paragraph'
  | 'unordered_list'
  | 'ordered_list'
  | 'blockquote'
  | 'code_block'
  | 'hr'
  | 'table'
  | 'block_math'

export interface TocEntry {
  level: number
  text: string
  id: string
}

// ─── Utilities ────────────────────────────────────────────────────────────────

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

// ─── Inline parsing ────────────────────────────────────────────────────────────

function parseInline(raw: string): InlineToken[] {
  const tokens: InlineToken[] = []
  let i = 0
  const s = raw

  while (i < s.length) {
    // inline math \(...\) 必须在「通用 \ 转义」之前，否则会吃掉反斜杠
    if (s[i] === '\\' && i + 1 < s.length && s[i + 1] === '(') {
      let j = i + 2
      let found = false
      while (j < s.length - 1) {
        if (s[j] === '\\' && s[j + 1] === ')') {
          tokens.push({ kind: 'math', text: s.slice(i + 2, j) })
          i = j + 2
          found = true
          break
        }
        j++
      }
      if (found) continue
    }

    // 仅处理 Markdown 需要的转义，不要把 LaTeX 的 \text、\frac 等吃掉
    if (s[i] === '\\' && i + 1 < s.length && '*_`'.includes(s[i + 1])) {
      tokens.push({ kind: 'text', text: s[i + 1] })
      i += 2
      continue
    }

    // bold **...**
    if (s[i] === '*' && s[i + 1] === '*') {
      let j = i + 2
      while (j < s.length && !(s[j] === '*' && s[j + 1] === '*')) j++
      if (j < s.length) {
        tokens.push({ kind: 'bold', text: s.slice(i + 2, j) })
        i = j + 2
        continue
      }
    }

    // italic *...*
    if (s[i] === '*') {
      let j = i + 1
      while (j < s.length && s[j] !== '*') j++
      if (j < s.length) {
        tokens.push({ kind: 'italic', text: s.slice(i + 1, j) })
        i = j + 1
        continue
      }
    }

    // inline math $...$
    if (s[i] === '$') {
      let j = i + 1
      while (j < s.length && s[j] !== '$') j++
      if (j < s.length) {
        if (j > i + 1) tokens.push({ kind: 'math', text: s.slice(i + 1, j) })
        i = j + 1
        continue
      }
    }

    if (s[i] === '[') {
      let j = i + 1
      while (j < s.length && s[j] !== ']') j++
      if (j < s.length && s[j + 1] === '(') {
        const linkText = s.slice(i + 1, j)
        let k = j + 2
        while (k < s.length && s[k] !== ')') k++
        if (k < s.length) {
          tokens.push({ kind: 'link', text: linkText, href: s.slice(j + 2, k) })
          i = k + 1
          continue
        }
      }
    }

    if (s[i] === '`') {
      let j = i + 1
      while (j < s.length && s[j] !== '`') j++
      if (j < s.length) {
        tokens.push({ kind: 'code', text: s.slice(i + 1, j) })
        i = j + 1
        continue
      }
    }

    let j = i
    while (j < s.length) {
      const c = s[j]
      if (c === '*' || c === '$' || c === '[' || c === '`') break
      j++
    }
    if (j > i) {
      tokens.push({ kind: 'text', text: s.slice(i, j) })
      i = j
    } else {
      tokens.push({ kind: 'text', text: s[i] })
      i += 1
    }
  }

  return tokens
}

function safeKatex(expr: string, displayMode: boolean): string {
  try {
    return katex.renderToString(expr, { displayMode, throwOnError: false })
  } catch {
    return displayMode
      ? `<pre class="text-red-400 text-xs">Invalid formula: ${expr}</pre>`
      : `<span class="text-red-400 text-xs">${expr}</span>`
  }
}

function renderTokens(tokens: InlineToken[], keyPrefix: string): React.ReactNode[] {
  return tokens.map((t, i) => {
    const k = `${keyPrefix}-${i}`
    switch (t.kind) {
      case 'code':
        return (
          <code key={k} className="rounded border border-border bg-bg-elevated px-1 py-0.5 font-mono text-[0.85em] text-text-primary break-all">
            {t.text}
          </code>
        )
      case 'link':
        return (
          <a key={k} href={t.href} target="_blank" rel="noopener noreferrer" className="text-accent underline underline-offset-2 hover:text-accent/80">
            {t.text}
          </a>
        )
      case 'math':
        return (
          <span key={k} className="katex-inline" dangerouslySetInnerHTML={{ __html: safeKatex(t.text, false) }} />
        )
      case 'bold':
        return (
          <strong key={k} className="font-semibold text-text-primary">{t.text}</strong>
        )
      case 'italic':
        return (
          <em key={k} className="italic text-text-secondary">{t.text}</em>
        )
      default:
        return <React.Fragment key={k}>{t.text}</React.Fragment>
    }
  })
}

// ─── Table parsing ────────────────────────────────────────────────────────────

function parseTableRow(line: string): string[] {
  return line.split('|').filter((_, i, a) => i > 0 && i < a.length - 1).map(c => c.trim())
}

function isTableSep(line: string): boolean {
  return /^\|?[\s\-:|]+\|[\s\-:|]*$/.test(line.trim())
}

function parseAlign(sepLine: string): ('left' | 'center' | 'right')[] {
  return parseTableRow(sepLine).map(cell => {
    const t = cell.trim()
    if (t.startsWith(':') && t.endsWith(':')) return 'center'
    if (t.endsWith(':')) return 'right'
    return 'left'
  })
}

// ─── Block parsing ────────────────────────────────────────────────────────────

interface Block {
  kind: BlockKind
  content: React.ReactNode
  headingLevel?: number
  headingText?: string
  headingId?: string
}

function isHeadingEnd(line: string): boolean {
  const trimmed = line.trim()
  return trimmed === '' || trimmed === '$$' || /^#{1,6}\s+/.test(trimmed) ||
    trimmed.startsWith('>') || trimmed.startsWith('- ') ||
    /^\s*\d+\.\s+/.test(trimmed) || trimmed.startsWith('```') || /^---/.test(trimmed)
}

function parseBlocks(md: string): Block[] {
  const lines = md.replace(/\r\n/g, '\n').split('\n')
  const blocks: Block[] = []
  let i = 0

  while (i < lines.length) {
    const line = lines[i]
    const trimmed = line.trim()

    if (trimmed === '') { i++; continue }

    if (trimmed === '$$') {
      const buf: string[] = []
      i++
      while (i < lines.length && lines[i].trim() !== '$$') { buf.push(lines[i]); i++ }
      if (i < lines.length) i++
      const content = buf.join('\n').trim()
      blocks.push({
        kind: 'block_math',
        content: (
          <div className="overflow-auto rounded-field border border-border bg-bg-elevated px-4 py-3 my-3" dangerouslySetInnerHTML={{ __html: safeKatex(content, true) }} />
        ),
      })
      continue
    }

    if (/^---+\s*$/.test(trimmed)) {
      blocks.push({ kind: 'hr', content: <hr className="my-4 border-border" /> })
      i++; continue
    }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/)
    if (headingMatch) {
      const level = headingMatch[1].length
      const rawText = headingMatch[2].trim()
      const id = slugify(rawText)
      const cls =
        level === 1 ? 'text-xl font-bold text-text-primary mt-6 mb-2' :
        level === 2 ? 'text-lg font-semibold text-text-primary mt-5 mb-2' :
        level === 3 ? 'text-base font-semibold text-text-primary mt-4 mb-1' :
        'text-sm font-medium text-text-secondary mt-3 mb-1'
      blocks.push({
        kind: 'heading', headingLevel: level, headingText: rawText, headingId: id,
        content: <div id={id} className={`${cls} scroll-mt-20`}>{renderTokens(parseInline(rawText), `h${level}`)}</div>,
      })
      i++; continue
    }

    if (trimmed.startsWith('>')) {
      const buf: string[] = []
      while (i < lines.length && lines[i].trim().startsWith('>')) { buf.push(lines[i].trim().replace(/^>\s?/, '')); i++ }
      blocks.push({
        kind: 'blockquote',
        content: (
          <blockquote className="rounded-xl border-l-4 border-accent bg-bg-elevated px-4 py-3 my-2 text-sm text-text-secondary italic">
            {buf.map((t, idx) => <div key={idx} className="mb-1 last:mb-0">{renderTokens(parseInline(t), `q-${idx}`)}</div>)}
          </blockquote>
        ),
      })
      continue
    }

    if (trimmed.startsWith('- ')) {
      const items: string[] = []
      while (i < lines.length && lines[i].trim().startsWith('- ')) { items.push(lines[i].trim().slice(2)); i++ }
      blocks.push({
        kind: 'unordered_list',
        content: <ul className="list-disc pl-5 space-y-1 text-sm text-text-secondary my-2">
          {items.map((t, idx) => <li key={idx} className="leading-relaxed">{renderTokens(parseInline(t), `ul-${idx}`)}</li>)}
        </ul>,
      })
      continue
    }

    if (/^\s*\d+\.\s+/.test(trimmed)) {
      const items: string[] = []
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) { items.push(lines[i].trim().replace(/^\d+\.\s+/, '')); i++ }
      blocks.push({
        kind: 'ordered_list',
        content: <ol className="list-decimal pl-5 space-y-1 text-sm text-text-secondary my-2">
          {items.map((t, idx) => <li key={idx} className="leading-relaxed">{renderTokens(parseInline(t), `ol-${idx}`)}</li>)}
        </ol>,
      })
      continue
    }

    if (trimmed.startsWith('```')) {
      const buf: string[] = []
      i++
      while (i < lines.length && !lines[i].trim().startsWith('```')) { buf.push(lines[i]); i++ }
      if (i < lines.length) i++
      blocks.push({
        kind: 'code_block',
        content: <pre className="overflow-x-auto rounded-field border border-border bg-bg-elevated px-4 py-3 my-2 text-xs font-mono text-text-primary leading-relaxed"><code>{buf.join('\n')}</code></pre>,
      })
      continue
    }

    if (trimmed.includes('|') && !isHeadingEnd(trimmed)) {
      let sepIdx = -1
      for (let j = i + 1; j < lines.length; j++) {
        if (isTableSep(lines[j])) { sepIdx = j; break }
        if (isHeadingEnd(lines[j])) break
      }

      if (sepIdx !== -1) {
        const headers = parseTableRow(lines[i])
        const aligns = parseAlign(lines[sepIdx])
        const rows: string[][] = []
        for (let r = sepIdx + 1; r < lines.length; r++) {
          const rowLine = lines[r].trim()
          if (rowLine === '' || isHeadingEnd(rowLine)) break
          if (!rowLine.includes('|')) break
          rows.push(parseTableRow(rowLine))
          if (rows.length > 200) break
        }

        if (rows.length > 0) {
          const thClass = 'px-3 py-2 text-xs font-semibold text-text-primary bg-bg-elevated border-b border-border'
          const tdClass = 'px-3 py-1.5 text-xs text-text-secondary border-b border-border last:border-b-0'
          blocks.push({
            kind: 'table',
            content: (
              <div className="overflow-x-auto rounded-field border border-border my-3">
                <table className="w-full border-collapse">
                  <thead>
                    <tr>
                      {headers.map((h, ci) => {
                        const al = aligns[ci] || 'left'
                        const alCls = al === 'center' ? 'text-center' : al === 'right' ? 'text-right' : 'text-left'
                        return <th key={ci} className={`${thClass} ${alCls}`}>{renderTokens(parseInline(h), `th-${ci}`)}</th>
                      })}
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, ri) => (
                      <tr key={ri} className="hover:bg-bg-elevated/50 transition-colors">
                        {row.map((cell, ci) => {
                          const al = aligns[ci] || 'left'
                          const alCls = al === 'center' ? 'text-center' : al === 'right' ? 'text-right' : 'text-left'
                          return <td key={ci} className={`${tdClass} ${alCls}`}>{renderTokens(parseInline(cell), `td-${ri}-${ci}`)}</td>
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ),
          })
          i = sepIdx + 1 + rows.length
          continue
        }
      }
    }

    // 行内仅含 $$ 的多行块（已在上面 line 217 处理）
    // 此处处理：以 $$ 开头但含有内容的情况（可能是跨行块的起点，也可能是单行 display math）
    if (trimmed.startsWith('$$')) {
      const endIdx = trimmed.indexOf('$$', 2)
      if (endIdx !== -1 && endIdx <= trimmed.length - 2) {
        // 单行 display math: $$formula$$
        const content = trimmed.slice(2, endIdx)
        blocks.push({
          kind: 'block_math',
          content: (
            <div className="overflow-auto rounded-field border border-border bg-bg-elevated px-4 py-3 my-3" dangerouslySetInnerHTML={{ __html: safeKatex(content, true) }} />
          ),
        })
        i++
        continue
      }
    }

    const buf: string[] = []
    while (i < lines.length) {
      const cur = lines[i]
      if (cur.trim() === '') break
      if (/^#{1,6}\s+/.test(cur)) break
      if (cur.trim().startsWith('>')) break
      if (cur.trim().startsWith('- ')) break
      if (/^\s*\d+\.\s+/.test(cur)) break
      if (cur.trim().startsWith('```')) break
      if (/^---/.test(cur)) break
      buf.push(cur)
      i++
    }
    if (buf.length > 0) {
      blocks.push({
        kind: 'paragraph',
        content: <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-secondary my-1">{renderTokens(parseInline(buf.join('\n')), 'p')}</p>,
      })
    }
  }

  return blocks
}

// ─── AI / 外部 Markdown 预处理 ────────────────────────────────────────────────

/** 将 LaTeX 行间 \[ ... \] 转为本渲染器识别的 $$ ... $$（避免模型输出无法进块级公式） */
export function normalizeLatexDisplayDelimiters(md: string): string {
  return md.replace(/\r\n/g, '\n')
    // 行间 \[ ... \]  → $$ ... $$
    .replace(/\\\[/g, '$$').replace(/\\\]/g, '$$')
    // 行内 \( ... \)  → $...$
    .replace(/\\\(/g, '$').replace(/\\\)/g, '$')
}

// ─── TOC ──────────────────────────────────────────────────────────────────────

export function parseToc(md: string): TocEntry[] {
  const toc: TocEntry[] = []
  const lines = md.replace(/\r\n/g, '\n').split('\n')
  for (const line of lines) {
    const m = line.match(/^(#{1,6})\s+(.*)$/)
    if (m) { toc.push({ level: m[1].length, text: m[2].trim(), id: slugify(m[2].trim()) }) }
  }
  return toc
}

// ─── Renderer (synchronous) ────────────────────────────────────────────────────

export function renderBlocks(md: string) {
  return parseBlocks(md)
}

// ─── Async Renderer (chunked, for very large docs) ────────────────────────────

export function renderBlocksAsync(md: string, onChunk: (blocks: Block[], done: boolean) => void, chunkSize = 50): void {
  const lines = md.replace(/\r\n/g, '\n').split('\n')
  const totalLines = lines.length

  const parseLine = (i: number): { consumed: number; block: Block | null } => {
    if (i >= totalLines) return { consumed: 0, block: null }
    const line = lines[i]
    const trimmed = line.trim()

    if (trimmed === '') return { consumed: 1, block: null }

    if (trimmed.startsWith('$$')) {
      const endIdx = trimmed.indexOf('$$', 2)
      if (endIdx !== -1 && endIdx <= trimmed.length - 2) {
        const content = trimmed.slice(2, endIdx)
        return { consumed: 1, block: { kind: 'block_math', content: <div className="overflow-auto rounded-field border border-border bg-bg-elevated px-4 py-3 my-3" dangerouslySetInnerHTML={{ __html: safeKatex(content, true) }} /> } }
      }
    }

    if (/^---+\s*$/.test(trimmed)) return { consumed: 1, block: { kind: 'hr', content: <hr className="my-4 border-border" /> } }

    const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/)
    if (headingMatch) {
      const level = headingMatch[1].length
      const rawText = headingMatch[2].trim()
      const id = slugify(rawText)
      const cls = level === 1 ? 'text-xl font-bold text-text-primary mt-6 mb-2' : level === 2 ? 'text-lg font-semibold text-text-primary mt-5 mb-2' : level === 3 ? 'text-base font-semibold text-text-primary mt-4 mb-1' : 'text-sm font-medium text-text-secondary mt-3 mb-1'
      return { consumed: 1, block: { kind: 'heading', headingLevel: level, headingText: rawText, headingId: id, content: <div id={id} className={`${cls} scroll-mt-20`}>{renderTokens(parseInline(rawText), `h${level}`)}</div> } }
    }

    if (trimmed.startsWith('>')) {
      const buf: string[] = []; let j = i
      while (j < totalLines && lines[j].trim().startsWith('>')) { buf.push(lines[j].trim().replace(/^>\s?/, '')); j++ }
      return { consumed: j - i, block: { kind: 'blockquote', content: <blockquote className="rounded-xl border-l-4 border-accent bg-bg-elevated px-4 py-3 my-2 text-sm text-text-secondary italic">{buf.map((t, idx) => <div key={idx} className="mb-1 last:mb-0">{renderTokens(parseInline(t), `q-${idx}`)}</div>)}</blockquote> } }
    }

    if (trimmed.startsWith('- ')) {
      const items: string[] = []; let j = i
      while (j < totalLines && lines[j].trim().startsWith('- ')) { items.push(lines[j].trim().slice(2)); j++ }
      return { consumed: j - i, block: { kind: 'unordered_list', content: <ul className="list-disc pl-5 space-y-1 text-sm text-text-secondary my-2">{items.map((t, idx) => <li key={idx} className="leading-relaxed">{renderTokens(parseInline(t), `ul-${idx}`)}</li>)}</ul> } }
    }

    if (/^\s*\d+\.\s+/.test(trimmed)) {
      const items: string[] = []; let j = i
      while (j < totalLines && /^\s*\d+\.\s+/.test(lines[j])) { items.push(lines[j].trim().replace(/^\d+\.\s+/, '')); j++ }
      return { consumed: j - i, block: { kind: 'ordered_list', content: <ol className="list-decimal pl-5 space-y-1 text-sm text-text-secondary my-2">{items.map((t, idx) => <li key={idx} className="leading-relaxed">{renderTokens(parseInline(t), `ol-${idx}`)}</li>)}</ol> } }
    }

    if (trimmed.startsWith('```')) {
      const buf: string[] = []; let j = i + 1
      while (j < totalLines && !lines[j].trim().startsWith('```')) { buf.push(lines[j]); j++ }
      return { consumed: j - i + 1, block: { kind: 'code_block', content: <pre className="overflow-x-auto rounded-field border border-border bg-bg-elevated px-4 py-3 my-2 text-xs font-mono text-text-primary leading-relaxed"><code>{buf.join('\n')}</code></pre> } }
    }

    const buf: string[] = []; let j = i
    while (j < totalLines) {
      const cur = lines[j]
      if (cur.trim() === '') break
      if (cur.trim() === '$$') break
      if (/^#{1,6}\s+/.test(cur)) break
      if (cur.trim().startsWith('>')) break
      if (cur.trim().startsWith('- ')) break
      if (/^\s*\d+\.\s+/.test(cur)) break
      if (cur.trim().startsWith('```')) break
      if (/^---/.test(cur)) break
      buf.push(cur); j++
    }
    return { consumed: j - i, block: buf.length > 0 ? { kind: 'paragraph', content: <p className="whitespace-pre-wrap text-sm leading-relaxed text-text-secondary my-1">{renderTokens(parseInline(buf.join('\n')), 'p')}</p> } : null }
  }

  let i = 0
  let chunk: Block[] = []

  function processNextBatch() {
    const deadline = performance.now() + 16
    while (i < totalLines && performance.now() < deadline) {
      const { consumed, block } = parseLine(i)
      i += consumed
      if (block) chunk.push(block)
      if (chunk.length >= chunkSize) {
        onChunk(chunk, false)
        chunk = []
        break
      }
    }

    if (i < totalLines) {
      requestAnimationFrame(processNextBatch)
    } else {
      if (chunk.length > 0) onChunk(chunk, false)
      onChunk([], true)
    }
  }

  requestAnimationFrame(processNextBatch)
}

// ─── Renderer (sync with memoization) ─────────────────────────────────────────

export function MdRenderer({ md }: { md: string }) {
  const blocks = useMemo(() => parseBlocks(md), [md])
  return (
    <div className="space-y-1">
      {blocks.map((b, idx) => (
        <React.Fragment key={idx}>{b.content}</React.Fragment>
      ))}
    </div>
  )
}

// ─── TOC Sidebar ──────────────────────────────────────────────────────────────

export function TocSidebar({ toc }: { toc: TocEntry[] }) {
  const [activeId, setActiveId] = useState<string>('')
  const observerRef = useRef<IntersectionObserver | null>(null)

  useEffect(() => {
    if (observerRef.current) observerRef.current.disconnect()
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter(e => e.isIntersecting)
        if (visible.length > 0) {
          const topmost = visible.reduce((a, b) =>
            a.boundingClientRect.top < b.boundingClientRect.top ? a : b
          )
          setActiveId(topmost.target.id)
        }
      },
      { rootMargin: '-60px 0px -70% 0px', threshold: 0 }
    )
    observerRef.current = observer

    const timeout = setTimeout(() => {
      toc.forEach(({ id }) => {
        const el = document.getElementById(id)
        if (el) observer.observe(el)
      })
    }, 300)

    return () => { clearTimeout(timeout); observer.disconnect() }
  }, [toc])

  const scrollTo = useCallback((id: string) => {
    const el = document.getElementById(id)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      setActiveId(id)
    }
  }, [])

  if (toc.length === 0) return null

  return (
    <nav className="space-y-0.5">
      {toc.map((entry) => {
        const isActive = activeId === entry.id
        const cls =
          entry.level === 1 ? 'font-semibold text-text-primary' :
          entry.level === 2 ? 'pl-2 text-text-secondary' :
          entry.level === 3 ? 'pl-5 text-text-muted text-xs' :
          'pl-8 text-text-muted text-xs'
        return (
          <button
            key={entry.id}
            onClick={() => scrollTo(entry.id)}
            className={`w-full text-left rounded px-2 py-1 text-xs transition-colors hover:text-text-primary ${cls} ${isActive ? 'text-accent bg-accent/10 font-medium' : 'text-text-secondary'}`}
          >
            {entry.text}
          </button>
        )
      })}
    </nav>
  )
}

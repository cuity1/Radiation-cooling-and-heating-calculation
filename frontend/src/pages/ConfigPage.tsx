import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import Button from '../components/ui/Button'
import { Card, CardDesc, CardHeader, CardTitle } from '../components/ui/Card'
import { getConfig, putConfig, restoreConfig } from '../services/config'
import { Settings, RotateCcw, Save, Code, ListChecks, AlertTriangle } from 'lucide-react'

function TextArea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={
        'min-h-[380px] w-full rounded-field border border-border glass-light p-3 text-xs text-text-primary ' +
        'placeholder:text-text-muted transition-all duration-150 ' +
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ' +
        'hover:border-border-light hover:bg-bg-elevated'
      }
    />
  )
}

function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={
        'w-full rounded-field border border-border glass-light px-3.5 py-2.5 text-sm text-text-primary ' +
        'placeholder:text-text-muted transition-all duration-150 ' +
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/50 ' +
        'hover:border-border-light hover:bg-bg-elevated'
      }
    />
  )
}

type CalcKey =
  | 'wavelength_range'
  | 'wavelength_range_emissivity'
  | 'visiable_range'
  | 'hc_values'
  | 't_a1'
  | 't_filmmin'
  | 't_filmmax'
  | 't_filmmins'
  | 't_filmmaxs'
  | 's_solar'

const CALC_FIELDS: Array<{ key: CalcKey; labelZh: string }> = [
  { key: 'wavelength_range', labelZh: '太阳光波长' },
  { key: 'wavelength_range_emissivity', labelZh: '发射率波长选取（μm），默认8,13 这里会影响计算波段' },
  { key: 'visiable_range', labelZh: '可见光波长' },
  { key: 'hc_values', labelZh: '换热系数' },
  { key: 't_a1', labelZh: '环境温度' },
  { key: 't_filmmin', labelZh: '辐射制冷薄膜温度下限' },
  { key: 't_filmmax', labelZh: '辐射制冷薄膜温度上限' },
  { key: 't_filmmins', labelZh: '辐射制热薄膜温度下限' },
  { key: 't_filmmaxs', labelZh: '辐射制热薄膜温度上限' },
  { key: 's_solar', labelZh: '太阳光强度，太高的话制冷功率会很低' },
]

function setIniValue(ini: string, section: string, key: string, value: string): string {
  const lines = ini.replace(/\r\n/g, '\n').split('\n')
  const targetHeader = `[${section}]`
  let inSection = false
  let sectionFound = false
  let insertAfter = -1

  for (let i = 0; i < lines.length; i += 1) {
    const raw = lines[i]
    const line = raw.trim()

    if (line.startsWith('[') && line.endsWith(']')) {
      if (line === targetHeader) {
        inSection = true
        sectionFound = true
        insertAfter = i
      } else {
        if (inSection) insertAfter = i - 1
        inSection = false
      }
      continue
    }

    if (!inSection) continue

    if (line === '' || line.startsWith('#') || line.startsWith(';')) {
      insertAfter = i
      continue
    }

    const eq = raw.indexOf('=')
    if (eq === -1) {
      insertAfter = i
      continue
    }

    const k = raw.slice(0, eq).trim().toLowerCase()
    if (k === key.toLowerCase()) {
      const prefix = raw.slice(0, eq + 1)
      lines[i] = `${prefix} ${value}`
      return lines.join('\n')
    }

    insertAfter = i
  }

  if (!sectionFound) {
    if (lines.length && lines[lines.length - 1].trim() !== '') lines.push('')
    lines.push(targetHeader)
    lines.push(`${key.toUpperCase()} = ${value}`)
    return lines.join('\n')
  }

  const idx = Math.max(insertAfter + 1, 0)
  lines.splice(idx, 0, `${key.toUpperCase()} = ${value}`)
  return lines.join('\n')
}

function SectionBadge(props: { label: string; active: boolean }) {
  return (
    <span className={`inline-flex items-center rounded-lg border px-2 py-1 text-[11px] font-semibold transition-colors ${
      props.active
        ? 'bg-accent/15 text-accent border-accent/30'
        : 'bg-white/[0.04] text-text-muted border-border'
    }`}>
      {props.label}
    </span>
  )
}

export default function ConfigPage() {
  const { t, i18n } = useTranslation()

  const [tab, setTab] = useState<'form' | 'raw'>('form')
  const q = useQuery({ queryKey: ['config'], queryFn: getConfig })

  const [draft, setDraft] = useState<string>('')
  const [showSaveMsg, setShowSaveMsg] = useState(false)

  const initialContent = q.data?.content
  useMemo(() => {
    if (initialContent != null && draft === '') setDraft(initialContent)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialContent])

  const saveM = useMutation({
    mutationFn: (content: string) => putConfig(content),
    onSuccess: (data) => {
      setDraft(data.content)
      setShowSaveMsg(true)
      setTimeout(() => setShowSaveMsg(false), 3000)
    },
  })

  const restoreM = useMutation({
    mutationFn: () => restoreConfig(),
    onSuccess: (data) => {
      setDraft(data.content)
      q.refetch()
    },
  })

  const parsed = q.data?.parsed || {}
  const calcParsed = (parsed['CALCULATIONS'] || {}) as Record<string, string>

  const calcForm = useMemo(() => {
    const out: Record<string, string> = {}
    for (const f of CALC_FIELDS) out[f.key] = calcParsed[f.key] ?? ''
    return out
  }, [q.data?.parsed])

  const [calcDraft, setCalcDraft] = useState<Record<string, string>>({})

  useMemo(() => {
    if (Object.keys(calcDraft).length === 0 && Object.keys(calcForm).length > 0) setCalcDraft(calcForm)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [calcForm])

  useMemo(() => {
    if (Object.keys(calcForm).length > 0) setCalcDraft(calcForm)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q.data?.parsed])

  const isZh = (i18n.language || 'zh').startsWith('zh')

  return (
    <div className="space-y-5">
      {/* Header */}
      <Card className="animate-fade-slide-up">
        <CardHeader>
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/15 text-accent">
                <Settings size={18} />
              </div>
              <div>
                <CardTitle>{t('pages.config.title')}</CardTitle>
                <CardDesc className="text-xs">{t('pages.config.desc')}</CardDesc>
              </div>
            </div>

            <div className="flex items-center gap-2 text-[11px] text-text-muted">
              {q.isLoading ? (
                <span className="animate-pulse">{t('common.loading')}</span>
              ) : (
                <>
                  <span>{t('pages.config.activePath')}:</span>
                  <span className="font-mono text-text-secondary">
                    {q.data?.user ? `${q.data.user.username} (id=${q.data.user.id})` : '-'}
                  </span>
                </>
              )}
            </div>
          </div>
        </CardHeader>

        {/* Toolbar */}
        <div className="flex flex-wrap items-center gap-2 mt-2">
          <Button
            variant="ghost"
            size="sm"
            icon={<RotateCcw size={12} />}
            className="text-amber-500/80 hover:text-amber-400 hover:bg-amber-500/10 border border-amber-500/20 hover:border-amber-500/40"
            onClick={() => {
              if (window.confirm(t('pages.config.restoreConfirm'))) restoreM.mutate()
            }}
            disabled={restoreM.isPending || q.isLoading}
          >
            {restoreM.isPending ? t('common.loading') : t('pages.config.restore')}
          </Button>

          <div className="h-5 w-px bg-border mx-1" />

          <Button variant={tab === 'form' ? 'primary' : 'secondary'} size="sm" icon={<ListChecks size={12} />} onClick={() => setTab('form')}>
            {t('pages.config.formTab')}
          </Button>
          <Button variant={tab === 'raw' ? 'primary' : 'secondary'} size="sm" icon={<Code size={12} />} onClick={() => setTab('raw')}>
            {t('pages.config.rawTab')}
          </Button>

          <div className="flex-1" />

          <Button variant="ghost" size="sm" icon={<RotateCcw size={11} />} onClick={() => q.refetch()} className="text-xs">
            {t('common.refresh')}
          </Button>
          <Button variant="primary" size="sm" icon={<Save size={12} />} loading={saveM.isPending} disabled={saveM.isPending || q.isLoading} onClick={() => saveM.mutate(draft)}>
            {saveM.isPending ? t('common.loading') : t('pages.config.save')}
          </Button>
        </div>

        {/* Feedback messages */}
        {saveM.isError && (
          <div className="mt-3 rounded-field border border-danger/30 bg-danger/10 p-2.5 text-xs text-text-secondary animate-scale-fade-in">
            {t('pages.config.saveFailed')}
          </div>
        )}
        {showSaveMsg && (
          <div className="mt-3 rounded-field border border-success/30 bg-success/10 p-2.5 text-xs text-text-secondary animate-scale-fade-in">
            {t('pages.config.saveSuccess')}
          </div>
        )}
        {restoreM.isError && (
          <div className="mt-3 rounded-field border border-danger/30 bg-danger/10 p-2.5 text-xs text-text-secondary animate-scale-fade-in">
            {t('pages.config.restoreFailed')}
          </div>
        )}
        {restoreM.isSuccess && (
          <div className="mt-3 rounded-field border border-success/30 bg-success/10 p-2.5 text-xs text-text-secondary animate-scale-fade-in">
            {t('pages.config.restoreSuccess')}
          </div>
        )}
      </Card>

      {/* Raw config tab */}
      {tab === 'raw' ? (
        <Card className="glass-light animate-fade-slide-up">
          <CardHeader>
            <CardTitle>{t('pages.config.rawTitle')}</CardTitle>
            <CardDesc className="text-xs">{t('pages.config.rawDesc')}</CardDesc>
          </CardHeader>
          <TextArea value={draft} onChange={(e) => setDraft(e.target.value)} spellCheck={false} />
        </Card>
      ) : (
        <Card className="glass-light animate-fade-slide-up">
          <CardHeader>
            <div className="flex items-center gap-2">
              <SectionBadge label="[CALCULATIONS]" active />
              <CardTitle className="text-sm">{t('pages.config.formTitle')}</CardTitle>
            </div>
            <CardDesc className="text-xs">{t('pages.config.formDesc')}</CardDesc>
          </CardHeader>

          {q.isLoading ? (
            <div className="text-sm text-text-secondary animate-pulse">{t('common.loading')}</div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {CALC_FIELDS.map((f) => {
                const label = isZh ? f.labelZh : f.key
                const rawVal = (calcDraft[f.key] ?? '').trim()

                let showWarning = false
                if (f.key === 'wavelength_range_emissivity' && rawVal !== '') {
                  const parts = rawVal.split(',').map((p) => parseFloat(p.trim()))
                  if (parts.length === 2 && parts.every((v) => !isNaN(v))) {
                    showWarning = parts.some((v) => v < 7 || v > 14)
                  }
                }

                return (
                  <div key={f.key} className="space-y-1.5">
                    <div className="text-xs font-semibold text-text-secondary px-1">{label}</div>
                    <Input
                      value={calcDraft[f.key] ?? ''}
                      onChange={(e) => {
                        const next = e.target.value
                        setCalcDraft((prev) => ({ ...prev, [f.key]: next }))
                        setDraft((prevIni) => setIniValue(prevIni, 'CALCULATIONS', f.key, next))
                      }}
                      className={showWarning ? 'border-danger/50' : ''}
                    />
                    {showWarning && (
                      <div className="flex items-start gap-1.5 rounded-field border border-danger/30 bg-danger/10 px-2.5 py-1.5 text-[11px] text-danger">
                        <AlertTriangle size={11} className="mt-0.5 shrink-0" />
                        <span>波段选取超过[7,14]的情况下，制冷功率计算请自行上传大气透过率文件（可通过工具箱计算得到），并且不支持原位模拟！</span>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </Card>
      )}

      {/* Notes */}
      <Card className="glass-light animate-fade-slide-up stagger-3">
        <CardHeader>
          <CardTitle className="text-sm">{t('pages.config.notesTitle')}</CardTitle>
          <CardDesc className="text-xs">{t('pages.config.notesDesc')}</CardDesc>
        </CardHeader>
        <div className="text-sm text-text-secondary leading-relaxed">{t('pages.config.notesBody')}</div>
      </Card>
    </div>
  )
}

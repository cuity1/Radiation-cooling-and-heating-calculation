import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import Button from '../components/ui/Button'
import { Card, CardDesc, CardHeader, CardTitle } from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import {
  clearInput,
  getUploadsActive,
  uploadInput,
  useSampleData,
  type UploadResult,
  type UseSampleResponse,
} from '../services/uploads'
import { Upload, FileText, Layers, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react'

function StatusBadge(props: { label: string; ok: boolean }) {
  return (
    <Badge tone={props.ok ? 'success' : 'warning'} showDot>
      {props.label}
    </Badge>
  )
}

function PreviewTable(props: { rows: number[][] }) {
  if (!props.rows.length) return null
  return (
    <div className="overflow-auto rounded-field border border-border mt-2">
      <table className="min-w-full text-xs">
        <thead className="bg-bg-elevated/60 text-text-muted sticky top-0 z-10">
          <tr>
            <th className="px-3 py-2 text-left font-semibold">x</th>
            <th className="px-3 py-2 text-left font-semibold">y</th>
          </tr>
        </thead>
        <tbody>
          {props.rows.map((r, idx) => (
            <tr key={idx} className="border-t border-border/50 last:border-0 hover:bg-white/[0.02] transition-colors">
              <td className="px-3 py-1.5 text-text-secondary font-mono">{r[0]}</td>
              <td className="px-3 py-1.5 text-text-secondary font-mono">{r[1]}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function UploadCard(props: {
  kind: 'reflectance' | 'emissivity' | 'transmittance'
  icon: React.ReactNode
  title: string
  desc: string
  last?: UploadResult | null
  onUploaded: (r: UploadResult) => void
  onCleared: () => void
}) {
  const { t } = useTranslation()
  const [file, setFile] = useState<File | null>(null)

  const m = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('no file')
      return uploadInput(props.kind, file)
    },
    onSuccess: (r) => props.onUploaded(r),
  })

  const clearM = useMutation({
    mutationFn: async () => {
      return clearInput(props.kind)
    },
    onSuccess: () => {
      setFile(null)
      props.onCleared()
    },
  })

  return (
    <Card className="glass-light h-full flex flex-col">
      <CardHeader>
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent/15 text-accent border border-accent/25">
            <div className="flex items-center justify-center">{props.icon}</div>
          </div>
          <div>
            <CardTitle className="text-sm">{props.title}</CardTitle>
            <CardDesc className="text-xs">{props.desc}</CardDesc>
          </div>
        </div>
      </CardHeader>

      <div className="space-y-3 flex-1 overflow-y-auto">
        <input
          type="file"
          accept=".txt,.csv,.xlsx,.xls"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-xs text-text-secondary file:mr-3 file:rounded-field file:border file:border-border file:bg-bg-elevated file:px-3 file:py-2 file:text-xs file:text-text-primary file:font-medium file:transition-all file:duration-150 hover:file:bg-bg-elevated/80 file:cursor-pointer"
        />

        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" size="sm" disabled={(!file && !props.last) || m.isPending || clearM.isPending} onClick={() => clearM.mutate()} className="text-xs">
            {t('pages.uploads.clear')}
          </Button>
          <Button variant="primary" size="sm" disabled={!file || m.isPending} loading={m.isPending} onClick={() => m.mutate()} className="text-xs">
            {m.isPending ? t('pages.uploads.uploading') : t('pages.uploads.uploadAndProcess')}
          </Button>
        </div>

        {m.isError ? (
          <div className="rounded-field border border-danger/30 bg-danger/10 p-2.5 text-xs text-text-secondary">
            {t('pages.uploads.uploadFailed')}
          </div>
        ) : null}

        {props.last ? (
          <div className="glass-light rounded-field border border-border p-3 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-text-muted">{t('pages.uploads.processed')}</span>
              <StatusBadge label={props.last.active_ready ? t('pages.uploads.ready') : t('pages.uploads.notReady')} ok={props.last.active_ready} />
            </div>
            <div className="text-sm text-text-primary font-medium truncate">{props.last.original_name}</div>
            <div className="flex items-center gap-4 text-[11px] text-text-secondary">
              <span>{t('pages.uploads.rows')}: <span className="font-mono">{props.last.rows}</span></span>
            </div>
            {props.last.tips.length ? (
              <div className="flex items-start gap-1.5 text-[11px] text-warning">
                <AlertTriangle size={11} className="mt-0.5 shrink-0" />
                <span>{props.last.tips.join('；')}</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 text-[11px] text-success">
                <CheckCircle2 size={11} />
                <span>{t('pages.uploads.tipsNone')}</span>
              </div>
            )}
            <PreviewTable rows={props.last.preview ?? []} />
          </div>
        ) : null}
      </div>
    </Card>
  )
}

export default function UploadsPage() {
  const { t } = useTranslation()

  const activeQ = useQuery({
    queryKey: ['uploads', 'active'],
    queryFn: getUploadsActive,
    refetchOnWindowFocus: false,
  })

  const [lastReflectance, setLastReflectance] = useState<UploadResult | null>(null)
  const [lastEmissivity, setLastEmissivity] = useState<UploadResult | null>(null)
  const [lastTransmittance, setLastTransmittance] = useState<UploadResult | null>(null)

  const ready = activeQ.data?.ready ?? false

  const activeSummary = useMemo(() => {
    const r = activeQ.data?.reflectance
    const e = activeQ.data?.emissivity
    const tr = activeQ.data?.transmittance
    return {
      rName: r?.original_name ?? t('pages.uploads.none'),
      eName: e?.original_name ?? t('pages.uploads.none'),
      tName: tr?.original_name ?? t('pages.uploads.none'),
      rAt: r?.updated_at ?? '',
      eAt: e?.updated_at ?? '',
      tAt: tr?.updated_at ?? '',
    }
  }, [activeQ.data, t])

  const useSampleM = useMutation({
    mutationFn: useSampleData,
    onSuccess: (res: UseSampleResponse) => {
      setLastReflectance({
        kind: 'reflectance', processed_id: res.reflectance.processed_id,
        processed_path: res.reflectance.processed_path, original_name: res.reflectance.original_name,
        rows: res.reflectance.rows, tips: res.reflectance.tips, preview: res.reflectance.preview, active_ready: res.ready,
      })
      setLastEmissivity({
        kind: 'emissivity', processed_id: res.emissivity.processed_id,
        processed_path: res.emissivity.processed_path, original_name: res.emissivity.original_name,
        rows: res.emissivity.rows, tips: res.emissivity.tips, preview: res.emissivity.preview, active_ready: res.ready,
      })
      if (res.transmittance) {
        setLastTransmittance({
          kind: 'transmittance', processed_id: res.transmittance.processed_id,
          processed_path: res.transmittance.processed_path, original_name: res.transmittance.original_name,
          rows: res.transmittance.rows, tips: res.transmittance.tips, preview: res.transmittance.preview, active_ready: res.ready,
        })
      }
      activeQ.refetch()
    },
  })

  return (
    <div className="space-y-5">
      {/* Header card */}
      <Card className="animate-fade-slide-up">
        <CardHeader>
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent/15 text-accent">
                <Upload size={18} />
              </div>
              <div>
                <CardTitle>{t('pages.uploads.title')}</CardTitle>
                <CardDesc className="text-xs">{t('pages.uploads.desc')}</CardDesc>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <StatusBadge label={ready ? t('pages.uploads.ready') : t('pages.uploads.notReady')} ok={ready} />
              {activeQ.isLoading && <Loader2 size={14} className="text-text-muted animate-spin" />}
              <Button variant="primary" size="sm" loading={useSampleM.isPending} onClick={() => useSampleM.mutate()}>
                {useSampleM.isPending ? t('pages.uploads.processing') : t('pages.uploads.useSample')}
              </Button>
            </div>
          </div>
        </CardHeader>

        {useSampleM.isError && (
          <div className="mt-2 rounded-field border border-danger/30 bg-danger/10 p-2.5 text-xs text-text-secondary animate-scale-fade-in">
            {t('pages.uploads.useSampleFailed')}
          </div>
        )}

        {/* Active materials */}
        <div className="grid gap-3 md:grid-cols-3 mt-3">
          <div className="glass-light rounded-field border border-border p-3 space-y-1">
            <div className="text-[11px] text-text-muted font-semibold uppercase tracking-wider">{t('pages.uploads.activeReflectance')}</div>
            <div className="text-sm text-text-primary truncate font-medium">{activeSummary.rName}</div>
            {activeSummary.rAt && <div className="text-[11px] text-text-muted">{activeSummary.rAt}</div>}
          </div>
          <div className="glass-light rounded-field border border-border p-3 space-y-1">
            <div className="text-[11px] text-text-muted font-semibold uppercase tracking-wider">{t('pages.uploads.activeEmissivity')}</div>
            <div className="text-sm text-text-primary truncate font-medium">{activeSummary.eName}</div>
            {activeSummary.eAt && <div className="text-[11px] text-text-muted">{activeSummary.eAt}</div>}
          </div>
          <div className="glass-light rounded-field border border-border p-3 space-y-1">
            <div className="text-[11px] text-text-muted font-semibold uppercase tracking-wider">{t('pages.uploads.activeTransmittance')}</div>
            <div className="text-sm text-text-primary truncate font-medium">{activeSummary.tName}</div>
            {activeSummary.tAt && <div className="text-[11px] text-text-muted">{activeSummary.tAt}</div>}
          </div>
        </div>
        <div className="text-[11px] text-text-tertiary mt-3">{t('pages.uploads.note')}</div>
      </Card>

      {/* Upload cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 items-stretch">
        <div className="animate-fade-slide-up stagger-1 flex flex-col" style={{ maxHeight: '620px' }}>
          <UploadCard
            kind="reflectance"
            icon={<FileText size={18} />}
            title={t('pages.uploads.reflectanceTitle')}
            desc={t('pages.uploads.reflectanceDesc')}
            last={lastReflectance}
            onUploaded={(r) => { setLastReflectance(r); activeQ.refetch() }}
            onCleared={() => { setLastReflectance(null); activeQ.refetch() }}
          />
        </div>
        <div className="animate-fade-slide-up stagger-2 flex flex-col" style={{ maxHeight: '620px' }}>
          <UploadCard
            kind="emissivity"
            icon={<Layers size={18} />}
            title={t('pages.uploads.emissivityTitle')}
            desc={t('pages.uploads.emissivityDesc')}
            last={lastEmissivity}
            onUploaded={(r) => { setLastEmissivity(r); activeQ.refetch() }}
            onCleared={() => { setLastEmissivity(null); activeQ.refetch() }}
          />
        </div>
        <div className="animate-fade-slide-up stagger-3 flex flex-col" style={{ maxHeight: '620px' }}>
          <UploadCard
            kind="transmittance"
            icon={<Upload size={18} />}
            title={t('pages.uploads.transmittanceTitle')}
            desc={t('pages.uploads.transmittanceDesc')}
            last={lastTransmittance}
            onUploaded={(r) => { setLastTransmittance(r); activeQ.refetch() }}
            onCleared={() => { setLastTransmittance(null); activeQ.refetch() }}
          />
        </div>
      </div>
    </div>
  )
}

import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Cloud, CloudSun, Leaf, Sun, Building2, Waves, AlertTriangle, Search } from 'lucide-react'
import clsx from 'clsx'

export type AtmPresetItem = {
  name: string // filename
  label: string // display label
  category: string
  icon: React.ReactNode
}

function classify(name: string): { category: string; icon: React.ReactNode; label: string } {
  const base = name.replace(/\.dll$/i, '')
  const low = base.toLowerCase()

  if (low.includes('clear') || low.includes('晴') || base === '1') {
    return { category: 'Clear', icon: <Sun size={16} />, label: base }
  }
  if (low.includes('cloud') || low.includes('云') || low.includes('no_cloud') || low.includes('fog') || low.includes('雾')) {
    // 合并为同一类别：云/雾
    return { category: 'CloudFog', icon: <CloudSun size={16} />, label: base }
  }
  if (low.includes('urban') || low.includes('城市') || low.includes('rural') || low.includes('农村')) {
    // 合并为同一类别：城市/农村
    return { category: 'UrbanRural', icon: <Building2 size={16} />, label: base }
  }
  if (low.includes('sea') || low.includes('海')) {
    return { category: 'Sea', icon: <Waves size={16} />, label: base }
  }
  if (low.includes('polluted') || low.includes('污')) {
    return { category: 'Polluted', icon: <AlertTriangle size={16} />, label: base }
  }

  return { category: 'Other', icon: <Cloud size={16} />, label: base }
}

export default function AtmPresetPicker({
  items,
  value,
  onChange,
  className,
}: {
  items: string[]
  value: string
  onChange: (v: string) => void
  className?: string
}) {
  const { t } = useTranslation()
  const [q, setQ] = useState('')

  const normalized = useMemo<AtmPresetItem[]>(() => {
    return (items || []).map((name) => {
      const meta = classify(name)
      return {
        name,
        label: meta.label,
        category: meta.category,
        icon: meta.icon,
      }
    })
  }, [items])

  const filtered = useMemo(() => {
    const qq = q.trim().toLowerCase()
    if (!qq) return normalized
    return normalized.filter((it) => (it.label + ' ' + it.name).toLowerCase().includes(qq))
  }, [normalized, q])

  const groups = useMemo(() => {
    const map = new Map<string, AtmPresetItem[]>()
    for (const it of filtered) {
      const arr = map.get(it.category) ?? []
      arr.push(it)
      map.set(it.category, arr)
    }
    // stable ordering
    const order = ['Clear', 'CloudFog', 'UrbanRural', 'Sea', 'Polluted', 'Other']
    return order
      .filter((k) => map.has(k))
      .map((k) => ({ category: k, items: map.get(k)! }))
  }, [filtered])

  return (
    <div className={clsx('space-y-3', className)}>
      <div className="glass-light flex items-center gap-2 rounded-field border border-border px-3 py-2.5 transition-all duration-150 hover:border-border-light">
        <Search size={14} className="text-text-muted" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={t('presets.search')}
          className="w-full bg-transparent text-sm text-text-primary placeholder:text-text-muted focus:outline-none"
        />
      </div>

      <div className="space-y-3">
        {groups.map((g) => (
          <div key={g.category} className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wider text-text-muted">
              {t(`presets.atmCategories.${g.category}`, g.category)}
            </div>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
              {g.items.map((it) => {
                const active = it.name === value
                return (
                  <button
                    key={it.name}
                    type="button"
                    onClick={() => onChange(it.name)}
                    className={clsx(
                      'flex items-center gap-2 rounded-xl border px-3 py-2.5 text-left transition-all duration-150',
                      active
                        ? 'border-border-accent bg-accent-soft shadow-inner-glow'
                        : 'border-border glass-light hover:bg-bg-elevated hover:border-border-light',
                    )}
                  >
                    <span className={clsx('transition-all duration-150', active ? 'text-accent' : 'text-text-muted')}>{it.icon}</span>
                    <span className={clsx('text-sm font-semibold', active ? 'text-text-primary' : 'text-text-secondary')}>
                      {it.label}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

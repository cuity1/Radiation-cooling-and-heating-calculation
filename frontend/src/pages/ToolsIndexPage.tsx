import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Card, CardDesc, CardHeader, CardTitle } from '../components/ui/Card'
import Button from '../components/ui/Button'
import { Cloud, Sun, Layers, PieChart, Radar, Map, Shirt, ThermometerSun, Thermometer, Wrench } from 'lucide-react'

function AtmosphericTransmittanceIcon({ size = 18 }: { size?: number }) {
  return (
    <div className="flex items-center justify-center w-full h-full">
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ display: 'block' }}>
        <rect x="6" y="3" width="12" height="18" rx="6" fill="none" />
        <path d="M 8 9 Q 10 8, 12 9 Q 14 10, 16 9" strokeWidth="1.5" />
        <path d="M 8 12 Q 10 11, 12 12 Q 14 13, 16 12" strokeWidth="1.5" />
        <path d="M 8 15 Q 10 14, 12 15 Q 14 16, 16 15" strokeWidth="1.5" />
      </svg>
    </div>
  )
}

const TOOL_ICONS: Record<string, React.ReactNode> = {
  Map,
  Thermometer,
  Shirt,
  Cloud,
  Sun,
  Layers,
  PieChart,
  Radar,
  ThermometerSun,
}

function ToolCard(props: { index: number; icon: React.ReactNode; title: string; desc: string; to: string; external?: boolean; cta: string }) {
  const animClass = `animate-fade-slide-up stagger-${Math.min(props.index, 10)}`
  const content = (
    <Card className="group glass-light hover:glass-strong h-full card-lift">
      <CardHeader className="mb-3">
        <div className="flex items-start gap-3.5">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent/15 text-accent border border-accent/25 shadow-[0_0_0_1px_rgba(10,132,255,0.15),0_4px_12px_rgba(10,132,255,0.08)] transition-all duration-300 group-hover:scale-105">
            <div className="flex items-center justify-center w-full h-full">{props.icon}</div>
          </div>
          <div className="min-w-0 flex-1">
            <CardTitle className="group-hover:text-accent transition-colors duration-200">{props.title}</CardTitle>
            <CardDesc>{props.desc}</CardDesc>
          </div>
        </div>
      </CardHeader>
      <Button variant="secondary" className="w-full text-xs" size="sm">
        {props.cta}
      </Button>
    </Card>
  )

  if (props.external) {
    return <a href={props.to} target="_blank" rel="noopener noreferrer" className={`block ${animClass}`}>{content}</a>
  }
  return <Link to={props.to} className={`block ${animClass}`}>{content}</Link>
}

const TOOLS = [
  { icon: <Map size={18} />,                title: t => t('tools.powerMap.title'),               desc: t => t('tools.powerMap.desc'),               to: '/power-map',                   cta: t => t('tools.open') },
  { icon: <Thermometer size={18} />,         title: t => t('tools.materialEnvTempMap.title'),      desc: t => t('tools.materialEnvTempMap.desc'),     to: '/material-env-temp-map',       cta: t => t('tools.open') },
  { icon: <Shirt size={18} />,              title: t => t('tools.radiationCoolingClothing.title'),desc: t => t('tools.radiationCoolingClothing.desc'),to: '/radiation-cooling-clothing', cta: t => t('tools.open') },
  { icon: <Cloud size={18} />,              title: t => t('tools.windCloud.title'),             desc: t => t('tools.windCloud.desc'),             to: '/tools/wind-cloud',           cta: t => t('tools.open') },
  { icon: <Sun size={18} />,                title: t => t('tools.solarEfficiency.title'),       desc: t => t('tools.solarEfficiency.desc'),       to: '/tools/solar-efficiency',     cta: t => t('tools.open') },
  { icon: <Layers size={18} />,             title: t => t('tools.emissivitySolarCloud.title'),   desc: t => t('tools.emissivitySolarCloud.desc'),   to: '/tools/emissivity-solar',     cta: t => t('tools.open') },
  { icon: <PieChart size={18} />,           title: t => t('tools.powerComponents.title'),       desc: t => t('tools.powerComponents.desc'),       to: '/tools/power-components',     cta: t => t('tools.open') },
  { icon: <Radar size={18} />,              title: t => t('tools.angularPower.title'),          desc: t => t('tools.angularPower.desc'),          to: '/tools/angular-power',        cta: t => t('tools.open') },
  { icon: <AtmosphericTransmittanceIcon size={18} />, title: t => t('tools.modtran.title'), desc: t => t('tools.modtran.desc'), to: '/tools/modtran-transmittance', cta: t => t('tools.open') },
  { icon: <ThermometerSun size={18} />,      title: t => t('tools.materialEnvTempCloud.title'),  desc: t => t('tools.materialEnvTempCloud.desc'),  to: '/tools/material-env-temp-cloud', cta: t => t('tools.open') },
  { icon: <Map size={18} />,               title: t => t('tools.mapRedraw.title'),             desc: t => t('tools.mapRedraw.desc'),             to: '/map-redraw',                 cta: t => t('tools.open') },
]

export default function ToolsIndexPage() {
  const { t } = useTranslation()

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass rounded-2xl p-6 md:p-8 shadow-glass animate-fade-slide-up relative overflow-hidden">
        <div className="absolute top-0 right-0 w-48 h-48 rounded-full opacity-[0.04] pointer-events-none" style={{ background: 'radial-gradient(circle, var(--accent) 0%, transparent 70%)' }} />
        <div className="flex items-start justify-between gap-4 relative">
          <div>
            <h1 className="text-xl font-bold text-text-primary tracking-tight">{t('pages.tools.title')}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed" style={{ color: '#FF6B6B' }}>{t('pages.tools.desc')}</p>
          </div>
          <div className="hidden md:flex h-10 w-10 items-center justify-center rounded-xl bg-accent/15 text-accent shrink-0">
            <Wrench size={20} />
          </div>
        </div>
      </div>

      {/* Tools grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {TOOLS.map((tool, i) => (
          <ToolCard
            key={i}
            index={i + 1}
            icon={tool.icon}
            title={tool.title(t)}
            desc={tool.desc(t)}
            to={tool.to}
            cta={tool.cta(t)}
          />
        ))}

        {/* Mie scattering external tool */}
        <div className="animate-fade-slide-up" style={{ animationDelay: `${(TOOLS.length + 1) * 60}ms` }}>
          <Card className="group glass-light hover:glass-strong h-full card-lift">
            <CardHeader className="mb-3">
              <div className="flex items-start gap-3.5">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent/15 text-accent border border-accent/25 shadow-[0_0_0_1px_rgba(10,132,255,0.15),0_4px_12px_rgba(10,132,255,0.08)] transition-all duration-300 group-hover:scale-105">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <circle cx="12" cy="12" r="4" />
                    <line x1="12" y1="2" x2="12" y2="6" />
                    <line x1="12" y1="18" x2="12" y2="22" />
                    <line x1="2" y1="12" x2="6" y2="12" />
                    <line x1="18" y1="12" x2="22" y2="12" />
                  </svg>
                </div>
                <div className="min-w-0 flex-1">
                  <CardTitle className="group-hover:text-accent transition-colors duration-200">{t('tools.mieScattering.title')}</CardTitle>
                  <CardDesc>{t('tools.mieScattering.desc')}</CardDesc>
                </div>
              </div>
            </CardHeader>
            <a href="https://physics.itmo.ru/en/mie#/spectrum" target="_blank" rel="noopener noreferrer">
              <Button variant="secondary" className="w-full text-xs" size="sm">{t('tools.open')}</Button>
            </a>
          </Card>
        </div>
      </div>
    </div>
  )
}

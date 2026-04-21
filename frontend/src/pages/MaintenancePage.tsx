import { useTranslation } from 'react-i18next'
import { Wrench } from 'lucide-react'

export default function MaintenancePage() {
  const { t } = useTranslation()

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center space-y-6">
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-accent-soft text-accent shadow-glow border border-border-accent">
        <Wrench size={40} />
      </div>
      <div>
        <h1 className="text-2xl font-semibold text-text-primary tracking-tight">
          {t('maintenance.title', '网站维护中')}
        </h1>
        <p className="mt-3 text-sm text-text-secondary max-w-md leading-relaxed">
          {t(
            'maintenance.message',
            '非常抱歉，网站正在进行维护，请稍后再试。维护完成后将第一时间恢复服务，感谢您的耐心等待。',
          )}
        </p>
      </div>
    </div>
  )
}

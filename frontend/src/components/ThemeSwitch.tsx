import { Moon, Sun } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'

export default function ThemeSwitch() {
  const { theme, toggleTheme } = useTheme()
  const isDark = theme === 'dark'

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="glass-light flex items-center justify-center rounded-field border border-border p-2 text-text-secondary transition-all duration-200 hover:bg-bg-elevated hover:text-text-primary hover:border-border-light hover:scale-105 active:scale-95"
      aria-label={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
      title={isDark ? 'Switch to light theme' : 'Switch to dark theme'}
    >
      <div className="relative h-4 w-4 overflow-hidden">
        <Sun
          size={16}
          className="absolute inset-0 text-amber-400 transition-all duration-300"
          style={{ opacity: isDark ? 0 : 1, transform: isDark ? 'rotate(90deg) scale(0)' : 'rotate(0) scale(1)' }}
        />
        <Moon
          size={16}
          className="absolute inset-0 text-accent transition-all duration-300"
          style={{ opacity: isDark ? 1 : 0, transform: isDark ? 'rotate(0) scale(1)' : 'rotate(-90deg) scale(0)' }}
        />
      </div>
    </button>
  )
}

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: 'var(--bg-default)',
          panel: 'var(--bg-panel)',
          subtle: 'var(--bg-subtle)',
          elevated: 'var(--bg-elevated)',
        },
        text: {
          primary: 'var(--text-primary)',
          secondary: 'var(--text-secondary)',
          muted: 'var(--text-muted)',
          tertiary: 'var(--text-tertiary)',
          accent: 'var(--text-accent)',
          'accent-hover': 'var(--text-accent-hover)',
          success: 'var(--text-success)',
          'success-muted': 'var(--text-success-muted)',
          warning: 'var(--text-warning)',
          'warning-muted': 'var(--text-warning-muted)',
          danger: 'var(--text-danger)',
          'danger-muted': 'var(--text-danger-muted)',
        },
        accent: {
          DEFAULT: 'var(--accent)',
          soft: 'var(--accent-soft)',
          lighter: 'var(--accent-lighter)',
        },
        success: 'var(--success)',
        warning: 'var(--warning)',
        danger: 'var(--danger)',
        border: {
          DEFAULT: 'var(--border-default)',
          light: 'var(--border-light)',
          accent: 'var(--border-accent)',
        },
      },
      backdropBlur: {
        xs: '2px',
        sm: '4px',
        DEFAULT: '20px', // 默认毛玻璃效果
        md: '24px',
        lg: '32px',
        xl: '40px',
      },
      boxShadow: {
        // 使用CSS变量以支持主题切换
        'glass': 'var(--shadow-glass)',
        'glass-lg': 'var(--shadow-glass-lg)',
        'glow': 'var(--shadow-glow)',
        'glow-lg': 'var(--shadow-glow-lg)',
        'inner-glow': 'var(--shadow-inner-glow)',
      },
      borderRadius: {
        'glass': '16px',
        'button': '12px',
        'field': '12px',
      },
      backgroundColor: {
        'hover-overlay': 'var(--hover-overlay)',
        'warning-soft': 'var(--warning-soft)',
        'success-soft': 'var(--success-soft)',
        'danger-soft': 'var(--danger-soft)',
      },
      borderColor: {
        'warning-soft': 'var(--warning-border)',
        'success-soft': 'var(--success-border)',
        'danger-soft': 'var(--danger-border)',
      },
      textColor: {
        'success-status': 'var(--success-text)',
        'warning-status': 'var(--warning-text)',
        'danger-status': 'var(--danger-text)',
      },
    },
  },
  plugins: [],
}

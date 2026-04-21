import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // 允许从局域网访问
    port: 5173,
    allowedHosts: [
      'radiative.top',
      'www.radiative.top', // 明确添加 www 子域名
      '.radiative.top', // 允许所有子域名
      'www.radiative.us.ci',
      '.radiative.us.ci', // 允许所有子域名
    ],
    strictPort: false,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8007',
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: [
      'radiative.top',
      'www.radiative.top',
      '.radiative.top',
      'www.radiative.us.ci',
      '.radiative.us.ci',
    ],
  },
})

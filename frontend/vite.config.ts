import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/rpa': { target: 'http://localhost:8004', changeOrigin: true },
      '/jobs': { target: 'http://localhost:8004', changeOrigin: true },
      '/records': { target: 'http://localhost:8004', changeOrigin: true },
    },
  },
})

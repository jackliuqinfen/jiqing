import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('@arco-design') || id.includes('@arco-themes')) return 'vendor-arco'
            if (id.includes('vue') || id.includes('pinia')) return 'vendor-vue'
            if (id.includes('sortablejs')) return 'vendor-dnd'
            return 'vendor'
          }
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:3008',
        changeOrigin: true,
      },
    },
  },
})

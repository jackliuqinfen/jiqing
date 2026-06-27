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
            if (id.includes('@visactor/vrender-core')) return 'vendor-vrender-core'
            if (id.includes('@visactor/vrender-kits')) return 'vendor-vrender-kits'
            if (id.includes('@visactor/vrender-components')) return 'vendor-vrender-components'
            if (id.includes('@visactor/vrender-animate')) return 'vendor-vrender-animate'
            if (id.includes('@visactor/vrender')) return 'vendor-vrender'
            if (id.includes('@visactor/vchart-arco-theme') || id.includes('@visactor/vchart-theme-utils')) return 'vendor-vchart-theme'
            if (id.includes('@visactor/vchart')) return 'vendor-vchart'
            if (id.includes('@visactor/vdataset')) return 'vendor-vdataset'
            if (id.includes('@visactor/vscale') || id.includes('@visactor/vutils') || id.includes('@visactor/vlayouts')) return 'vendor-visactor-utils'
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

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@arco-themes/vue-0000/css/arco.css'
import { installArcoAppComponents } from '@/ui/arcoAppComponents'
import { initThemePreference } from '@/ui/theme'
import App from './App.vue'
import router from './router'

const PRELOAD_RECOVERY_KEY = 'jiqing-preload-recovered'

window.addEventListener('vite:preloadError', (event) => {
  event.preventDefault()
  if (window.sessionStorage.getItem(PRELOAD_RECOVERY_KEY) === '1') return
  window.sessionStorage.setItem(PRELOAD_RECOVERY_KEY, '1')
  const url = new URL(window.location.href)
  url.searchParams.set('v', String(Date.now()))
  window.location.replace(url.toString())
})

const app = createApp(App)

// Pinia 状态管理
app.use(createPinia())

// Vue Router
app.use(router)

installArcoAppComponents(app)
initThemePreference()

app.mount('#app')

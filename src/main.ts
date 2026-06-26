import { createApp } from 'vue'
import { createPinia } from 'pinia'
import '@arco-themes/vue-0000/css/arco.css'
import { installTDesignCompat } from '@/ui/tdesignCompat'
import '@/ui/tdesignCompat.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)

// Pinia 状态管理
app.use(createPinia())

// Vue Router
app.use(router)

installTDesignCompat(app)

app.mount('#app')

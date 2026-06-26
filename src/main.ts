import { createApp } from 'vue'
import { createPinia } from 'pinia'
import TDesign from 'tdesign-vue-next'
import 'tdesign-vue-next/es/style/index.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)

// Pinia 状态管理
app.use(createPinia())

// Vue Router
app.use(router)

// TDesign 组件库
app.use(TDesign)

app.mount('#app')

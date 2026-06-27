<template>
  <div class="login-page">
    <canvas ref="animationCanvasRef" class="login-animation" aria-hidden="true" />
    <div class="login-grid" aria-hidden="true" />

    <section class="login-command">
      <div class="brand-block">
        <span class="brand-mark">
          <t-icon name="layers" size="28px" />
        </span>
        <div>
          <h1>江苏集庆·工程管理系统</h1>
          <p>Engineering Management Console</p>
        </div>
      </div>

      <div class="command-copy">
        <span class="system-state"><i /> 稳态指挥台已就绪</span>
        <h2>工程审计、项目协同与经营数据的统一入口</h2>
        <p>登录后进入首页数据看板，查看审计项目吞吐、时限风险、附件留痕和后台主题配置。</p>
      </div>

      <div class="signal-board">
        <article>
          <span>当前模块</span>
          <strong>审计看板</strong>
          <em>已启用</em>
        </article>
        <article>
          <span>主题体系</span>
          <strong>Arco</strong>
          <em>白名单切换</em>
        </article>
        <article>
          <span>图表引擎</span>
          <strong>VChart</strong>
          <em>动画联动</em>
        </article>
      </div>
    </section>

    <section class="login-panel" aria-label="登录">
      <div class="panel-card">
        <div class="form-header">
          <span>内部系统登录</span>
          <h2>欢迎回来</h2>
          <p>请输入已开通的账号和密码。</p>
        </div>

        <div class="auth-tabs" role="tablist">
          <button class="auth-tab active" type="button" role="tab" aria-selected="true">登录</button>
          <t-tooltip content="请联系管理员" placement="top" :show-arrow="true">
            <button
              class="auth-tab auth-tab--disabled"
              type="button"
              role="tab"
              aria-selected="false"
              aria-disabled="true"
              tabindex="-1"
              @click.prevent="onRegisterClick"
            >
              注册
            </button>
          </t-tooltip>
        </div>

        <t-form
          ref="loginFormRef"
          :data="loginForm"
          :rules="loginRules"
          label-align="top"
          class="auth-form"
          @submit="handleLogin"
        >
          <t-form-item label="账号" name="username">
            <t-input
              v-model="loginForm.username"
              placeholder="请输入您的账号"
              clearable
              size="large"
              autocomplete="username"
            >
              <template #prefix-icon>
                <t-icon name="user" />
              </template>
            </t-input>
          </t-form-item>

          <t-form-item label="密码" name="password">
            <t-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              autocomplete="current-password"
            >
              <template #prefix-icon>
                <t-icon name="lock-on" />
              </template>
            </t-input>
          </t-form-item>

          <t-form-item>
            <t-button
              theme="primary"
              type="button"
              block
              size="large"
              :loading="authStore.isAuthLoading"
              @click="handleLogin"
            >
              登录系统
            </t-button>
          </t-form-item>
        </t-form>

        <div class="form-tip">
          <t-icon name="info-circle" size="14px" />
          <span>如无账号，请联系系统管理员开通；生产环境不展示默认账号提示。</span>
        </div>
      </div>

      <p class="login-footer">© 2026 江苏集庆建设 · 工程管理系统</p>
    </section>
  </div>
</template>

<script setup lang="ts">
import $ from 'jquery'
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { MessagePlugin } from '@/ui/message'
import type { FormInstanceFunctions, FormRule } from '@/ui/tdesignCompat'

type Particle = {
  x: number
  y: number
  vx: number
  vy: number
  size: number
  alpha: number
}

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const animationCanvasRef = ref<HTMLCanvasElement | null>(null)
const loginFormRef = ref<FormInstanceFunctions | null>(null)
const loginForm = reactive({
  username: '',
  password: '',
})

const loginRules: Record<string, FormRule[]> = {
  username: [
    { required: true, message: '请输入账号', trigger: 'blur' },
    { min: 2, message: '账号至少 2 个字符', trigger: 'blur' },
    { max: 50, message: '账号不能超过 50 个字符', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_\u4e00-\u9fa5]+$/, message: '账号仅支持字母、数字、下划线和中文', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
  ],
}

let animationFrame = 0
let particles: Particle[] = []
let canvasContext: CanvasRenderingContext2D | null = null

function createParticles(width: number, height: number) {
  const count = width < 760 ? 24 : 48
  particles = Array.from({ length: count }, () => ({
    x: Math.random() * width,
    y: Math.random() * height,
    vx: (Math.random() - 0.5) * 0.24,
    vy: (Math.random() - 0.5) * 0.2,
    size: 1.1 + Math.random() * 1.8,
    alpha: 0.32 + Math.random() * 0.5,
  }))
}

function resizeAnimationCanvas() {
  const canvas = animationCanvasRef.value
  if (!canvas) return
  const ratio = Math.min(window.devicePixelRatio || 1, 2)
  const $canvas = $(canvas)
  const width = Math.max(1, Math.floor($canvas.outerWidth() || window.innerWidth))
  const height = Math.max(1, Math.floor($canvas.outerHeight() || window.innerHeight))
  canvas.width = Math.floor(width * ratio)
  canvas.height = Math.floor(height * ratio)
  canvasContext = canvas.getContext('2d')
  canvasContext?.setTransform(ratio, 0, 0, ratio, 0, 0)
  createParticles(width, height)
}

function drawAnimationFrame() {
  const canvas = animationCanvasRef.value
  if (!canvas || !canvasContext) return

  const width = canvas.width / Math.min(window.devicePixelRatio || 1, 2)
  const height = canvas.height / Math.min(window.devicePixelRatio || 1, 2)
  canvasContext.clearRect(0, 0, width, height)

  particles.forEach((point, index) => {
    point.x += point.vx
    point.y += point.vy
    if (point.x < -20) point.x = width + 20
    if (point.x > width + 20) point.x = -20
    if (point.y < -20) point.y = height + 20
    if (point.y > height + 20) point.y = -20

    canvasContext!.beginPath()
    canvasContext!.arc(point.x, point.y, point.size, 0, Math.PI * 2)
    canvasContext!.fillStyle = `rgba(20, 201, 201, ${point.alpha})`
    canvasContext!.fill()

    for (let nextIndex = index + 1; nextIndex < particles.length; nextIndex += 1) {
      const next = particles[nextIndex]
      const distance = Math.hypot(point.x - next.x, point.y - next.y)
      if (distance > 126) continue
      const opacity = (1 - distance / 126) * 0.18
      canvasContext!.beginPath()
      canvasContext!.moveTo(point.x, point.y)
      canvasContext!.lineTo(next.x, next.y)
      canvasContext!.strokeStyle = `rgba(22, 93, 255, ${opacity})`
      canvasContext!.lineWidth = 1
      canvasContext!.stroke()
    }
  })

  animationFrame = window.requestAnimationFrame(drawAnimationFrame)
}

function startBackgroundAnimation() {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  resizeAnimationCanvas()
  $(window).on('resize.loginAnimation', resizeAnimationCanvas)
  animationFrame = window.requestAnimationFrame(drawAnimationFrame)
}

function stopBackgroundAnimation() {
  if (animationFrame) window.cancelAnimationFrame(animationFrame)
  animationFrame = 0
  $(window).off('resize.loginAnimation')
  particles = []
  canvasContext = null
}

function syncLoginFormFromDom() {
  const usernameInput = document.querySelector<HTMLInputElement>('input[autocomplete="username"]')
  const passwordInput = document.querySelector<HTMLInputElement>('input[autocomplete="current-password"]')
  if (usernameInput) loginForm.username = usernameInput.value
  if (passwordInput) loginForm.password = passwordInput.value
}

async function handleLogin(context?: Event | { validateResult?: boolean }) {
  if (context && 'preventDefault' in context) context.preventDefault()
  if (authStore.isAuthLoading) return

  syncLoginFormFromDom()
  const username = loginForm.username.trim()
  const password = loginForm.password
  if (!username) {
    MessagePlugin.warning('请输入账号')
    return
  }
  if (!password) {
    MessagePlugin.warning('请输入密码')
    return
  }

  const ok = await authStore.login(username, password)
  if (ok) {
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect)
  }
}

function onRegisterClick() {
  MessagePlugin.warning('请联系管理员')
}

onMounted(startBackgroundAnimation)
onBeforeUnmount(stopBackgroundAnimation)
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(420px, .95fr);
  overflow: hidden;
  position: relative;
  color: #fff;
  background:
    radial-gradient(circle at 18% 18%, rgba(20, 201, 201, .2), transparent 32%),
    linear-gradient(135deg, #071326 0%, #0d2448 52%, #102f56 100%);
}

.login-animation,
.login-grid {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.login-animation {
  z-index: 0;
}

.login-grid {
  z-index: 1;
  background-image:
    linear-gradient(rgba(255, 255, 255, .055) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, .045) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: linear-gradient(90deg, #000 0%, #000 58%, transparent 100%);
}

.login-command,
.login-panel {
  position: relative;
  z-index: 2;
}

.login-command {
  min-height: 100vh;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: var(--space-8);
  padding: var(--space-10);
}

.brand-block {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.brand-mark {
  width: 54px;
  height: 54px;
  display: grid;
  place-items: center;
  background: var(--color-brand-500);
  border: 1px solid rgba(255, 255, 255, .18);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, .14);
}

.brand-block h1 {
  margin: 0;
  color: #fff;
  font-size: var(--text-2xl);
  line-height: 1.18;
}

.brand-block p {
  margin: 4px 0 0;
  color: rgba(255, 255, 255, .58);
  font-size: var(--text-xs);
  letter-spacing: 0;
}

.command-copy {
  max-width: 680px;
  display: grid;
  align-content: center;
  gap: var(--space-4);
}

.system-state {
  width: fit-content;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: rgba(255, 255, 255, .72);
  font-size: var(--text-sm);
}

.system-state i {
  width: 9px;
  height: 9px;
  background: var(--color-success);
  box-shadow: 0 0 0 5px rgba(0, 180, 42, .14);
}

.command-copy h2 {
  max-width: 640px;
  margin: 0;
  color: #fff;
  font-size: 42px;
  line-height: 1.16;
  font-weight: 700;
}

.command-copy p {
  max-width: 620px;
  margin: 0;
  color: rgba(255, 255, 255, .66);
  font-size: var(--text-md);
}

.signal-board {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
  max-width: 680px;
}

.signal-board article {
  min-height: 104px;
  display: grid;
  align-content: center;
  gap: 4px;
  padding: var(--space-4);
  background: rgba(255, 255, 255, .07);
  border: 1px solid rgba(255, 255, 255, .13);
}

.signal-board span,
.signal-board em {
  color: rgba(255, 255, 255, .55);
  font-size: var(--text-xs);
  font-style: normal;
}

.signal-board strong {
  color: #fff;
  font-size: var(--text-xl);
}

.login-panel {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-8);
  background: rgba(245, 248, 252, .96);
  color: var(--text-primary);
  border-left: 1px solid rgba(255, 255, 255, .16);
}

.panel-card {
  width: 100%;
  max-width: 440px;
  padding: var(--space-8);
  background: var(--bg-surface);
  border: 1px solid var(--border-color-strong);
  box-shadow: 0 18px 48px rgba(15, 31, 61, .12);
}

.form-header {
  margin-bottom: var(--space-6);
}

.form-header span {
  display: block;
  margin-bottom: var(--space-2);
  color: var(--color-brand-500);
  font-size: var(--text-xs);
  font-weight: 600;
}

.form-header h2 {
  margin: 0 0 var(--space-1);
  color: var(--text-primary);
  font-size: var(--text-3xl);
  line-height: 1.2;
}

.form-header p {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.auth-tabs {
  display: flex;
  gap: 0;
  padding: 3px;
  margin-bottom: var(--space-6);
  background: var(--color-gray-50);
  border: 1px solid var(--border-color);
}

.auth-tab {
  flex: 1;
  height: 34px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font: inherit;
  font-size: var(--text-sm);
  font-weight: 500;
  transition: all var(--duration-fast) var(--ease-out);
}

.auth-tab:hover:not(.auth-tab--disabled) {
  color: var(--text-primary);
}

.auth-tab.active {
  background: var(--bg-surface);
  color: var(--color-brand-500);
  border: 1px solid var(--border-color);
}

.auth-tab--disabled,
.auth-tab--disabled:hover {
  color: var(--color-gray-300);
  cursor: not-allowed;
  opacity: .62;
  user-select: none;
}

.auth-form :deep(.t-form__label) {
  padding-bottom: var(--space-1);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
}

.form-tip {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  margin-top: var(--space-5);
  padding: var(--space-3);
  color: var(--text-secondary);
  background: var(--color-gray-20);
  border: 1px solid var(--border-color);
  font-size: var(--text-xs);
  line-height: 1.5;
}

.form-tip :deep(.t-icon) {
  flex-shrink: 0;
  margin-top: 1px;
  color: var(--text-tertiary);
}

.login-footer {
  margin-top: var(--space-6);
  color: var(--text-tertiary);
  font-size: var(--text-xs);
}

@media (max-width: 1080px) {
  .login-page {
    grid-template-columns: 1fr;
  }

  .login-command {
    min-height: auto;
    grid-template-rows: auto auto;
    padding: var(--space-6);
  }

  .command-copy {
    align-content: start;
  }

  .command-copy h2 {
    font-size: var(--text-4xl);
  }

  .signal-board {
    display: none;
  }

  .login-panel {
    min-height: auto;
    padding: var(--space-5);
    background: var(--bg-page);
    border-left: 0;
  }
}

@media (max-width: 640px) {
  .login-page {
    min-height: 100vh;
  }

  .login-command {
    padding: var(--space-5);
    gap: var(--space-5);
  }

  .brand-block {
    align-items: flex-start;
  }

  .brand-mark {
    width: 44px;
    height: 44px;
  }

  .brand-block h1 {
    font-size: var(--text-xl);
  }

  .command-copy h2 {
    font-size: var(--text-3xl);
  }

  .command-copy p {
    font-size: var(--text-sm);
  }

  .login-panel {
    padding: 0 var(--space-4) var(--space-5);
  }

  .panel-card {
    padding: var(--space-5);
  }
}
</style>

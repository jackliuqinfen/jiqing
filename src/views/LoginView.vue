<template>
  <div class="login-page">
    <router-link class="login-brand" to="/">
      <span class="brand-logo">
        <img :src="brandLogo" alt="江苏集庆建设" />
      </span>
    </router-link>
    <canvas ref="particleCanvasRef" class="login-particles" aria-hidden="true" />

    <main class="login-main">
      <section class="login-intro" aria-label="系统概览">
        <div class="intro-kicker">
          <i />
          <span>工程审计与项目协同平台</span>
        </div>
        <h1>统一管理项目进度、审计流转和经营数据</h1>
        <p>面向工程咨询、招投标和项目审计场景，登录后可进入首页看板、审计看板和后台配置。</p>

        <div class="intro-board">
          <article>
            <span>常用入口</span>
            <strong>审计看板</strong>
            <em>可进入</em>
          </article>
          <article>
            <span>项目资料</span>
            <strong>集中归集</strong>
            <em>按项目查看</em>
          </article>
          <article>
            <span>界面风格</span>
            <strong>品牌配色</strong>
            <em>可调整</em>
          </article>
        </div>
      </section>

      <section class="login-panel" aria-label="账号登录">
        <div class="panel-card">
          <div class="panel-head">
            <div>
              <p>账号登录</p>
              <h2>欢迎回来</h2>
            </div>
            <t-tag variant="light" theme="primary">单位内部使用</t-tag>
          </div>

          <div class="auth-tabs" role="tablist" aria-label="登录注册切换">
            <button
              class="auth-tab active"
              type="button"
              role="tab"
              aria-selected="true"
            >
              登录
            </button>
            <t-tooltip content="注册入口由管理员统一开通" placement="top" :show-arrow="true">
              <button
                class="auth-tab auth-tab--disabled"
                type="button"
                role="tab"
                aria-selected="false"
                aria-disabled="true"
                tabindex="-1"
                @click.prevent="showRegisterHint"
              >
                注册
              </button>
            </t-tooltip>
          </div>

          <t-alert v-if="loginErrorMessage" theme="danger" class="auth-alert">
            {{ loginErrorMessage }}
          </t-alert>

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
                :type="passwordVisible ? 'text' : 'password'"
                placeholder="请输入密码"
                size="large"
                autocomplete="current-password"
              >
                <template #prefix-icon>
                  <t-icon name="lock-on" />
                </template>
                <template #suffix-icon>
                  <button
                    class="password-toggle"
                    type="button"
                    :aria-label="passwordVisible ? '隐藏密码' : '显示密码'"
                    @click="togglePasswordVisible"
                    @mousedown.prevent
                  >
                    <t-icon :name="passwordVisible ? 'eye-invisible' : 'eye'" />
                  </button>
                </template>
              </t-input>
            </t-form-item>

            <div class="form-meta">
              <span>如无账号，请联系系统管理员开通。</span>
            </div>

            <t-button
              theme="primary"
              type="submit"
              block
              size="large"
              :loading="authStore.isAuthLoading"
            >
              登录系统
            </t-button>
          </t-form>

          <div class="form-tip">
            <t-icon name="info-circle" size="14px" />
            <span>忘记账号或无法登录时，请联系系统管理员协助处理。</span>
          </div>
        </div>
        <p class="login-footer">© 2026 江苏集庆建设 · 工程管理系统</p>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { MessagePlugin } from '@/ui/message'
import type { FormInstanceFunctions, FormRule } from '@/ui/tdesignCompat'
import brandLogo from '@/assets/aoqiang-construction-logo.svg'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const loginFormRef = ref<FormInstanceFunctions | null>(null)
const particleCanvasRef = ref<HTMLCanvasElement | null>(null)
const passwordVisible = ref(false)
const loginForm = reactive({
  username: '',
  password: '',
})

type Particle = {
  x: number
  y: number
  vx: number
  vy: number
  radius: number
  baseAlpha: number
}

let particleContext: CanvasRenderingContext2D | null = null
let particleFrame = 0
let particles: Particle[] = []
const pointer = { x: -9999, y: -9999, active: false }

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

const loginErrorMessage = computed(() => {
  const raw = authStore.error?.trim()
  if (!raw) return ''
  const normalized = raw.toLowerCase()
  if (raw.includes('账号') && raw.includes('密码')) return '账号或密码不正确，请重新输入后再试。'
  if (raw.includes('锁定') || normalized.includes('locked')) return '账号当前已锁定，请联系管理员处理后再登录。'
  if (raw.includes('网络') || normalized.includes('timeout') || normalized.includes('fetch')) return '当前网络或服务暂时不可用，请稍后重试。'
  return '登录失败，请检查账号状态后重试，必要时联系管理员。'
})

const registerHint = computed(() => {
  return authStore.registrationOpen
    ? '请按单位要求提交开通申请。'
    : '注册入口暂未开放，请联系管理员开通账号。'
})

watch(
  () => [loginForm.username, loginForm.password],
  () => {
    if (authStore.error) authStore.clearError()
  }
)

function showRegisterHint() {
  MessagePlugin.warning(registerHint.value)
}

function togglePasswordVisible() {
  passwordVisible.value = !passwordVisible.value
}

function getBrandRgb() {
  const raw = '#168CFF'
  const hex = raw.match(/^#?([0-9a-fA-F]{6})$/)?.[1]
  if (hex) {
    return {
      r: Number.parseInt(hex.slice(0, 2), 16),
      g: Number.parseInt(hex.slice(2, 4), 16),
      b: Number.parseInt(hex.slice(4, 6), 16),
    }
  }
  const rgb = raw.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i)
  return rgb
    ? { r: Number(rgb[1]), g: Number(rgb[2]), b: Number(rgb[3]) }
    : { r: 71, g: 135, b: 240 }
}

function getParticleCount(width: number) {
  if (width < 640) return 18
  if (width < 1024) return 34
  return 58
}

function createParticles(width: number, height: number) {
  const count = getParticleCount(width)
  particles = Array.from({ length: count }, () => ({
    x: Math.random() * width,
    y: Math.random() * height,
    vx: (Math.random() - 0.5) * 0.18,
    vy: (Math.random() - 0.5) * 0.16,
    radius: 1.4 + Math.random() * 1.7,
    baseAlpha: 0.18 + Math.random() * 0.18,
  }))
}

function resizeParticleCanvas() {
  const canvas = particleCanvasRef.value
  if (!canvas) return
  const ratio = Math.min(window.devicePixelRatio || 1, 2)
  const width = window.innerWidth
  const height = window.innerHeight
  canvas.width = Math.round(width * ratio)
  canvas.height = Math.round(height * ratio)
  canvas.style.width = `${width}px`
  canvas.style.height = `${height}px`
  particleContext = canvas.getContext('2d')
  particleContext?.setTransform(ratio, 0, 0, ratio, 0, 0)
  createParticles(width, height)
}

function drawParticles() {
  const canvas = particleCanvasRef.value
  const ctx = particleContext
  if (!canvas || !ctx) return

  const ratio = Math.min(window.devicePixelRatio || 1, 2)
  const width = canvas.width / ratio
  const height = canvas.height / ratio
  const brand = getBrandRgb()
  ctx.clearRect(0, 0, width, height)

  particles.forEach((particle) => {
    particle.x += particle.vx
    particle.y += particle.vy

    if (particle.x < -12) particle.x = width + 12
    if (particle.x > width + 12) particle.x = -12
    if (particle.y < -12) particle.y = height + 12
    if (particle.y > height + 12) particle.y = -12
  })

  const linkDistance = width < 640 ? 92 : 126
  particles.forEach((particle, index) => {
    for (let nextIndex = index + 1; nextIndex < particles.length; nextIndex += 1) {
      const next = particles[nextIndex]
      const distance = Math.hypot(particle.x - next.x, particle.y - next.y)
      if (distance > linkDistance) continue

      const pointerBoost = pointer.active
        ? Math.max(0, 1 - Math.min(
          Math.hypot(pointer.x - particle.x, pointer.y - particle.y),
          Math.hypot(pointer.x - next.x, pointer.y - next.y)
        ) / 160)
        : 0
      const alpha = (1 - distance / linkDistance) * (0.1 + pointerBoost * 0.22)
      ctx.beginPath()
      ctx.moveTo(particle.x, particle.y)
      ctx.lineTo(next.x, next.y)
      ctx.strokeStyle = `rgba(${brand.r}, ${brand.g}, ${brand.b}, ${alpha})`
      ctx.lineWidth = 1
      ctx.stroke()
    }
  })

  particles.forEach((particle) => {
    const distanceToPointer = pointer.active ? Math.hypot(pointer.x - particle.x, pointer.y - particle.y) : 9999
    const boost = Math.max(0, 1 - distanceToPointer / 170)
    ctx.beginPath()
    ctx.arc(particle.x, particle.y, particle.radius + boost * 1.6, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(${brand.r}, ${brand.g}, ${brand.b}, ${particle.baseAlpha + boost * 0.38})`
    ctx.fill()
  })

  particleFrame = window.requestAnimationFrame(drawParticles)
}

function handlePointerMove(event: MouseEvent) {
  pointer.x = event.clientX
  pointer.y = event.clientY
  pointer.active = true
}

function handlePointerLeave() {
  pointer.active = false
  pointer.x = -9999
  pointer.y = -9999
}

function setupParticles() {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  resizeParticleCanvas()
  window.addEventListener('resize', resizeParticleCanvas)
  window.addEventListener('mousemove', handlePointerMove)
  window.addEventListener('mouseleave', handlePointerLeave)
  particleFrame = window.requestAnimationFrame(drawParticles)
}

function teardownParticles() {
  if (particleFrame) window.cancelAnimationFrame(particleFrame)
  particleFrame = 0
  particles = []
  particleContext = null
  window.removeEventListener('resize', resizeParticleCanvas)
  window.removeEventListener('mousemove', handlePointerMove)
  window.removeEventListener('mouseleave', handlePointerLeave)
}

async function handleLogin(context?: Event | { validateResult?: boolean }) {
  if (context && 'preventDefault' in context) context.preventDefault()
  if (authStore.isAuthLoading) return

  const valid = await loginFormRef.value?.validate()
  if (valid !== true) return

  const ok = await authStore.login(loginForm.username.trim(), loginForm.password)
  if (ok) {
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect)
  }
}

onMounted(() => {
  if (authStore.error) authStore.clearError()
  setupParticles()
})

onBeforeUnmount(() => {
  teardownParticles()
})
</script>

<style scoped>
.login-page {
  position: relative;
  overflow: hidden;
  min-height: 100vh;
  display: grid;
  --color-brand-50: #EAF4FF;
  --color-brand-100: #D8EBFF;
  --color-brand-500: #0E42D2;
  --color-brand-600: #092B8A;
  --color-brand-ink: #0E42D2;
  --color-primary-6: #168CFF;
  --color-primary-7: #0E42D2;
  --text-on-brand: #FFFFFF;
  background: #f7f9fb url('@/assets/login-page-bg-grey.jpg') center / cover no-repeat;
  color: var(--text-primary);
}

.login-brand {
  position: absolute;
  top: clamp(18px, 4vh, 40px);
  left: clamp(24px, 4vw, 56px);
  z-index: 2;
  display: grid;
  align-items: start;
  gap: var(--space-2);
  color: var(--text-primary);
  text-decoration: none;
}

.login-particles {
  position: fixed;
  inset: 0;
  z-index: 0;
  width: 100vw;
  height: 100vh;
  pointer-events: none;
}

.brand-logo {
  width: 200px;
  height: 150px;
  display: grid;
  align-items: center;
  justify-items: start;
}

.brand-logo img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.login-main {
  position: relative;
  z-index: 1;
  width: min(1180px, calc(100% - 48px));
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 430px;
  gap: clamp(36px, 6vw, 86px);
  align-items: center;
  justify-self: center;
  padding: clamp(32px, 5vw, 64px) 0;
}

.login-intro {
  min-width: 0;
  display: grid;
  gap: var(--space-5);
}

.intro-kicker {
  width: fit-content;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--color-brand-ink);
  font-size: var(--text-sm);
  font-weight: 600;
}

.intro-kicker i {
  width: 8px;
  height: 8px;
  background: var(--color-success);
  box-shadow: 0 0 0 5px rgba(0, 180, 42, .12);
}

.login-intro h1 {
  max-width: 720px;
  margin: 0;
  color: var(--text-primary);
  font-size: 42px;
  line-height: 1.18;
  font-weight: 700;
  letter-spacing: 0;
}

.login-intro p {
  max-width: 620px;
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-md);
  line-height: 1.8;
}

.intro-board {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
  max-width: 680px;
  margin-top: var(--space-3);
}

.intro-board article {
  min-height: 112px;
  display: grid;
  align-content: center;
  gap: 4px;
  padding: var(--space-4);
  background: rgba(255, 255, 255, .78);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: 0 12px 36px rgba(18, 38, 74, .08);
}

.intro-board span,
.intro-board em {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
}

.intro-board strong {
  color: var(--text-primary);
  font-size: var(--text-xl);
}

.login-panel {
  min-width: 0;
  display: grid;
  gap: var(--space-5);
  justify-items: center;
}

.panel-card {
  width: 100%;
  padding: var(--space-8);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: 0 22px 60px rgba(18, 38, 74, .14);
}

.panel-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

.panel-head p {
  margin: 0 0 4px;
  color: var(--color-brand-ink);
  font-size: var(--text-xs);
  font-weight: 600;
}

.panel-head h2 {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--text-3xl);
  line-height: 1.2;
}

.auth-tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  padding: 3px;
  margin-bottom: var(--space-6);
  background: var(--color-gray-50);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

.auth-tab {
  min-height: 38px;
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font: inherit;
  font-size: var(--text-sm);
  font-weight: 500;
}

.auth-tab.active {
  background: var(--bg-surface);
  color: var(--color-brand-ink);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
}

.auth-tab--disabled {
  color: var(--color-gray-300);
  cursor: not-allowed;
  opacity: .72;
}

.auth-alert {
  margin-bottom: var(--space-4);
}

.auth-form :deep(.t-form__label) {
  padding-bottom: var(--space-1);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
}

.form-meta {
  display: flex;
  justify-content: flex-end;
  margin: calc(var(--space-2) * -1) 0 var(--space-5);
  color: var(--text-tertiary);
  font-size: var(--text-xs);
}

.password-toggle {
  width: 28px;
  height: 28px;
  display: inline-grid;
  place-items: center;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
}

.password-toggle:hover {
  color: var(--color-brand-ink);
  background: var(--color-brand-50);
}

.password-toggle:focus-visible {
  outline: 2px solid var(--color-brand-500);
  outline-offset: 2px;
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
  border-radius: var(--radius-md);
  font-size: var(--text-xs);
  line-height: 1.6;
}

.form-tip :deep(.t-icon) {
  flex-shrink: 0;
  margin-top: 1px;
  color: var(--text-tertiary);
}

.login-footer {
  margin: 0;
  color: var(--text-tertiary);
  font-size: var(--text-xs);
}

@media (max-width: 980px) {
  .login-main {
    grid-template-columns: 1fr;
    gap: var(--space-8);
  }

  .login-intro h1 {
    font-size: var(--text-4xl);
  }

  .intro-board {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .login-brand {
    top: var(--space-4);
    left: var(--space-4);
  }

  .login-main {
    width: calc(100% - 32px);
    min-height: auto;
    padding: var(--space-6) 0;
  }

  .brand-logo {
    width: 170px;
    height: 128px;
  }

  .login-intro h1 {
    font-size: var(--text-3xl);
  }

  .login-intro p {
    font-size: var(--text-sm);
  }

  .panel-card {
    padding: var(--space-5);
  }
}
</style>

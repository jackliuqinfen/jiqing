<template>
  <div class="login-page">
    <div class="login-bg" aria-hidden="true" />

    <main class="login-main">
      <section class="login-hero" aria-label="系统品牌">
        <router-link class="login-brand" to="/">
          <span class="brand-logo">
            <img :src="brandLogo" alt="江苏集庆建设" />
          </span>
        </router-link>

        <div class="hero-copy">
          <span>JIQING CONSTRUCTION</span>
          <h1>工程管理系统</h1>
          <p>项目协同、资料归档、审计流转。</p>
        </div>

        <div class="hero-meta" aria-label="系统能力">
          <span>项目</span>
          <span>资料</span>
          <span>审计</span>
        </div>
      </section>

      <section class="login-panel" aria-label="账号登录">
        <div class="panel-card">
          <div class="panel-head">
            <div>
              <p>{{ activeMode === 'login' ? 'SIGN IN' : 'REQUEST ACCESS' }}</p>
              <h2>{{ activeMode === 'login' ? '欢迎回来' : '账号开通' }}</h2>
            </div>
          </div>

          <div class="auth-tabs" role="tablist" aria-label="登录注册切换">
            <button
              class="auth-tab"
              :class="{ active: activeMode === 'login' }"
              type="button"
              role="tab"
              :aria-selected="activeMode === 'login'"
              @click="activeMode = 'login'"
            >
              登录
            </button>
            <button
              class="auth-tab"
              :class="{ active: activeMode === 'register' }"
              type="button"
              role="tab"
              :aria-selected="activeMode === 'register'"
              @click="activeMode = 'register'"
            >
              注册
            </button>
          </div>

          <AAlert v-if="loginErrorMessage" theme="danger" class="auth-alert">
            {{ loginErrorMessage }}
          </AAlert>

          <AForm
            v-if="activeMode === 'login'"
            ref="loginFormRef"
            :model="loginForm"
            :rules="loginRules"
            layout="vertical"
            class="auth-form"
            @submit="() => handleLogin()"
          >
            <AFormItem label="账号" name="username">
              <AInput
                v-model="loginForm.username"
                placeholder="输入账号"
                clearable
                size="large"
                autocomplete="username"
              >
                <template #prefix-icon>
                  <AIcon name="user" />
                </template>
              </AInput>
            </AFormItem>

            <AFormItem label="密码" name="password">
              <AInput
                v-model="loginForm.password"
                :type="passwordVisible ? 'text' : 'password'"
                placeholder="输入密码"
                size="large"
                autocomplete="current-password"
              >
                <template #prefix-icon>
                  <AIcon name="lock-on" />
                </template>
                <template #suffix-icon>
                  <button
                    class="password-toggle"
                    type="button"
                    :aria-label="passwordVisible ? '隐藏密码' : '显示密码'"
                    @click="togglePasswordVisible"
                    @mousedown.prevent
                  >
                    <AIcon :name="passwordVisible ? 'eye-invisible' : 'eye'" />
                  </button>
                </template>
              </AInput>
            </AFormItem>

            <div class="form-meta">
              <span>内部账号登录</span>
              <button type="button" @click="showRegisterHint">无法登录？</button>
            </div>

            <AButton
              theme="primary"
              html-type="submit"
              block
              size="large"
              :loading="authStore.isAuthLoading"
            >
              登录系统
            </AButton>
          </AForm>

          <div v-else class="register-state">
            <span class="register-icon">
              <AIcon name="user-add" />
            </span>
            <h3>由管理员开通账号</h3>
            <p>请联系系统管理员完成身份确认和权限分配。</p>
            <AButton size="large" block @click="showRegisterHint">我知道了</AButton>
          </div>
        </div>

        <p class="login-footer">江苏集庆建设 · 工程管理系统</p>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { MessagePlugin } from '@/ui/message'
import type { AppFormInstance, AppValidationRule } from '@/ui/arcoAppComponents'
import brandLogo from '@/assets/aoqiang-construction-logo.svg'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

const loginFormRef = ref<AppFormInstance | null>(null)
const passwordVisible = ref(false)
const activeMode = ref<'login' | 'register'>('login')
const loginForm = reactive({
  username: '',
  password: '',
})

const loginRules: Record<string, AppValidationRule[]> = {
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
  if (raw.includes('账号') && raw.includes('密码')) return '账号或密码不正确，请重新输入。'
  if (raw.includes('锁定') || normalized.includes('locked')) return '账号已锁定，请联系管理员。'
  if (raw.includes('网络') || normalized.includes('timeout') || normalized.includes('fetch')) return '服务暂时不可用，请稍后重试。'
  return '登录失败，请检查账号状态。'
})

const registerHint = computed(() => {
  return authStore.registrationOpen
    ? '请联系管理员完成账号开通。'
    : '注册入口暂未开放，请联系管理员开通账号。'
})

watch(
  () => [loginForm.username, loginForm.password],
  () => {
    if (authStore.error) authStore.clearError()
  }
)

function showRegisterHint() {
  MessagePlugin.info(registerHint.value)
}

function togglePasswordVisible() {
  passwordVisible.value = !passwordVisible.value
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
})
</script>

<style scoped>
.login-page {
  position: relative;
  min-height: 100vh;
  overflow: hidden;
  color: #102040;
  background:
    linear-gradient(135deg, rgba(249, 252, 255, 0.96) 0%, rgba(238, 247, 255, 0.92) 44%, rgba(248, 251, 255, 0.98) 100%),
    url('@/assets/login-page-bg-grey.jpg') center / cover no-repeat;
}

.login-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    repeating-linear-gradient(118deg, rgba(22, 93, 255, 0.045) 0 1px, transparent 1px 16px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.82), rgba(255, 255, 255, 0.24));
  mask-image: linear-gradient(90deg, #000 0%, rgba(0, 0, 0, 0.82) 58%, rgba(0, 0, 0, 0.45) 100%);
}

.login-main {
  position: relative;
  z-index: 1;
  width: min(1080px, calc(100% - 48px));
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 420px);
  gap: clamp(40px, 8vw, 112px);
  align-items: center;
  justify-self: center;
  margin: 0 auto;
  padding: clamp(32px, 6vw, 72px) 0;
}

.login-hero {
  min-width: 0;
  display: grid;
  gap: clamp(34px, 6vh, 72px);
  align-content: center;
}

.login-brand {
  width: fit-content;
  color: inherit;
  text-decoration: none;
}

.brand-logo {
  width: 232px;
  height: 132px;
  display: grid;
  align-items: center;
  justify-items: start;
  margin-left: -18px;
}

.brand-logo img {
  display: block;
  width: 112%;
  height: 112%;
  object-fit: contain;
  object-position: left center;
  filter: saturate(1.18) contrast(1.08) brightness(0.95);
}

.hero-copy {
  display: grid;
  gap: 14px;
}

.hero-copy span {
  color: #165dff;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .16em;
}

.hero-copy h1 {
  max-width: 520px;
  margin: 0;
  color: #102040;
  font-size: clamp(42px, 6vw, 72px);
  line-height: 1.02;
  font-weight: 800;
  letter-spacing: 0;
}

.hero-copy p {
  margin: 0;
  color: #5f6f8f;
  font-size: 17px;
  line-height: 1.7;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.hero-meta span {
  min-width: 64px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #24446f;
  background: rgba(255, 255, 255, 0.54);
  border: 1px solid rgba(128, 158, 210, 0.24);
  border-radius: 999px;
  box-shadow: 0 8px 20px rgba(55, 92, 155, 0.06);
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
  font-size: 13px;
  font-weight: 700;
}

.login-panel {
  min-width: 0;
  width: 100%;
  display: grid;
  gap: 18px;
  justify-items: center;
}

.panel-card {
  width: 100%;
  padding: 34px;
  border: 1px solid rgba(255, 255, 255, 0.78);
  border-radius: 18px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(255, 255, 255, 0.62)),
    rgba(255, 255, 255, 0.72);
  box-shadow: 0 28px 70px rgba(36, 75, 136, 0.16);
  backdrop-filter: blur(24px) saturate(150%);
  -webkit-backdrop-filter: blur(24px) saturate(150%);
}

.panel-head {
  margin-bottom: 24px;
}

.panel-head p {
  margin: 0 0 8px;
  color: #165dff;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: .14em;
}

.panel-head h2 {
  margin: 0;
  color: #102040;
  font-size: 30px;
  line-height: 1.2;
  font-weight: 800;
  letter-spacing: 0;
}

.auth-tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px;
  padding: 4px;
  margin-bottom: 24px;
  background: rgba(235, 243, 255, 0.74);
  border: 1px solid rgba(128, 158, 210, 0.22);
  border-radius: 12px;
}

.auth-tab {
  min-height: 40px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: #66789a;
  cursor: pointer;
  font: inherit;
  font-size: 14px;
  font-weight: 700;
}

.auth-tab.active {
  color: #165dff;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 8px 18px rgba(54, 95, 160, 0.1);
}

.auth-alert {
  margin-bottom: 18px;
}

.auth-form :deep(.arco-form-item-label-col) {
  padding-bottom: 7px;
}

.auth-form :deep(.arco-form-item-label) {
  color: #32496f;
  font-size: 13px;
  font-weight: 700;
}

.auth-form :deep(.arco-input-wrapper) {
  min-height: 46px;
  background: rgba(255, 255, 255, 0.78) !important;
}

.form-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: -2px 0 22px;
  color: #7c8ba6;
  font-size: 12px;
}

.form-meta button {
  border: 0;
  padding: 0;
  color: #165dff;
  background: transparent;
  cursor: pointer;
  font: inherit;
  font-weight: 700;
}

.password-toggle {
  width: 28px;
  height: 28px;
  display: inline-grid;
  place-items: center;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: #7c8ba6;
  cursor: pointer;
}

.password-toggle:hover {
  color: #165dff;
  background: rgba(22, 93, 255, 0.08);
}

.password-toggle:focus-visible,
.auth-tab:focus-visible,
.form-meta button:focus-visible {
  outline: 2px solid rgba(22, 93, 255, 0.6);
  outline-offset: 2px;
}

.register-state {
  min-height: 236px;
  display: grid;
  align-content: center;
  justify-items: center;
  gap: 14px;
  text-align: center;
}

.register-icon {
  width: 54px;
  height: 54px;
  display: grid;
  place-items: center;
  color: #165dff;
  background: rgba(22, 93, 255, 0.1);
  border: 1px solid rgba(22, 93, 255, 0.14);
  border-radius: 16px;
}

.register-state h3 {
  margin: 4px 0 0;
  color: #102040;
  font-size: 18px;
}

.register-state p {
  max-width: 260px;
  margin: 0 0 8px;
  color: #6b7b98;
  line-height: 1.7;
}

.login-footer {
  width: 100%;
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: -4px 0 0;
  padding: 0 16px;
  color: #7c8ba6;
  background: rgba(255, 255, 255, 0.42);
  border: 1px solid rgba(128, 158, 210, 0.16);
  border-radius: 12px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.58);
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
  font-size: 12px;
  line-height: 1;
  text-align: center;
}

.login-page .login-hero {
  display: grid !important;
  gap: clamp(34px, 6vh, 72px) !important;
  align-content: center !important;
}

.login-page .panel-card {
  padding: 34px !important;
  border-radius: 18px !important;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(255, 255, 255, 0.62)),
    rgba(255, 255, 255, 0.72) !important;
  box-shadow: 0 28px 70px rgba(36, 75, 136, 0.16) !important;
  backdrop-filter: blur(24px) saturate(150%) !important;
  -webkit-backdrop-filter: blur(24px) saturate(150%) !important;
}

@media (max-width: 920px) {
  .login-main {
    grid-template-columns: 1fr;
    gap: 34px;
    align-content: center;
  }

  .login-hero {
    gap: 22px;
  }

  .brand-logo {
    width: 172px;
    height: 96px;
    margin-left: -12px;
  }

  .hero-copy h1 {
    font-size: 40px;
  }
}

@media (max-width: 640px) {
  .login-page {
    min-height: 100vh;
    overflow-y: auto;
  }

  .login-main {
    width: calc(100% - 32px);
    min-height: auto;
    padding: 22px 0 30px;
  }

  .login-hero {
    gap: 18px;
  }

  .brand-logo {
    width: 142px;
    height: 78px;
    margin-left: -8px;
  }

  .hero-copy {
    gap: 8px;
  }

  .hero-copy span {
    font-size: 10px;
  }

  .hero-copy h1 {
    font-size: 30px;
  }

  .hero-copy p {
    font-size: 14px;
  }

  .hero-meta {
    display: none;
  }

  .panel-card {
    padding: 22px;
    border-radius: 14px;
  }

  .panel-head {
    margin-bottom: 18px;
  }

  .panel-head h2 {
    font-size: 24px;
  }

  .auth-tabs {
    margin-bottom: 18px;
  }

  .form-meta {
    margin-bottom: 18px;
  }
}
</style>

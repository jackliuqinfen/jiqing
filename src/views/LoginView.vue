<template>
  <div class="login-page">
    <!-- 左侧品牌区 — 纯色深蓝区块，零渐变零模糊 -->
    <div class="login-brand">
      <div class="brand-content">
        <div class="brand-mark">
          <div class="brand-logo">
            <t-icon name="layers" size="28px" />
          </div>
          <div class="brand-text">
            <h1 class="brand-title">江苏集庆·工程管理系统</h1>
            <p class="brand-subtitle">Engineering Management Console</p>
          </div>
        </div>
        <p class="brand-desc">工程审计、项目协同与经营看板一体化平台</p>
        <div class="brand-features">
          <div class="feature-item">
            <div class="feature-icon-box">
              <t-icon name="check" size="14px" />
            </div>
              <span>审计看板流程流转</span>
          </div>
          <div class="feature-item">
            <div class="feature-icon-box">
              <t-icon name="check" size="14px" />
            </div>
            <span>一审 / 二审双审计对账</span>
          </div>
          <div class="feature-item">
            <div class="feature-icon-box">
              <t-icon name="check" size="14px" />
            </div>
            <span>超期督办 + 审减统计</span>
          </div>
          <div class="feature-item">
            <div class="feature-icon-box">
              <t-icon name="check" size="14px" />
            </div>
              <span>主题配置 + 附件留痕</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧表单区 — 纯白 + 清晰边界 -->
    <div class="login-form-area">
      <div class="form-card">
        <div class="form-header">
          <h2 class="form-title">欢迎回来</h2>
          <p class="form-subtitle">请输入您的账号和密码登录系统</p>
        </div>

        <!-- Tab 切换 -->
        <div class="auth-tabs" role="tablist">
          <button class="auth-tab active" role="tab" aria-selected="true">登录</button>
          <t-tooltip content="请联系管理员" placement="top" :show-arrow="true">
            <button
              class="auth-tab auth-tab--disabled"
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
              登 录
            </t-button>
          </t-form-item>
        </t-form>

        <div class="form-tip">
          <t-icon name="info-circle" size="14px" />
          <span>如无账号，请联系系统管理员开通</span>
        </div>
      </div>

      <p class="login-footer">© 2026 江苏集庆建设 · 工程管理系统</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/store/auth'
import { MessagePlugin } from '@/ui/message'
import type { FormInstanceFunctions, FormRule } from '@/ui/tdesignCompat'

const authStore = useAuthStore()
const route = useRoute()
const router = useRouter()

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
</script>

<style scoped>
/* ========== 页面布局 — 纯色分屏，1px 分割线 ========== */
.login-page {
  display: flex;
  min-height: 100vh;
  background: var(--bg-page);
}

/* ========== 左侧品牌区 — 纯色深蓝，零渐变零模糊 ========== */
.login-brand {
  flex: 0 0 520px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-brand-700);
  color: var(--text-inverse);
  padding: var(--space-10);
}

.brand-content {
  max-width: 380px;
}

.brand-mark {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

.brand-logo {
  width: 52px;
  height: 52px;
  border-radius: var(--radius-md);
  background: var(--color-brand-500);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #FFFFFF;
  flex-shrink: 0;
}

.brand-title {
  font-size: var(--text-2xl);
  font-weight: 700;
  letter-spacing: 0.5px;
  margin: 0 0 var(--space-1);
  color: #FFFFFF;
}

.brand-subtitle {
  font-size: var(--text-xs);
  color: var(--color-brand-200);
  letter-spacing: 1px;
  text-transform: uppercase;
  margin: 0;
  font-weight: 500;
}

.brand-desc {
  font-size: var(--text-md);
  color: var(--color-brand-100);
  margin-bottom: var(--space-8);
  line-height: 1.6;
}

.brand-features {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.feature-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  font-size: var(--text-sm);
  color: rgba(255, 255, 255, 0.9);
  padding: var(--space-1) 0;
}

.feature-icon-box {
  width: 22px;
  height: 22px;
  border-radius: var(--radius-sm);
  background: var(--color-success);
  color: #FFFFFF;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* ========== 右侧表单区 — 纯白卡片 + 清晰边界 ========== */
.login-form-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-8);
  background: var(--bg-page);
}

.form-card {
  width: 100%;
  max-width: 440px;
  background: var(--bg-surface);
  border: 1px solid var(--border-color-strong);
  padding: var(--space-8) var(--space-8) var(--space-6);
}

.form-header {
  margin-bottom: var(--space-6);
}

.form-title {
  font-size: var(--text-2xl);
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 var(--space-1);
}

.form-subtitle {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin: 0;
}

/* Tab 切换 — 纯色扁平 capsule */
.auth-tabs {
  display: flex;
  gap: 0;
  background: var(--color-gray-50);
  border: 1px solid var(--border-color);
  padding: 3px;
  margin-bottom: var(--space-6);
}

.auth-tab {
  flex: 1;
  height: 34px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
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
  opacity: 0.6;
  user-select: none;
}

.auth-form :deep(.t-form__label) {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: 500;
  padding-bottom: var(--space-1);
}

.form-tip {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  margin-top: var(--space-5);
  padding: var(--space-3);
  background: var(--color-gray-20);
  border: 1px solid var(--border-color);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  line-height: 1.5;
}

.form-tip :deep(.t-icon) {
  flex-shrink: 0;
  margin-top: 1px;
  color: var(--text-tertiary);
}

.login-footer {
  margin-top: var(--space-6);
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

/* ========== 响应式 ========== */
@media (max-width: 960px) {
  .login-brand {
    display: none;
  }
  .login-form-area {
    padding: var(--space-5);
  }
  .form-card {
    padding: var(--space-6);
    border: 1px solid var(--border-color);
  }
}
</style>

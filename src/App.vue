<template>
  <div v-if="authStore.status === 'idle'" class="auth-init-loading">
    <ASpin :size="32" text="正在初始化..." />
  </div>
  <router-view v-else />
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/store/auth'

const authStore = useAuthStore()

onMounted(async () => {
  await authStore.initAuth()
})
</script>

<style>
/* ============================================================
   工程管理后台设计系统
   清爽、克制、可扫读，贴近 Arco 后台产品的密度和状态表达
   ============================================================ */

:root {
  /* ── 品牌主色（纯色蓝，无渐变） ── */
  --color-brand-50: #E8F3FF;
  --color-brand-100: #BEDAFF;
  --color-brand-200: #94BFFF;
  --color-brand-300: #6AA1FF;
  --color-brand-400: #4080FF;
  --color-brand-500: #165DFF;
  --color-brand-600: #0E42D2;
  --color-brand-700: #092AA6;
  --color-brand-800: #061D79;
  --color-brand-900: #03114D;
  --color-brand-ink: #165DFF;

  /* ── 中性灰阶（纯色冷静灰） ── */
  --color-gray-0: #FFFFFF;
  --color-gray-20: #FAFBFC;
  --color-gray-50: #F7F8FA;
  --color-gray-100: #F2F3F5;
  --color-gray-200: #E5E6EB;
  --color-gray-300: #C9CDD4;
  --color-gray-400: #A9AEB8;
  --color-gray-500: #86909C;
  --color-gray-600: #4E5969;
  --color-gray-700: #272E3B;
  --color-gray-800: #1D2129;
  --color-gray-900: #0B1020;

  /* ── 语义色（纯色扁平） ── */
  --color-success: #00B42A;
  --color-success-bg: #E8FFEA;
  --color-success-border: #AFF0B5;
  --color-warning: #FF7D00;
  --color-warning-bg: #FFF7E8;
  --color-warning-border: #FFD591;
  --color-risk: #FADC19;
  --color-risk-text: #A87100;
  --color-risk-bg: #FEFFE8;
  --color-risk-border: #FFE58F;
  --color-danger: #F53F3F;
  --color-danger-bg: #FFECE8;
  --color-danger-border: #FDCDC5;
  --color-info: #14C9C9;
  --color-info-bg: #E8FFFB;
  --color-info-border: #B7F4EC;

  /* ── 阶段专属色（看板列标识） ── */
  --color-stage-submitted: #165DFF;
  --color-stage-first-audit: #FF7D00;
  --color-stage-second-audit: #F53F3F;
  --color-stage-conclusion: #14B8A6;
  --color-stage-archived: #86909C;

  /* ── 背景与表面（纯色分层） ── */
  --bg-page: #F7F8FA;
  --bg-surface: #FFFFFF;
  --bg-muted: #F7F8FA;
  --bg-hover: #F2F7FF;
  --bg-active: #E8F3FF;

  /* ── 边框与分割线（1px 实线） ── */
  --border-color: #E5E6EB;
  --border-color-strong: #C9CDD4;
  --divider-color: #E5E6EB;

  /* ── 文本色 ── */
  --text-primary: #1D2129;
  --text-secondary: #4E5969;
  --text-tertiary: #86909C;
  --text-disabled: #C9CDD4;
  --text-inverse: #FFFFFF;
  --text-link: #165DFF;
  --text-on-brand: #FFFFFF;

  /* ── 间距（4px 基准） ── */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;

  /* ── 字体 ── */
  --font-sans: 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'WenQuanYi Micro Hei',
    -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --font-mono: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New',
    monospace;

  /* ── 字号 ── */
  --text-xs: 12px;
  --text-sm: 13px;
  --text-base: 14px;
  --text-md: 15px;
  --text-lg: 16px;
  --text-xl: 18px;
  --text-2xl: 20px;
  --text-3xl: 24px;
  --text-4xl: 30px;

  /* ── 阴影（克制层级，贴近企业级后台） ── */
  --shadow-flat: none;
  --shadow-card: 0 4px 10px rgba(29, 33, 41, 0.04);
  --shadow-elevated: 0 6px 16px rgba(29, 33, 41, 0.08);
  --shadow-dropdown: 0 4px 12px rgba(29, 33, 41, 0.12);
  --shadow-overlay: 0 8px 24px rgba(29, 33, 41, 0.16);

  /* ── 圆角（小圆角，克制使用） ── */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 8px;

  /* ── 过渡 ── */
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --duration-fast: 120ms;
  --duration-normal: 180ms;
  --duration-slow: 240ms;

  /* ── 布局常量 ── */
  --header-height: 56px;
}

/* ============================================================
   基础重置
   ============================================================ */
*,
*::before,
*::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html {
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-rendering: optimizeLegibility;
}

body {
  font-family: var(--font-sans);
  font-size: var(--text-base);
  line-height: 1.5;
  color: var(--text-primary);
  background: var(--bg-page);
}

button,
input,
textarea,
select {
  font-family: inherit;
}

a {
  color: var(--text-link);
}

a:hover {
  color: var(--color-brand-400);
}

/* ============================================================
   Arco Design 全局变量覆盖（全部对齐扁平纯色体系）
   ============================================================ */
:root {
  --color-primary-1: var(--color-brand-50);
  --color-primary-2: var(--color-brand-100);
  --color-primary-3: var(--color-brand-200);
  --color-primary-4: var(--color-brand-300);
  --color-primary-5: var(--color-brand-400);
  --color-primary-6: var(--color-brand-500);
  --color-primary-7: var(--color-brand-600);
  --color-primary-8: var(--color-brand-700);
  --color-primary-9: var(--color-brand-800);
  --color-primary-10: var(--color-brand-900);
  --color-bg-1: var(--bg-surface);
  --color-bg-2: var(--bg-muted);
  --color-bg-3: var(--bg-page);
  --color-fill-1: var(--bg-hover);
  --color-fill-2: var(--bg-active);
  --color-border-1: var(--border-color);
  --color-border-2: var(--border-color-strong);
  --color-text-1: var(--text-primary);
  --color-text-2: var(--text-secondary);
  --color-text-3: var(--text-tertiary);
  --color-text-4: var(--text-disabled);
  --border-radius-small: var(--radius-sm);
  --border-radius-medium: var(--radius-md);
  --border-radius-large: var(--radius-lg);
  --box-shadow1: none;
  --box-shadow2: var(--shadow-elevated);
  --box-shadow3: var(--shadow-overlay);
}

/* ============================================================
   Arco 业务按钮统一：主操作跟随品牌色，次要操作保持中性
   ============================================================ */
.arco-btn.app-button--brand,
.arco-btn-primary {
  color: var(--text-on-brand) !important;
  background-color: var(--color-brand-500) !important;
  border-color: var(--color-brand-500) !important;
}

.arco-btn.app-button--brand:not(.arco-btn-disabled):hover,
.arco-btn.app-button--brand:not(.arco-btn-disabled):focus-visible,
.arco-btn-primary:not(.arco-btn-disabled):hover,
.arco-btn-primary:not(.arco-btn-disabled):focus-visible {
  color: var(--text-on-brand) !important;
  background-color: var(--color-brand-600) !important;
  border-color: var(--color-brand-600) !important;
}

.arco-btn.app-button--brand-outline,
.arco-btn-outline {
  color: var(--color-brand-600) !important;
  background-color: var(--bg-surface) !important;
  border-color: var(--color-brand-300) !important;
}

.arco-btn.app-button--brand-outline:not(.arco-btn-disabled):hover,
.arco-btn.app-button--brand-outline:not(.arco-btn-disabled):focus-visible,
.arco-btn-outline:not(.arco-btn-disabled):hover,
.arco-btn-outline:not(.arco-btn-disabled):focus-visible {
  color: var(--color-brand-700) !important;
  background-color: var(--color-brand-50) !important;
  border-color: var(--color-brand-500) !important;
}

.arco-btn.app-button--neutral,
.arco-btn-secondary {
  color: var(--text-secondary) !important;
  background-color: var(--bg-surface) !important;
  border-color: var(--border-color) !important;
}

.arco-btn.app-button--neutral:not(.arco-btn-disabled):hover,
.arco-btn.app-button--neutral:not(.arco-btn-disabled):focus-visible,
.arco-btn-secondary:not(.arco-btn-disabled):hover,
.arco-btn-secondary:not(.arco-btn-disabled):focus-visible {
  color: var(--color-brand-600) !important;
  background-color: var(--color-brand-50) !important;
  border-color: var(--color-brand-300) !important;
}

.arco-btn-disabled,
.arco-btn[disabled] {
  color: var(--text-disabled) !important;
  background-color: var(--color-gray-100) !important;
  border-color: var(--border-color) !important;
}

/* ============================================================
   通用工具类
   ============================================================ */
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ============================================================
   认证初始化 loading
   ============================================================ */
.auth-init-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  background: var(--bg-page);
}

/* ============================================================
   滚动条 — 扁平细条
   ============================================================ */
::-webkit-scrollbar {
  width: 5px;
  height: 5px;
}

::-webkit-scrollbar-thumb {
  background: var(--color-gray-200);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--color-gray-300);
}

::-webkit-scrollbar-track {
  background: transparent;
}
</style>


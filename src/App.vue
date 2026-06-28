<template>
  <div v-if="authStore.status === 'idle'" class="auth-init-loading">
    <t-loading size="large" text="正在初始化..." />
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
  --color-brand-50: #EBF0FF;
  --color-brand-100: #D6E0FF;
  --color-brand-200: #ADC2FF;
  --color-brand-300: #85A3FF;
  --color-brand-400: #5C85FF;
  --color-brand-500: #4787F0;
  --color-brand-600: #2566D9;
  --color-brand-700: #164FB6;
  --color-brand-800: #0028A3;
  --color-brand-900: #001C85;
  --color-brand-ink: #4787F0;

  /* ── 中性灰阶（纯色冷静灰） ── */
  --color-gray-0: #FFFFFF;
  --color-gray-20: #FAFBFC;
  --color-gray-50: #F2F3F7;
  --color-gray-100: #E5E7EB;
  --color-gray-200: #D1D5DB;
  --color-gray-300: #B0B7C3;
  --color-gray-400: #8E95A3;
  --color-gray-500: #6B7280;
  --color-gray-600: #4B5563;
  --color-gray-700: #374151;
  --color-gray-800: #1F2937;
  --color-gray-900: #111827;

  /* ── 语义色（纯色扁平） ── */
  --color-success: #00B42A;
  --color-success-bg: #E6F9F2;
  --color-success-border: #B3EAD5;
  --color-warning: #FF8D1A;
  --color-warning-bg: #FFF4E6;
  --color-warning-border: #FFD9B3;
  --color-danger: #FF3B3B;
  --color-danger-bg: #FFEBEB;
  --color-danger-border: #FFCCCC;
  --color-info: #14C9C9;
  --color-info-bg: #E6F9F7;
  --color-info-border: #B3EDE7;

  /* ── 阶段专属色（看板列标识） ── */
  --color-stage-submitted: #3366FF;
  --color-stage-first-audit: #FF8D1A;
  --color-stage-second-audit: #FF3B3B;
  --color-stage-conclusion: #14B8A6;
  --color-stage-archived: #8E95A3;

  /* ── 背景与表面（纯色分层） ── */
  --bg-page: #F5F7FB;
  --bg-surface: #FFFFFF;
  --bg-muted: #F8FAFD;
  --bg-hover: #EFF5FF;
  --bg-active: #EAF2FF;

  /* ── 边框与分割线（1px 实线） ── */
  --border-color: #E6EAF2;
  --border-color-strong: #D6DEEA;
  --divider-color: #E6EAF2;

  /* ── 文本色 ── */
  --text-primary: #17233D;
  --text-secondary: #5F6F89;
  --text-tertiary: #9AA8BC;
  --text-disabled: #B0B7C3;
  --text-inverse: #FFFFFF;
  --text-link: #4787F0;
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

  /* ── 阴影（仅保留极简的 2 级，纯扁平风格） ── */
  --shadow-flat: none;
  --shadow-elevated: 0 6px 18px rgba(17, 36, 75, 0.06);
  --shadow-overlay: 0 18px 48px rgba(17, 36, 75, 0.16);

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
  --border-radius-small: var(--radius-sm);
  --border-radius-medium: var(--radius-md);
  --border-radius-large: var(--radius-lg);
  --box-shadow1: none;
  --box-shadow2: var(--shadow-elevated);
  --box-shadow3: var(--shadow-overlay);
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

import { getCurrentTheme } from '@/api/system'
import type { CurrentTheme, ThemeSetting } from '@/types'

type ThemeTokens = {
  brand: string
  brandDark: string
  success: string
  warning: string
  page: string
  surface: string
  muted: string
  text: string
  secondary: string
  border: string
}

function normalizeHexColor(value?: string) {
  const raw = String(value || '').trim()
  const match = raw.match(/^#?([0-9a-fA-F]{6})$/)
  return match ? `#${match[1].toUpperCase()}` : ''
}

function relativeLuminance(hex: string) {
  const { r, g, b } = hexToRgb(hex)
  const channel = (value: number) => {
    const normalized = value / 255
    return normalized <= 0.03928
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

export function normalizeArcoThemePackage(value?: string) {
  const raw = String(value || '').trim()
  return /^@(arco-design\/theme|arco-themes\/vue)-[a-z0-9-]+$/i.test(raw) ? raw : ''
}

export function arcoThemeCssUrl(themePackage: string) {
  return `https://cdn.jsdelivr.net/npm/${themePackage}/css/arco.css`
}

function setArcoThemeLink(themePackage?: string) {
  const id = 'dynamic-arco-theme-css'
  const current = document.getElementById(id) as HTMLLinkElement | null
  const normalized = normalizeArcoThemePackage(themePackage)
  if (!normalized) {
    current?.remove()
    return
  }
  const href = arcoThemeCssUrl(normalized)
  if (current?.href === href) return
  const next = document.createElement('link')
  next.id = id
  next.rel = 'stylesheet'
  next.href = href
  current?.replaceWith(next)
  if (!current) document.head.appendChild(next)
}

export function loadArcoThemePackage(themePackage: string): Promise<void> {
  const normalized = normalizeArcoThemePackage(themePackage)
  if (!normalized) return Promise.reject(new Error('请输入形如 @arco-design/theme-christmas 或 @arco-themes/vue-cestc-wuhan-linear 的主题字符'))
  const href = arcoThemeCssUrl(normalized)
  const existing = document.querySelector<HTMLLinkElement>(`link[data-arco-theme-test="${normalized}"]`)
  if (existing?.dataset.loaded === 'true') return Promise.resolve()

  return new Promise((resolve, reject) => {
    const probe = document.createElement('link')
    const timeout = window.setTimeout(() => {
      probe.remove()
      reject(new Error('主题加载超时，请检查主题字符或网络'))
    }, 12000)

    probe.rel = 'stylesheet'
    probe.href = href
    probe.dataset.arcoThemeTest = normalized
    probe.onload = () => {
      window.clearTimeout(timeout)
      probe.dataset.loaded = 'true'
      setArcoThemeLink(normalized)
      probe.remove()
      resolve()
    }
    probe.onerror = () => {
      window.clearTimeout(timeout)
      probe.remove()
      reject(new Error('主题加载失败，请确认主题字符已发布且可访问'))
    }
    document.head.appendChild(probe)
  })
}

function hexToRgb(hex: string) {
  const value = normalizeHexColor(hex).slice(1)
  return {
    r: Number.parseInt(value.slice(0, 2), 16),
    g: Number.parseInt(value.slice(2, 4), 16),
    b: Number.parseInt(value.slice(4, 6), 16),
  }
}

function rgbToHex({ r, g, b }: { r: number; g: number; b: number }) {
  return `#${[r, g, b].map((n) => Math.round(Math.min(255, Math.max(0, n))).toString(16).padStart(2, '0')).join('').toUpperCase()}`
}

function mixColor(color: string, target: string, weight: number) {
  const from = hexToRgb(color)
  const to = hexToRgb(target)
  return rgbToHex({
    r: from.r * (1 - weight) + to.r * weight,
    g: from.g * (1 - weight) + to.g * weight,
    b: from.b * (1 - weight) + to.b * weight,
  })
}

export function sanitizeBrandColor(value?: string, fallback = '#4787F0') {
  const normalized = normalizeHexColor(value)
  const safeFallback = normalizeHexColor(fallback) || '#4787F0'
  if (!normalized) return safeFallback
  if (relativeLuminance(normalized) <= 0.82) return normalized
  const darker = mixColor(normalized, '#000000', 0.45)
  if (relativeLuminance(darker) <= 0.82) return darker
  const darkerFallback = mixColor(normalized, '#000000', 0.6)
  return relativeLuminance(darkerFallback) <= 0.82 ? darkerFallback : safeFallback
}

const themeTokens: Record<string, ThemeTokens> = {
  'arco-theme-0000': {
    brand: '#4787F0',
    brandDark: '#2566D9',
    success: '#00B42A',
    warning: '#FF7D00',
    page: '#F2F3F7',
    surface: '#FFFFFF',
    muted: '#FAFBFC',
    text: '#111827',
    secondary: '#6B7280',
    border: '#E5E7EB',
  },
  'arco-default': {
    brand: '#4787F0',
    brandDark: '#2566D9',
    success: '#00B42A',
    warning: '#FF7D00',
    page: '#F2F3F7',
    surface: '#FFFFFF',
    muted: '#FAFBFC',
    text: '#111827',
    secondary: '#6B7280',
    border: '#E5E7EB',
  },
  'jiqing-blue': {
    brand: '#0E42D2',
    brandDark: '#092B8A',
    success: '#14C9C9',
    warning: '#F7BA1E',
    page: '#F3F7FF',
    surface: '#FFFFFF',
    muted: '#EDF3FF',
    text: '#0F1F3D',
    secondary: '#53627A',
    border: '#D8E2F2',
  },
  'engineering-green': {
    brand: '#008F7A',
    brandDark: '#00685B',
    success: '#00B42A',
    warning: '#FF9A2E',
    page: '#F1FAF8',
    surface: '#FFFFFF',
    muted: '#E8FFFB',
    text: '#102A27',
    secondary: '#526A66',
    border: '#CFE8E2',
  },
  'gov-gray-blue': {
    brand: '#1D3557',
    brandDark: '#10213A',
    success: '#2A9D8F',
    warning: '#E9C46A',
    page: '#F3F6F8',
    surface: '#FFFFFF',
    muted: '#EAF0F4',
    text: '#172033',
    secondary: '#5F6C7B',
    border: '#D7E0E7',
  },
  'dark-command': {
    brand: '#165DFF',
    brandDark: '#4C86FF',
    success: '#00B42A',
    warning: '#FFB65E',
    page: '#0B1220',
    surface: '#111827',
    muted: '#162033',
    text: '#F8FAFC',
    secondary: '#CBD5E1',
    border: '#26344D',
  },
}

function setVar(name: string, value: string) {
  document.documentElement.style.setProperty(name, value)
}

export function applyTheme(setting: ThemeSetting | CurrentTheme) {
  const tokens = themeTokens[setting.themeKey] || themeTokens['arco-theme-0000']
  const brand = sanitizeBrandColor(setting.brandColor, tokens.brand)
  const brandDark = mixColor(brand, '#000000', 0.22)
  document.documentElement.dataset.theme = setting.themeKey
  setArcoThemeLink(setting.themePackage)
  document.documentElement.dataset.compact = setting.compactMode ? 'true' : 'false'
  document.documentElement.dataset.dark = setting.darkMode || setting.themeKey === 'dark-command' ? 'true' : 'false'

  setVar('--color-brand-50', `${brand}14`)
  setVar('--color-brand-100', `${brand}24`)
  setVar('--color-brand-200', mixColor(brand, '#FFFFFF', 0.64))
  setVar('--color-brand-300', mixColor(brand, '#FFFFFF', 0.42))
  setVar('--color-brand-400', mixColor(brand, '#FFFFFF', 0.22))
  setVar('--color-brand-500', brand)
  setVar('--color-brand-600', brandDark)
  setVar('--color-brand-700', mixColor(brand, '#000000', 0.34))
  setVar('--color-success', tokens.success)
  setVar('--color-warning', tokens.warning)
  setVar('--bg-page', tokens.page)
  setVar('--bg-surface', tokens.surface)
  setVar('--bg-muted', tokens.muted)
  setVar('--bg-hover', tokens.muted)
  setVar('--bg-active', `${brand}16`)
  setVar('--text-primary', tokens.text)
  setVar('--text-secondary', tokens.secondary)
  setVar('--border-color', tokens.border)
  setVar('--divider-color', tokens.border)
  setVar('--color-primary-6', brand)
  setVar('--color-primary-7', brandDark)
}

export async function initThemePreference() {
  try {
    const theme = await getCurrentTheme()
    applyTheme(theme)
  } catch {
    applyTheme({ themeKey: 'arco-theme-0000', darkMode: false, compactMode: false, applyScope: 'global' })
  }
}

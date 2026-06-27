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

const themeTokens: Record<string, ThemeTokens> = {
  'arco-theme-0000': {
    brand: '#165DFF',
    brandDark: '#0E42D2',
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
    brand: '#165DFF',
    brandDark: '#0E42D2',
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
  document.documentElement.dataset.theme = setting.themeKey
  document.documentElement.dataset.compact = setting.compactMode ? 'true' : 'false'
  document.documentElement.dataset.dark = setting.darkMode || setting.themeKey === 'dark-command' ? 'true' : 'false'

  setVar('--color-brand-50', `${tokens.brand}14`)
  setVar('--color-brand-100', `${tokens.brand}24`)
  setVar('--color-brand-500', tokens.brand)
  setVar('--color-brand-600', tokens.brandDark)
  setVar('--color-brand-700', tokens.brandDark)
  setVar('--color-success', tokens.success)
  setVar('--color-warning', tokens.warning)
  setVar('--bg-page', tokens.page)
  setVar('--bg-surface', tokens.surface)
  setVar('--bg-muted', tokens.muted)
  setVar('--bg-hover', tokens.muted)
  setVar('--bg-active', `${tokens.brand}16`)
  setVar('--text-primary', tokens.text)
  setVar('--text-secondary', tokens.secondary)
  setVar('--border-color', tokens.border)
  setVar('--divider-color', tokens.border)
  setVar('--color-primary-6', tokens.brand)
  setVar('--color-primary-7', tokens.brandDark)
}

export async function initThemePreference() {
  try {
    const theme = await getCurrentTheme()
    applyTheme(theme)
  } catch {
    applyTheme({ themeKey: 'arco-theme-0000', darkMode: false, compactMode: false, applyScope: 'global' })
  }
}


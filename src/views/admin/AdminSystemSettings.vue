<template>
  <div class="admin-settings">
    <PageHeader title="系统设置" description="管理登录、账号开通和界面风格等常用设置">
      <template #meta>
        <t-tag variant="light" theme="primary">常用设置</t-tag>
        <t-tag variant="light">界面 / 账号 / 登录</t-tag>
      </template>
    </PageHeader>

    <t-card class="settings-card theme-card" title="界面风格" :bordered="true">
      <template #actions>
        <t-button size="small" variant="outline" :loading="savingTheme" @click="resetTheme">恢复默认</t-button>
      </template>
      <div class="theme-current">
        <div>
          <span class="field-label">当前风格</span>
          <strong>{{ currentThemeName }}</strong>
          <em>{{ themeSettings.darkMode ? '深色显示' : '浅色显示' }} · {{ themeSettings.compactMode ? '紧凑间距' : '标准间距' }}</em>
        </div>
        <div class="theme-toggles">
          <label>
            <t-switch v-model="themeSettings.compactMode" size="small" @change="saveTheme" />
            <span>紧凑显示</span>
          </label>
          <label>
            <t-switch v-model="themeSettings.darkMode" size="small" @change="saveTheme" />
            <span>深色模式</span>
          </label>
        </div>
      </div>
      <div class="brand-color-panel">
        <div>
          <span class="field-label">品牌主色</span>
          <strong>{{ normalizedBrandColor }}</strong>
          <em>输入 6 位色号，保存后侧栏、按钮、选中状态和预览会同步更新。</em>
        </div>
        <div class="brand-color-controls">
          <input
            :value="normalizedBrandColor"
            class="brand-color-picker"
            type="color"
            :disabled="savingTheme"
            aria-label="选择品牌主色"
            @input="updateBrandColor"
          />
          <input
            v-model.trim="themeSettings.brandColor"
            class="brand-color-input"
            placeholder="#4787F0"
            :disabled="savingTheme"
            @keyup.enter="saveTheme"
          />
          <t-button size="small" theme="primary" :loading="savingTheme" @click="saveTheme">应用品牌色</t-button>
          <span v-if="brandColorError" class="brand-color-error">{{ brandColorError }}</span>
        </div>
      </div>
      <div class="logo-color-panel">
        <div>
          <span class="field-label">侧边栏 LOGO 色彩</span>
          <strong>{{ sidebarLogoVariantLabel }}</strong>
          <em>仅影响业务界面左侧导航 LOGO，不改变登录页 LOGO 和登录页配色。</em>
        </div>
        <div class="logo-color-switch" role="group" aria-label="侧边栏 LOGO 色彩">
          <button
            v-for="option in sidebarLogoVariantOptions"
            :key="option.value"
            type="button"
            :class="{ active: themeSettings.sidebarLogoVariant === option.value }"
            :disabled="savingTheme"
            @click="selectSidebarLogoVariant(option.value)"
          >
            <i :class="`logo-sample logo-sample--${option.value}`" />
            <span>{{ option.label }}</span>
          </button>
        </div>
      </div>
      <div class="theme-package-panel">
        <div>
          <span class="field-label">主题商店样式</span>
          <strong>{{ themePackageInput ? '已填写样式名称' : '未使用外部样式' }}</strong>
          <em>需要使用主题商店样式时，粘贴完整样式名称。应用成功后会询问是否同步推荐品牌色，并返回首页查看效果。</em>
        </div>
        <div class="theme-package-controls">
          <input
            v-model.trim="themePackageInput"
            class="theme-package-input"
            placeholder="请输入主题商店样式名称"
            :disabled="savingTheme"
            @keyup.enter="applyThemePackage"
          />
          <t-button size="small" theme="primary" :loading="savingTheme" @click="applyThemePackage">应用样式</t-button>
          <t-button size="small" variant="outline" :disabled="savingTheme || !themeSettings.themePackage" @click="clearThemePackage">恢复内置样式</t-button>
          <span v-if="themePackageError" class="theme-package-error">{{ themePackageError }}</span>
        </div>
      </div>
      <div class="theme-grid">
        <button
          v-for="theme in themeOptions"
          :key="theme.themeKey"
          class="theme-option"
          :class="{ 'theme-option--active': themeSettings.themeKey === theme.themeKey, 'theme-option--disabled': !theme.isEnabled }"
          :disabled="!theme.isEnabled || savingTheme"
          type="button"
          @click="selectTheme(theme)"
        >
          <span class="theme-swatch-row">
            <i v-for="color in theme.previewColors" :key="color" :style="{ backgroundColor: color }" />
          </span>
          <span class="theme-name">{{ friendlyThemeName(theme) }}</span>
          <span class="theme-package">{{ friendlyThemeDescription(theme) }}</span>
          <span class="theme-meta">{{ theme.isDefault ? '推荐风格' : theme.isEnabled ? '可使用' : '暂不可用' }}</span>
        </button>
      </div>

      <div class="theme-scope-panel">
        <div>
          <span class="field-label">应用范围</span>
          <strong>{{ applyScopeLabel }}</strong>
          <em>选择界面风格和品牌色在哪些页面生效，便于分阶段调整。</em>
        </div>
        <div class="scope-switch" role="group" aria-label="主题应用范围">
          <button
            v-for="scope in applyScopeOptions"
            :key="scope.value"
            type="button"
            :class="{ active: themeSettings.applyScope === scope.value }"
            :disabled="savingTheme"
            @click="selectApplyScope(scope.value)"
          >
            {{ scope.label }}
          </button>
        </div>
      </div>

      <div class="theme-preview-board">
        <section class="theme-preview-card">
          <div class="preview-head">
            <span>当前风格预览</span>
            <strong>{{ currentThemeName }}</strong>
          </div>
          <div class="preview-shell" :style="previewStyle">
            <div class="preview-sidebar">
              <i />
              <span>工程管理</span>
            </div>
            <div class="preview-main">
              <div class="preview-toolbar">
                <span />
                <em />
              </div>
              <div class="preview-kpis">
                <b>10</b>
                <b>4</b>
                <b>2</b>
              </div>
              <div class="preview-list">
                <span />
                <span />
                <span />
              </div>
            </div>
          </div>
          <div class="theme-facts">
            <span>当前风格：{{ currentThemeName }}</span>
            <span>适用范围：{{ applyScopeLabel }}</span>
            <span>使用状态：{{ activeTheme?.isEnabled ? '可正常使用' : '暂不可用' }}</span>
            <span>推荐风格：{{ activeTheme?.isDefault ? '是' : '否' }}</span>
          </div>
        </section>

        <section class="theme-preview-card">
          <div class="preview-head">
            <span>数据图预览</span>
            <strong>看板图表</strong>
          </div>
          <div class="chart-preview">
            <VChartPanel :spec="chartPreviewSpec" />
          </div>
          <p class="preview-note">数据图会跟随当前品牌色和辅助色，方便看板保持统一观感。</p>
        </section>
      </div>
    </t-card>

    <t-dialog
      v-model:visible="brandFollowDialogVisible"
      header="是否同步品牌主色"
      :confirm-btn="{ content: '同步推荐颜色', loading: savingTheme }"
      :cancel-btn="{ content: '保留当前品牌色' }"
      width="460px"
      @confirm="confirmFollowThemeBrandColor"
      @update:visible="handleBrandFollowDialogVisible"
    >
      <div class="brand-follow-dialog">
        <p>界面样式已应用成功。是否将品牌主色同步为该样式推荐颜色？</p>
        <div class="brand-follow-preview">
          <i :style="{ backgroundColor: pendingThemeBrandColor }" />
          <span>{{ pendingThemeBrandColor }}</span>
        </div>
        <em>选择“保留当前品牌色”会只应用界面样式，不改变侧栏、按钮和业务高亮色。</em>
      </div>
    </t-dialog>

    <!-- 注册设置卡片 -->
    <t-card class="settings-card" title="账号开通" :bordered="true">
      <template #actions>
        <t-button size="small" variant="outline" :loading="savingReg" @click="saveRegistration">保存</t-button>
      </template>
      <t-form label-align="left" label-width="140px" class="settings-form">
        <t-form-item label="允许自行申请账号" help="关闭后，新账号由管理员统一开通">
          <t-switch v-model="regSettings.enabled" size="large" />
          <span class="switch-text">{{ regSettings.enabled ? '已开放' : '已关闭' }}</span>
        </t-form-item>
        <t-form-item label="申请后需要审核" help="开启后，新账号审核通过后才能登录">
          <t-switch v-model="regSettings.requireApproval" size="large" />
          <span class="switch-text">{{ regSettings.requireApproval ? '需要审批' : '无需审批' }}</span>
        </t-form-item>
      </t-form>
    </t-card>

    <!-- 登录规则卡片 -->
    <t-card class="settings-card" title="登录安全" :bordered="true">
      <template #actions>
        <t-button size="small" variant="outline" :loading="savingLogin" @click="saveLoginRules">保存</t-button>
      </template>
      <t-form label-align="left" label-width="160px" class="settings-form">
        <t-form-item label="密码最少位数" help="建议不少于 6 位，降低账号被误用的风险">
          <t-input-number v-model="loginRulesSettings.minPasswordLength" :min="1" :max="32" style="width:180px" />
        </t-form-item>
        <t-form-item label="最多输错次数" help="连续输错超过该次数后，账号会暂时保护">
          <t-input-number v-model="loginRulesSettings.maxLoginAttempts" :min="1" :max="20" style="width:180px" />
        </t-form-item>
        <t-form-item label="自动退出时间" help="长时间未操作时，系统会自动退出登录">
          <t-input-number v-model="loginRulesSettings.sessionTimeoutMinutes" :min="15" :max="1440" style="width:180px" />
          <span class="switch-text">分钟</span>
        </t-form-item>
        <t-form-item label="允许多处登录" help="关闭后，同一账号新登录时，原位置会自动退出">
          <t-switch v-model="loginRulesSettings.allowConcurrentSessions" size="large" />
          <span class="switch-text">{{ loginRulesSettings.allowConcurrentSessions ? '允许' : '不允许' }}</span>
        </t-form-item>
      </t-form>
    </t-card>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import type { ISpec } from '@visactor/vchart/esm/core'
import {
  getCurrentTheme,
  getSystemSetting,
  getThemeOptions,
  resetCurrentTheme,
  setSystemSetting,
  updateCurrentTheme,
} from '@/api/system'
import VChartPanel from '@/components/VChartPanel.vue'
import { useAuthStore } from '@/store/auth'
import { MessagePlugin } from '@/ui/message'
import { applyTheme, loadArcoThemePackage, normalizeArcoThemePackage } from '@/ui/theme'
import type { RegistrationSetting, LoginRulesSetting, ThemeOption, ThemeSetting } from '@/types'
import PageHeader from '@/components/PageHeader.vue'

const authStore = useAuthStore()
const router = useRouter()
const savingReg = ref(false)
const savingLogin = ref(false)
const savingTheme = ref(false)
const themeOptions = ref<ThemeOption[]>([])
const themePackageInput = ref('')
const brandFollowDialogVisible = ref(false)
const pendingThemePackage = ref('')
const pendingThemeBrandColor = ref('#4787F0')
const brandFollowDecisionHandled = ref(false)

const regSettings = reactive<RegistrationSetting>({ enabled: false, requireApproval: true })
const loginRulesSettings = reactive<LoginRulesSetting>({
  minPasswordLength: 1, maxLoginAttempts: 5, sessionTimeoutMinutes: 480, allowConcurrentSessions: true,
})
const themeSettings = reactive<ThemeSetting>({
  themeKey: 'arco-theme-0000',
  darkMode: false,
  compactMode: false,
  applyScope: 'global',
  brandColor: '#4787F0',
  themePackage: '',
  sidebarLogoVariant: 'color',
})

const applyScopeOptions = [
  { label: '全局', value: 'global' },
  { label: '首页数据看板', value: 'dashboard' },
  { label: '审计看板', value: 'audit' },
  { label: '后台管理', value: 'admin' },
]

const sidebarLogoVariantOptions = [
  { label: '彩色', value: 'color' },
  { label: '白色', value: 'white' },
  { label: '黑色', value: 'black' },
] as const

const currentThemeName = computed(() => {
  const theme = themeOptions.value.find((item) => item.themeKey === themeSettings.themeKey)
  return theme ? friendlyThemeName(theme) : '默认蓝色风格'
})

const activeTheme = computed(() => themeOptions.value.find((item) => item.themeKey === themeSettings.themeKey) || null)

function normalizeHexColor(value?: string) {
  const raw = String(value || '').trim()
  const match = raw.match(/^#?([0-9a-fA-F]{6})$/)
  return match ? `#${match[1].toUpperCase()}` : ''
}

function rgbToHex(value: string) {
  const hex = normalizeHexColor(value)
  if (hex) return hex
  const match = value.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i)
  if (!match) return ''
  return `#${match.slice(1, 4).map((item) => Number(item).toString(16).padStart(2, '0')).join('').toUpperCase()}`
}

function getThemePackageBrandColor() {
  const styles = getComputedStyle(document.documentElement)
  const candidates = ['--primary-6', '--color-primary-6', '--arcoblue-6']
  for (const key of candidates) {
    const color = rgbToHex(styles.getPropertyValue(key).trim())
    if (color) return color
  }
  return normalizedBrandColor.value
}

function updateBrandColor(event: Event) {
  themeSettings.brandColor = (event.target as HTMLInputElement).value
}

const normalizedBrandColor = computed(() => normalizeHexColor(themeSettings.brandColor) || '#4787F0')

const brandColorError = computed(() => {
  return normalizeHexColor(themeSettings.brandColor) ? '' : '请输入例如 #4787F0 的 6 位色号'
})

const themePackageError = computed(() => {
  if (!themePackageInput.value) return ''
  return normalizeArcoThemePackage(themePackageInput.value) ? '' : '样式名称格式不正确，请从主题商店复制完整名称后再试。'
})

const activePreviewColors = computed(() => {
  const colors = activeTheme.value?.previewColors || []
  const palette = colors.length ? colors : ['#165DFF', '#14C9C9', '#00B42A', '#FF7D00']
  return [normalizedBrandColor.value, ...palette.slice(1)]
})

const applyScopeLabel = computed(() => {
  return applyScopeOptions.find((item) => item.value === themeSettings.applyScope)?.label || '全局'
})

const sidebarLogoVariantLabel = computed(() => {
  return sidebarLogoVariantOptions.find((item) => item.value === themeSettings.sidebarLogoVariant)?.label || '彩色'
})

function friendlyThemeName(theme?: ThemeOption | null) {
  if (!theme) return '默认蓝色风格'
  const key = theme.themeKey
  if (key === 'arco-theme-0000' || theme.isDefault) return '默认蓝色风格'
  if (key === 'arco-default') return '经典蓝色风格'
  if (key === 'jiqing-blue') return '专业蓝色风格'
  if (key === 'engineering-green') return '工程绿色风格'
  if (key === 'gov-gray-blue') return '政企灰蓝风格'
  if (key === 'dark-command') return '深色看板风格'
  return theme.themeName.replace(/Arco|Theme|主题包|fallback/gi, '').trim() || '自定义风格'
}

function friendlyThemeDescription(theme: ThemeOption) {
  if (!theme.isEnabled) return '暂不可用'
  if (theme.isDefault) return '适合日常办公'
  if (theme.themeKey === 'dark-command') return '适合大屏展示'
  if (theme.themeKey === 'engineering-green') return '适合工程资料场景'
  if (theme.themeKey === 'gov-gray-blue') return '适合正式汇报场景'
  return '可用于看板和后台页面'
}

const previewStyle = computed(() => {
  const [brand, cyan, green, warning] = activePreviewColors.value
  const dark = themeSettings.darkMode || themeSettings.themeKey === 'dark-command'
  return {
    '--preview-brand': brand,
    '--preview-cyan': cyan || brand,
    '--preview-green': green || '#00B42A',
    '--preview-warning': warning || '#FF7D00',
    '--preview-bg': dark ? '#0B1220' : '#F5F8FC',
    '--preview-surface': dark ? '#111827' : '#FFFFFF',
    '--preview-text': dark ? '#F8FAFC' : '#172033',
    '--preview-border': dark ? '#26344D' : '#D7E0E7',
  }
})

const chartPreviewSpec = computed<ISpec>(() => ({
  type: 'bar',
  background: 'transparent',
  color: activePreviewColors.value,
  data: [{
    id: 'themePreview',
    values: [
      { stage: '送审', count: 10 },
      { stage: '一审', count: 4 },
      { stage: '二审', count: 3 },
      { stage: '归档', count: 2 },
    ],
  }],
  xField: 'stage',
  yField: 'count',
  seriesField: 'stage',
  padding: { top: 14, right: 12, bottom: 32, left: 34 },
  tooltip: { visible: true },
  animationAppear: { duration: 720, easing: 'cubicOut' },
  bar: { style: { cornerRadius: [3, 3, 0, 0] } },
  axes: [
    { orient: 'bottom', label: { autoHide: true } },
    { orient: 'left', min: 0, tick: { tickCount: 4 } },
  ],
} as ISpec))

onMounted(async () => {
  try {
    const [reg, login, themes, currentTheme] = await Promise.all([
      getSystemSetting('registration_open'),
      getSystemSetting('login_rules'),
      getThemeOptions(),
      getCurrentTheme(),
    ])
    if (reg) Object.assign(regSettings, reg.value as RegistrationSetting)
    if (login) Object.assign(loginRulesSettings, login.value as LoginRulesSetting)
    themeOptions.value = themes
    Object.assign(themeSettings, {
      themeKey: currentTheme.themeKey,
      darkMode: currentTheme.darkMode,
      compactMode: currentTheme.compactMode,
      applyScope: currentTheme.applyScope,
      brandColor: currentTheme.brandColor || '#4787F0',
      themePackage: currentTheme.themePackage || '',
      sidebarLogoVariant: currentTheme.sidebarLogoVariant || 'color',
    })
    themePackageInput.value = currentTheme.themePackage || ''
    applyTheme(currentTheme)
  } catch { /* 默认值 */ }
})

async function selectTheme(theme: ThemeOption) {
  if (!theme.isEnabled || theme.themeKey === themeSettings.themeKey) return
  themeSettings.themeKey = theme.themeKey
  await saveTheme()
}

async function selectApplyScope(scope: string) {
  if (themeSettings.applyScope === scope) return
  themeSettings.applyScope = scope
  await saveTheme()
}

async function selectSidebarLogoVariant(variant: ThemeSetting['sidebarLogoVariant']) {
  if (!variant || themeSettings.sidebarLogoVariant === variant) return
  themeSettings.sidebarLogoVariant = variant
  await saveTheme()
}

async function saveTheme() {
  if (brandColorError.value) {
    MessagePlugin.warning(brandColorError.value)
    return
  }
  savingTheme.value = true
  try {
    const next = await updateCurrentTheme({ ...themeSettings, brandColor: normalizedBrandColor.value })
    Object.assign(themeSettings, {
      themeKey: next.themeKey,
      darkMode: next.darkMode,
      compactMode: next.compactMode,
      applyScope: next.applyScope,
      brandColor: next.brandColor || normalizedBrandColor.value,
      themePackage: next.themePackage || '',
      sidebarLogoVariant: next.sidebarLogoVariant || 'color',
    })
    themePackageInput.value = next.themePackage || ''
    applyTheme(next)
    MessagePlugin.success('界面风格已更新')
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '界面风格保存失败，请稍后重试。')
  } finally {
    savingTheme.value = false
  }
}

async function resetTheme() {
  savingTheme.value = true
  try {
    const next = await resetCurrentTheme()
    Object.assign(themeSettings, {
      themeKey: next.themeKey,
      darkMode: next.darkMode,
      compactMode: next.compactMode,
      applyScope: next.applyScope,
      brandColor: next.brandColor || '#4787F0',
      themePackage: next.themePackage || '',
      sidebarLogoVariant: next.sidebarLogoVariant || 'color',
    })
    themePackageInput.value = next.themePackage || ''
    applyTheme(next)
    MessagePlugin.success('已恢复默认界面风格')
  } catch {
    MessagePlugin.error('恢复失败，请稍后重试。')
  } finally {
    savingTheme.value = false
  }
}

async function applyThemePackage() {
  if (themePackageError.value) {
    MessagePlugin.warning(themePackageError.value)
    return
  }
  const nextPackage = normalizeArcoThemePackage(themePackageInput.value)
  if (!nextPackage) {
    MessagePlugin.warning('请输入主题商店样式名称')
    return
  }
  savingTheme.value = true
  try {
    await loadArcoThemePackage(nextPackage)
    const next = await updateCurrentTheme({
      ...themeSettings,
      brandColor: normalizedBrandColor.value,
      themePackage: nextPackage,
    })
    Object.assign(themeSettings, {
      themeKey: next.themeKey,
      darkMode: next.darkMode,
      compactMode: next.compactMode,
      applyScope: next.applyScope,
      brandColor: next.brandColor || normalizedBrandColor.value,
      themePackage: next.themePackage || nextPackage,
      sidebarLogoVariant: next.sidebarLogoVariant || themeSettings.sidebarLogoVariant || 'color',
    })
    themePackageInput.value = next.themePackage || nextPackage
    pendingThemePackage.value = next.themePackage || nextPackage
    pendingThemeBrandColor.value = getThemePackageBrandColor()
    brandFollowDecisionHandled.value = false
    brandFollowDialogVisible.value = true
    MessagePlugin.success('界面样式已应用')
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '界面样式应用失败，请检查名称是否正确后重试。')
  } finally {
    savingTheme.value = false
  }
}

function refreshToHome() {
  window.setTimeout(() => {
    router.replace('/')
    window.location.reload()
  }, 500)
}

function handleBrandFollowDialogVisible(value: boolean) {
  brandFollowDialogVisible.value = value
  if (!value && pendingThemePackage.value && !brandFollowDecisionHandled.value) {
    brandFollowDecisionHandled.value = true
    MessagePlugin.success('已保留当前品牌色，即将返回首页')
    refreshToHome()
  }
}

async function confirmFollowThemeBrandColor() {
  if (!pendingThemePackage.value) return
  brandFollowDecisionHandled.value = true
  savingTheme.value = true
  try {
    const next = await updateCurrentTheme({
      ...themeSettings,
      brandColor: pendingThemeBrandColor.value,
      themePackage: pendingThemePackage.value,
    })
    Object.assign(themeSettings, {
      themeKey: next.themeKey,
      darkMode: next.darkMode,
      compactMode: next.compactMode,
      applyScope: next.applyScope,
      brandColor: next.brandColor || pendingThemeBrandColor.value,
      themePackage: next.themePackage || pendingThemePackage.value,
      sidebarLogoVariant: next.sidebarLogoVariant || themeSettings.sidebarLogoVariant || 'color',
    })
    applyTheme(next)
    brandFollowDialogVisible.value = false
    MessagePlugin.success('品牌色已同步，即将返回首页')
    refreshToHome()
  } catch (err) {
    brandFollowDecisionHandled.value = false
    MessagePlugin.error(err instanceof Error ? err.message : '品牌色同步失败，请稍后重试。')
  } finally {
    savingTheme.value = false
  }
}

async function clearThemePackage() {
  savingTheme.value = true
  try {
    const next = await updateCurrentTheme({
      ...themeSettings,
      brandColor: normalizedBrandColor.value,
      themePackage: '',
    })
    Object.assign(themeSettings, {
      themeKey: next.themeKey,
      darkMode: next.darkMode,
      compactMode: next.compactMode,
      applyScope: next.applyScope,
      brandColor: next.brandColor || normalizedBrandColor.value,
      themePackage: '',
      sidebarLogoVariant: next.sidebarLogoVariant || themeSettings.sidebarLogoVariant || 'color',
    })
    themePackageInput.value = ''
    applyTheme(next)
    MessagePlugin.success('已恢复内置界面样式')
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '恢复失败，请稍后重试。')
  } finally {
    savingTheme.value = false
  }
}

async function saveRegistration() {
  savingReg.value = true
  try {
    await setSystemSetting('registration_open', { ...regSettings }, authStore.username)
    MessagePlugin.success('账号开通设置已保存')
  } catch { MessagePlugin.error('保存失败，请稍后重试。') }
  finally { savingReg.value = false }
}

async function saveLoginRules() {
  savingLogin.value = true
  try {
    await setSystemSetting('login_rules', { ...loginRulesSettings }, authStore.username)
    MessagePlugin.success('登录安全设置已保存')
  } catch { MessagePlugin.error('保存失败，请稍后重试。') }
  finally { savingLogin.value = false }
}
</script>

<style scoped>
.admin-settings {
  max-width: 1120px;
  min-width: 0;
}
.page-header { margin-bottom: var(--space-8); }
.page-title { font-size: var(--text-2xl); font-weight: 700; color: var(--text-primary); margin: 0 0 var(--space-1); }
.page-desc { font-size: var(--text-sm); color: var(--text-secondary); margin: 0; }
.settings-card { margin-bottom: var(--space-5); }
.settings-form { padding-top: var(--space-2); }
.switch-text { margin-left: var(--space-3); font-size: var(--text-sm); color: var(--text-secondary); }
.theme-current {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4);
  margin-bottom: var(--space-4);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
}
.brand-color-panel,
.logo-color-panel,
.theme-package-panel {
  display: grid;
  grid-template-columns: minmax(220px, .75fr) minmax(360px, 1.25fr);
  gap: var(--space-4);
  align-items: center;
  padding: var(--space-4);
  margin-bottom: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
}
.brand-color-panel strong,
.logo-color-panel strong,
.theme-package-panel strong {
  display: block;
  margin: 2px 0;
  color: var(--text-primary);
  font-size: var(--text-lg);
}
.brand-color-panel em,
.logo-color-panel em,
.theme-package-panel em {
  display: block;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
}
.brand-color-controls {
  display: grid;
  grid-template-columns: 44px minmax(150px, 1fr) auto;
  gap: var(--space-2);
  align-items: center;
}
.brand-color-picker {
  width: 44px;
  height: 34px;
  padding: 2px;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
  cursor: pointer;
}
.brand-color-input {
  min-height: 34px;
  padding: 6px 10px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font: inherit;
  outline: none;
}
.brand-color-input:focus {
  border-color: var(--color-brand-500);
  box-shadow: 0 0 0 2px var(--color-brand-50);
}
.brand-color-error {
  grid-column: 2 / -1;
  color: var(--color-danger);
  font-size: var(--text-xs);
}
.logo-color-switch {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  align-self: center;
  background: var(--border-color);
  border: 1px solid var(--border-color);
}
.logo-color-switch button {
  min-height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  border: 0;
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  font: inherit;
  font-size: var(--text-sm);
}
.logo-color-switch button:hover,
.logo-color-switch button.active {
  color: var(--color-brand-ink);
  background: var(--bg-active);
}
.logo-sample {
  width: 28px;
  height: 18px;
  display: inline-block;
  border: 1px solid var(--border-color);
  background: linear-gradient(135deg, #0E42D2 0 45%, #77B82A 45% 72%, #14C9C9 72%);
}
.logo-sample--white {
  background: #FFFFFF;
}
.logo-sample--black {
  background: #111827;
}
.theme-package-controls {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto auto;
  gap: var(--space-2);
  align-items: center;
}
.theme-package-input {
  min-height: 34px;
  padding: 6px 10px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  color: var(--text-primary);
  font: inherit;
  outline: none;
}
.theme-package-input:focus {
  border-color: var(--color-brand-500);
  box-shadow: 0 0 0 2px var(--color-brand-50);
}
.theme-package-error {
  grid-column: 1 / -1;
  color: var(--color-danger);
  font-size: var(--text-xs);
}
.field-label,
.theme-meta,
.theme-package {
  display: block;
  font-size: var(--text-xs);
  color: var(--text-secondary);
}
.theme-current strong {
  display: block;
  margin: 2px 0;
  font-size: var(--text-lg);
  color: var(--text-primary);
}
.theme-current em {
  font-style: normal;
  color: var(--text-tertiary);
  font-size: var(--text-xs);
}
.theme-toggles {
  display: flex;
  gap: var(--space-4);
}
.theme-toggles label {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-secondary);
  font-size: var(--text-sm);
}
.theme-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}
.theme-option {
  display: grid;
  gap: var(--space-2);
  min-height: 122px;
  padding: var(--space-4);
  text-align: left;
  cursor: pointer;
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
}
.theme-option:hover {
  border-color: var(--color-brand-500);
}
.theme-option--active {
  border-color: var(--color-brand-500);
  background: var(--bg-active);
}
.theme-option--disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.theme-swatch-row {
  display: flex;
  gap: 6px;
}
.theme-swatch-row i {
  width: 24px;
  height: 24px;
  border: 1px solid rgba(0, 0, 0, 0.08);
}
.theme-name {
  font-weight: 700;
  color: var(--text-primary);
}
.theme-scope-panel {
  display: grid;
  grid-template-columns: minmax(220px, .75fr) minmax(320px, 1.25fr);
  gap: var(--space-4);
  margin-top: var(--space-4);
  padding: var(--space-4);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
}
.theme-scope-panel strong {
  display: block;
  margin: 2px 0;
  color: var(--text-primary);
  font-size: var(--text-lg);
}
.theme-scope-panel em {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
}
.scope-switch {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px;
  align-self: center;
  background: var(--border-color);
  border: 1px solid var(--border-color);
}
.scope-switch button {
  min-height: 36px;
  border: 0;
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  font: inherit;
  font-size: var(--text-xs);
}
.scope-switch button.active {
  background: var(--color-brand-500);
  color: var(--text-on-brand);
}
.theme-preview-board {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(320px, .9fr);
  gap: var(--space-4);
  margin-top: var(--space-4);
}
.theme-preview-card {
  min-width: 0;
  min-height: 286px;
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
}
.preview-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.preview-head span,
.preview-note {
  color: var(--text-secondary);
  font-size: var(--text-xs);
}
.preview-head strong {
  color: var(--text-primary);
  font-size: var(--text-sm);
}
.preview-shell {
  min-width: 0;
  display: grid;
  grid-template-columns: 128px minmax(0, 1fr);
  min-height: 150px;
  overflow: hidden;
  background: var(--preview-bg);
  border: 1px solid var(--preview-border);
  color: var(--preview-text);
}
.preview-sidebar {
  display: grid;
  align-content: start;
  gap: var(--space-3);
  padding: var(--space-3);
  background: linear-gradient(180deg, color-mix(in srgb, var(--preview-brand), #0b1220 68%), #0b1220);
  color: var(--text-on-brand);
}
.preview-sidebar i {
  width: 28px;
  height: 18px;
  background: linear-gradient(90deg, var(--preview-green), var(--preview-cyan));
}
.preview-sidebar span {
  font-size: var(--text-xs);
  font-weight: 700;
}
.preview-main {
  min-width: 0;
  display: grid;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--preview-surface);
}
.preview-toolbar {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
}
.preview-toolbar span,
.preview-toolbar em {
  height: 10px;
  background: var(--preview-border);
}
.preview-toolbar span { width: 42%; }
.preview-toolbar em { width: 22%; }
.preview-kpis {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-2);
}
.preview-kpis b {
  min-height: 46px;
  display: grid;
  place-items: center;
  color: var(--preview-text);
  background: color-mix(in srgb, var(--preview-brand), transparent 88%);
  border: 1px solid var(--preview-border);
}
.preview-list {
  display: grid;
  gap: var(--space-2);
}
.preview-list span {
  height: 10px;
  background: linear-gradient(90deg, var(--preview-cyan), transparent);
}
.theme-facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2);
  margin-top: var(--space-3);
}
.theme-facts span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}
.chart-preview {
  min-width: 0;
  height: 190px;
  overflow: hidden;
}
.chart-preview :deep(.vchart-panel) {
  min-height: 190px;
}
.preview-note {
  margin: var(--space-3) 0 0;
  line-height: 1.6;
}
.brand-follow-dialog {
  display: grid;
  gap: var(--space-3);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  line-height: 1.6;
}
.brand-follow-dialog p {
  margin: 0;
  color: var(--text-primary);
}
.brand-follow-dialog em {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
}
.brand-follow-preview {
  display: inline-flex;
  width: fit-content;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
}
.brand-follow-preview i {
  width: 22px;
  height: 22px;
  border: 1px solid rgba(0, 0, 0, .08);
}
.brand-follow-preview span {
  color: var(--text-primary);
  font-weight: 700;
}
@media (max-width: 860px) {
  .theme-grid { grid-template-columns: 1fr; }
  .theme-current { align-items: flex-start; flex-direction: column; }
  .brand-color-panel,
  .logo-color-panel,
  .theme-package-panel,
  .theme-scope-panel,
  .theme-preview-board { grid-template-columns: 1fr; }
  .brand-color-controls { grid-template-columns: 44px minmax(0, 1fr); }
  .brand-color-controls :deep(.arco-btn) { grid-column: 1 / -1; }
  .theme-package-controls { grid-template-columns: 1fr; }
  .logo-color-switch { grid-template-columns: 1fr; }
  .scope-switch { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .preview-shell { grid-template-columns: 76px minmax(0, 1fr); }
  .theme-preview-card { padding: var(--space-3); }
  .theme-facts { grid-template-columns: 1fr; }
}
</style>

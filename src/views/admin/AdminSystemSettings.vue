<template>
  <div class="admin-settings">
    <div class="page-header">
      <h2 class="page-title">系统设置</h2>
      <p class="page-desc">管理系统全局参数，包括注册开关、登录规则等</p>
    </div>

    <t-card class="settings-card theme-card" title="主题外观" :bordered="true">
      <template #actions>
        <t-button size="small" variant="outline" :loading="savingTheme" @click="resetTheme">恢复默认</t-button>
      </template>
      <div class="theme-current">
        <div>
          <span class="field-label">当前主题</span>
          <strong>{{ currentThemeName }}</strong>
          <em>{{ themeSettings.themeKey }}</em>
        </div>
        <div class="theme-toggles">
          <label>
            <t-switch v-model="themeSettings.compactMode" size="small" @change="saveTheme" />
            <span>紧凑</span>
          </label>
          <label>
            <t-switch v-model="themeSettings.darkMode" size="small" @change="saveTheme" />
            <span>深色</span>
          </label>
        </div>
      </div>
      <div class="brand-color-panel">
        <div>
          <span class="field-label">品牌主色</span>
          <strong>{{ normalizedBrandColor }}</strong>
          <em>输入 6 位 HEX 色号，保存后侧栏、按钮、激活态和主题预览会全局更新。</em>
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
      <div class="theme-package-panel">
        <div>
          <span class="field-label">Arco 主题字符</span>
          <strong>{{ themePackageInput || '未设置主题包' }}</strong>
          <em>从 Arco Design 主题商店复制类似 @arco-design/theme-christmas 的字符，加载成功后会自动刷新并返回首页。</em>
        </div>
        <div class="theme-package-controls">
          <input
            v-model.trim="themePackageInput"
            class="theme-package-input"
            placeholder="@arco-design/theme-christmas"
            :disabled="savingTheme"
            @keyup.enter="applyThemePackage"
          />
          <t-button size="small" theme="primary" :loading="savingTheme" @click="applyThemePackage">切换主题包</t-button>
          <t-button size="small" variant="outline" :disabled="savingTheme || !themeSettings.themePackage" @click="clearThemePackage">清除主题包</t-button>
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
          <span class="theme-name">{{ theme.themeName }}</span>
          <span class="theme-package">{{ theme.packageName }}</span>
          <span class="theme-meta">{{ theme.isDefault ? '默认主题' : theme.isEnabled ? '可切换' : '未启用' }}</span>
        </button>
      </div>

      <div class="theme-scope-panel">
        <div>
          <span class="field-label">应用范围</span>
          <strong>{{ applyScopeLabel }}</strong>
          <em>当前版本按配置落库，后续模块可按范围读取主题策略。</em>
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
            <span>当前主题预览</span>
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
            <span>主题 key：{{ activeTheme?.themeKey || themeSettings.themeKey }}</span>
            <span>包标识：{{ activeTheme?.packageName || '-' }}</span>
            <span>启用状态：{{ activeTheme?.isEnabled ? '已启用' : '未启用' }}</span>
            <span>默认主题：{{ activeTheme?.isDefault ? '是' : '否' }}</span>
          </div>
        </section>

        <section class="theme-preview-card">
          <div class="preview-head">
            <span>图表主题预览</span>
            <strong>VChart + Arco Theme</strong>
          </div>
          <div class="chart-preview">
            <VChartPanel :spec="chartPreviewSpec" />
          </div>
          <p class="preview-note">图表颜色来自当前白名单主题色板，并通过 VChart Arco 主题适配器保持基础风格一致。</p>
        </section>
      </div>
    </t-card>

    <!-- 注册设置卡片 -->
    <t-card class="settings-card" title="注册设置" :bordered="true">
      <template #actions>
        <t-button size="small" variant="outline" :loading="savingReg" @click="saveRegistration">保存</t-button>
      </template>
      <t-form label-align="left" label-width="140px" class="settings-form">
        <t-form-item label="开放注册" help="关闭后，前端注册入口将禁用，仅管理员可创建用户">
          <t-switch v-model="regSettings.enabled" size="large" />
          <span class="switch-text">{{ regSettings.enabled ? '已开放' : '已关闭' }}</span>
        </t-form-item>
        <t-form-item label="注册需审批" help="开启后，新注册用户需管理员审批才能登录">
          <t-switch v-model="regSettings.requireApproval" size="large" />
          <span class="switch-text">{{ regSettings.requireApproval ? '需要审批' : '无需审批' }}</span>
        </t-form-item>
      </t-form>
    </t-card>

    <!-- 登录规则卡片 -->
    <t-card class="settings-card" title="登录规则" :bordered="true">
      <template #actions>
        <t-button size="small" variant="outline" :loading="savingLogin" @click="saveLoginRules">保存</t-button>
      </template>
      <t-form label-align="left" label-width="160px" class="settings-form">
        <t-form-item label="密码最小长度" help="用户密码的最小字符数（6-32）">
          <t-input-number v-model="loginRulesSettings.minPasswordLength" :min="1" :max="32" style="width:180px" />
        </t-form-item>
        <t-form-item label="最大登录尝试次数" help="超过此次数将临时锁定账户">
          <t-input-number v-model="loginRulesSettings.maxLoginAttempts" :min="1" :max="20" style="width:180px" />
        </t-form-item>
        <t-form-item label="会话超时（分钟）" help="登录会话无操作超时时间">
          <t-input-number v-model="loginRulesSettings.sessionTimeoutMinutes" :min="15" :max="1440" style="width:180px" />
          <span class="switch-text">分钟</span>
        </t-form-item>
        <t-form-item label="允许多端登录" help="关闭后，新登录会踢掉旧会话">
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

const authStore = useAuthStore()
const router = useRouter()
const savingReg = ref(false)
const savingLogin = ref(false)
const savingTheme = ref(false)
const themeOptions = ref<ThemeOption[]>([])
const themePackageInput = ref('')

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
})

const applyScopeOptions = [
  { label: '全局', value: 'global' },
  { label: '首页数据看板', value: 'dashboard' },
  { label: '审计看板', value: 'audit' },
  { label: '后台管理', value: 'admin' },
]

const currentThemeName = computed(() => {
  return themeOptions.value.find((item) => item.themeKey === themeSettings.themeKey)?.themeName || 'Arco 官方默认主题'
})

const activeTheme = computed(() => themeOptions.value.find((item) => item.themeKey === themeSettings.themeKey) || null)

function normalizeHexColor(value?: string) {
  const raw = String(value || '').trim()
  const match = raw.match(/^#?([0-9a-fA-F]{6})$/)
  return match ? `#${match[1].toUpperCase()}` : ''
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
  return normalizeArcoThemePackage(themePackageInput.value) ? '' : '请输入例如 @arco-design/theme-christmas 的主题字符'
})

const activePreviewColors = computed(() => {
  const colors = activeTheme.value?.previewColors || []
  const palette = colors.length ? colors : ['#165DFF', '#14C9C9', '#00B42A', '#FF7D00']
  return [normalizedBrandColor.value, ...palette.slice(1)]
})

const applyScopeLabel = computed(() => {
  return applyScopeOptions.find((item) => item.value === themeSettings.applyScope)?.label || '全局'
})

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
    })
    themePackageInput.value = next.themePackage || ''
    applyTheme(next)
    MessagePlugin.success('主题已切换')
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '主题保存失败')
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
    })
    themePackageInput.value = next.themePackage || ''
    applyTheme(next)
    MessagePlugin.success('已恢复默认主题')
  } catch {
    MessagePlugin.error('恢复失败')
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
    MessagePlugin.warning('请输入主题字符')
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
    })
    MessagePlugin.success('主题包切换成功，即将返回首页')
    window.setTimeout(() => {
      router.replace('/')
      window.location.reload()
    }, 700)
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '主题包切换失败')
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
    })
    themePackageInput.value = ''
    applyTheme(next)
    MessagePlugin.success('主题包已清除')
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '清除失败')
  } finally {
    savingTheme.value = false
  }
}

async function saveRegistration() {
  savingReg.value = true
  try {
    await setSystemSetting('registration_open', { ...regSettings }, authStore.username)
    MessagePlugin.success('注册设置已保存')
  } catch { MessagePlugin.error('保存失败') }
  finally { savingReg.value = false }
}

async function saveLoginRules() {
  savingLogin.value = true
  try {
    await setSystemSetting('login_rules', { ...loginRulesSettings }, authStore.username)
    MessagePlugin.success('登录规则已保存')
  } catch { MessagePlugin.error('保存失败') }
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
.theme-package-panel strong {
  display: block;
  margin: 2px 0;
  color: var(--text-primary);
  font-size: var(--text-lg);
}
.brand-color-panel em,
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
  color: #fff;
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
  color: #fff;
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
@media (max-width: 860px) {
  .theme-grid { grid-template-columns: 1fr; }
  .theme-current { align-items: flex-start; flex-direction: column; }
  .brand-color-panel,
  .theme-package-panel,
  .theme-scope-panel,
  .theme-preview-board { grid-template-columns: 1fr; }
  .brand-color-controls { grid-template-columns: 44px minmax(0, 1fr); }
  .brand-color-controls :deep(.arco-btn) { grid-column: 1 / -1; }
  .theme-package-controls { grid-template-columns: 1fr; }
  .scope-switch { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .preview-shell { grid-template-columns: 76px minmax(0, 1fr); }
  .theme-preview-card { padding: var(--space-3); }
  .theme-facts { grid-template-columns: 1fr; }
}
</style>

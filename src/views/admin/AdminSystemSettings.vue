<template>
  <div class="admin-settings">
    <div class="page-header">
      <h2 class="page-title">系统设置</h2>
      <p class="page-desc">管理系统全局参数，包括注册开关、登录规则等</p>
    </div>

    <t-card class="settings-card" title="主题外观" :bordered="true">
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
import {
  getCurrentTheme,
  getSystemSetting,
  getThemeOptions,
  resetCurrentTheme,
  setSystemSetting,
  updateCurrentTheme,
} from '@/api/system'
import { useAuthStore } from '@/store/auth'
import { MessagePlugin } from '@/ui/message'
import { applyTheme } from '@/ui/theme'
import type { RegistrationSetting, LoginRulesSetting, ThemeOption, ThemeSetting } from '@/types'

const authStore = useAuthStore()
const savingReg = ref(false)
const savingLogin = ref(false)
const savingTheme = ref(false)
const themeOptions = ref<ThemeOption[]>([])

const regSettings = reactive<RegistrationSetting>({ enabled: false, requireApproval: true })
const loginRulesSettings = reactive<LoginRulesSetting>({
  minPasswordLength: 1, maxLoginAttempts: 5, sessionTimeoutMinutes: 480, allowConcurrentSessions: true,
})
const themeSettings = reactive<ThemeSetting>({
  themeKey: 'arco-theme-0000',
  darkMode: false,
  compactMode: false,
  applyScope: 'global',
})

const currentThemeName = computed(() => {
  return themeOptions.value.find((item) => item.themeKey === themeSettings.themeKey)?.themeName || 'Arco 官方默认主题'
})

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
    })
    applyTheme(currentTheme)
  } catch { /* 默认值 */ }
})

async function selectTheme(theme: ThemeOption) {
  if (!theme.isEnabled || theme.themeKey === themeSettings.themeKey) return
  themeSettings.themeKey = theme.themeKey
  await saveTheme()
}

async function saveTheme() {
  savingTheme.value = true
  try {
    const next = await updateCurrentTheme({ ...themeSettings })
    Object.assign(themeSettings, {
      themeKey: next.themeKey,
      darkMode: next.darkMode,
      compactMode: next.compactMode,
      applyScope: next.applyScope,
    })
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
    })
    applyTheme(next)
    MessagePlugin.success('已恢复默认主题')
  } catch {
    MessagePlugin.error('恢复失败')
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
.admin-settings { max-width: 980px; }
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
@media (max-width: 860px) {
  .theme-grid { grid-template-columns: 1fr; }
  .theme-current { align-items: flex-start; flex-direction: column; }
}
</style>

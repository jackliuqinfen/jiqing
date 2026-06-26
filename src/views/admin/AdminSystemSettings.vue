<template>
  <div class="admin-settings">
    <div class="page-header">
      <h2 class="page-title">系统设置</h2>
      <p class="page-desc">管理系统全局参数，包括注册开关、登录规则等</p>
    </div>

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
import { ref, reactive, onMounted } from 'vue'
import { getSystemSetting, setSystemSetting } from '@/api/system'
import { useAuthStore } from '@/store/auth'
import { MessagePlugin } from 'tdesign-vue-next'
import type { RegistrationSetting, LoginRulesSetting } from '@/types'

const authStore = useAuthStore()
const savingReg = ref(false)
const savingLogin = ref(false)

const regSettings = reactive<RegistrationSetting>({ enabled: false, requireApproval: true })
const loginRulesSettings = reactive<LoginRulesSetting>({
  minPasswordLength: 1, maxLoginAttempts: 5, sessionTimeoutMinutes: 480, allowConcurrentSessions: true,
})

onMounted(async () => {
  try {
    const [reg, login] = await Promise.all([getSystemSetting('registration_open'), getSystemSetting('login_rules')])
    if (reg) Object.assign(regSettings, reg.value as RegistrationSetting)
    if (login) Object.assign(loginRulesSettings, login.value as LoginRulesSetting)
  } catch { /* 默认值 */ }
})

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
.admin-settings { max-width: 720px; }
.page-header { margin-bottom: var(--space-8); }
.page-title { font-size: var(--text-2xl); font-weight: 700; color: var(--text-primary); margin: 0 0 var(--space-1); }
.page-desc { font-size: var(--text-sm); color: var(--text-secondary); margin: 0; }
.settings-card { margin-bottom: var(--space-5); }
.settings-form { padding-top: var(--space-2); }
.switch-text { margin-left: var(--space-3); font-size: var(--text-sm); color: var(--text-secondary); }
</style>

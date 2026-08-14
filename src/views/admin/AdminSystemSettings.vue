<template>
  <div class="admin-settings">
    <PageHeader title="系统设置" description="管理登录、账号开通和界面风格等常用设置">
      <template #meta>
        <ATag variant="light" theme="primary">常用设置</ATag>
        <ATag variant="light">界面 / 账号 / 登录 / 上传</ATag>
      </template>
    </PageHeader>

    <ACard class="settings-card theme-card" title="界面风格" :bordered="true">
      <template #actions>
        <AButton size="small" variant="outline" :loading="savingTheme" @click="resetTheme">恢复默认</AButton>
      </template>
      <div class="theme-current">
        <div>
          <span class="field-label">当前风格</span>
          <strong>{{ currentThemeName }}</strong>
          <em>{{ themeSettings.darkMode ? '深色显示' : '浅色显示' }} · {{ themeSettings.compactMode ? '紧凑间距' : '标准间距' }}</em>
        </div>
        <div class="theme-toggles">
          <label>
            <ASwitch v-model="themeSettings.compactMode" size="small" @change="saveTheme" />
            <span>紧凑显示</span>
          </label>
          <label>
            <ASwitch v-model="themeSettings.darkMode" size="small" @change="saveTheme" />
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
          <AInput
            v-model.trim="themeSettings.brandColor"
            class="brand-color-input"
            placeholder="#165DFF"
            :disabled="savingTheme"
            @keyup.enter="saveTheme"
          />
          <AButton size="small" theme="primary" :loading="savingTheme" @click="saveTheme">应用品牌色</AButton>
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
      <div class="workspace-background-panel">
        <div>
          <span class="field-label">工作台背景</span>
          <strong>{{ hasCustomWorkspaceBackground ? '自定义背景' : '系统默认背景' }}</strong>
          <em>仅影响登录后的工程管理工作台。支持 PNG、JPG、WebP，图片不能超过 2 MB。</em>
        </div>
        <div class="workspace-background-editor">
          <div
            class="workspace-background-preview"
            :style="workspaceBackgroundPreviewStyle"
            role="img"
            aria-label="当前工作台背景预览"
          >
            <span>{{ hasCustomWorkspaceBackground ? '自定义' : '默认' }}</span>
          </div>
          <div class="workspace-background-actions">
            <input
              ref="workspaceBackgroundInput"
              class="workspace-background-input"
              type="file"
              accept="image/png,image/jpeg,image/webp"
              :disabled="savingTheme"
              @change="handleWorkspaceBackgroundFile"
            />
            <AButton size="small" theme="primary" :loading="savingTheme" @click="chooseWorkspaceBackground">更换背景</AButton>
            <AButton
              size="small"
              variant="outline"
              :disabled="savingTheme || !hasCustomWorkspaceBackground"
              @click="restoreDefaultWorkspaceBackground"
            >
              恢复默认背景
            </AButton>
          </div>
        </div>
      </div>
      <div class="theme-package-panel">
        <div>
          <span class="field-label">主题商店样式</span>
          <strong>{{ themePackageInput ? '已填写样式名称' : '未使用外部样式' }}</strong>
          <em>需要使用主题商店样式时，粘贴完整样式名称。应用成功后会询问是否同步推荐品牌色，并返回首页查看效果。</em>
        </div>
        <div class="theme-package-controls">
          <AInput
            v-model.trim="themePackageInput"
            class="theme-package-input"
            placeholder="请输入主题商店样式名称"
            :disabled="savingTheme"
            @keyup.enter="applyThemePackage"
          />
          <AButton size="small" theme="primary" :loading="savingTheme" @click="applyThemePackage">应用样式</AButton>
          <AButton size="small" variant="outline" :disabled="savingTheme || !themeSettings.themePackage" @click="clearThemePackage">恢复内置样式</AButton>
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
    </ACard>

    <AModal
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
    </AModal>

    <!-- 注册设置卡片 -->
    <ACard class="settings-card" title="账号开通" :bordered="true">
      <template #actions>
        <AButton size="small" variant="outline" :loading="savingReg" @click="saveRegistration">保存</AButton>
      </template>
      <AForm :model="regSettings" label-align="left" label-width="140px" class="settings-form">
        <AFormItem label="允许自行申请账号" help="关闭后，新账号由管理员统一开通">
          <ASwitch v-model="regSettings.enabled" size="medium" />
          <span class="switch-text">{{ regSettings.enabled ? '已开放' : '已关闭' }}</span>
        </AFormItem>
        <AFormItem label="申请后需要审核" help="开启后，新账号审核通过后才能登录">
          <ASwitch v-model="regSettings.requireApproval" size="medium" />
          <span class="switch-text">{{ regSettings.requireApproval ? '需要审批' : '无需审批' }}</span>
        </AFormItem>
      </AForm>
    </ACard>

    <!-- 登录规则卡片 -->
    <ACard class="settings-card" title="登录安全" :bordered="true">
      <template #actions>
        <AButton size="small" variant="outline" :loading="savingLogin" @click="saveLoginRules">保存</AButton>
      </template>
      <AForm :model="loginRulesSettings" label-align="left" label-width="160px" class="settings-form">
        <AFormItem label="密码最少位数" help="建议不少于 6 位，降低账号被误用的风险">
          <AInputNumber v-model="loginRulesSettings.minPasswordLength" :min="1" :max="32" style="width:180px" />
        </AFormItem>
        <AFormItem label="最多输错次数" help="连续输错超过该次数后，账号会暂时保护">
          <AInputNumber v-model="loginRulesSettings.maxLoginAttempts" :min="1" :max="20" style="width:180px" />
        </AFormItem>
        <AFormItem label="自动退出时间" help="长时间未操作时，系统会自动退出登录">
          <AInputNumber v-model="loginRulesSettings.sessionTimeoutMinutes" :min="15" :max="1440" style="width:180px" />
          <span class="switch-text">分钟</span>
        </AFormItem>
        <AFormItem label="允许多处登录" help="关闭后，同一账号新登录时，原位置会自动退出">
          <ASwitch v-model="loginRulesSettings.allowConcurrentSessions" size="medium" />
          <span class="switch-text">{{ loginRulesSettings.allowConcurrentSessions ? '允许' : '不允许' }}</span>
        </AFormItem>
      </AForm>
    </ACard>

    <ACard class="settings-card" title="文件上传" :bordered="true">
      <template #actions>
        <AButton size="small" variant="outline" :loading="savingUpload" @click="saveUploadSettings">保存</AButton>
      </template>
      <AForm :model="uploadSettings" label-align="left" label-width="160px" class="settings-form">
        <AFormItem
          label="单文件最大大小"
          help="限制每次上传的单个资料文件大小，影响项目资料、资料中心和审计相关附件。"
        >
          <AInputNumber
            v-model="uploadSettings.maxFileSizeMb"
            :min="1"
            :max="500"
            style="width:180px"
          />
          <span class="switch-text">MB</span>
        </AFormItem>
      </AForm>
      <p class="settings-note">
        建议日常资料控制在 100MB 以内。超过该限制时，系统会提示员工压缩文件或联系管理员调整上限。
      </p>
    </ACard>

    <ACard class="settings-card desktop-sync-card" title="本地资料同步" :bordered="true">
      <template #actions>
        <AButton
          size="small"
          theme="primary"
          :loading="savingDesktopSync || desktopSyncPolicyLoading"
          :disabled="!desktopSyncPolicyLoaded || desktopSyncPolicyLoading"
          @click="saveDesktopSyncSettings"
        >
          保存同步策略
        </AButton>
      </template>

      <AAlert type="info" class="desktop-sync-intro">
        服务器到本地只读同步，本地新增或修改不会自动上传。
      </AAlert>

      <div v-if="desktopSyncPolicyLoadError" class="desktop-sync-load-error">
        <AAlert type="error">
          {{ desktopSyncPolicyLoadError }}
        </AAlert>
        <AButton size="small" :loading="desktopSyncPolicyLoading" @click="retryDesktopSyncPolicy">
          重新加载同步策略
        </AButton>
      </div>

      <AAlert v-if="desktopSyncValidationError" type="error" class="desktop-sync-validation-error">
        {{ desktopSyncValidationError }}
      </AAlert>

      <AForm :model="desktopSyncSettings" label-align="left" label-width="180px" class="settings-form desktop-sync-form">
        <AFormItem label="启用本地资料同步" help="总开关默认关闭。关闭后，所有客户端都不能获取同步清单或下载同步文件。">
          <ASwitch v-model="desktopSyncSettings.enabled" size="medium" />
          <span class="switch-text">{{ desktopSyncSettings.enabled ? '已启用' : '已关闭' }}</span>
        </AFormItem>

        <AFormItem label="客户端首次默认启用" help="仅控制已获授权用户首次使用客户端时的初始选择，不会绕过上方总开关或服务器权限。">
          <ASwitch v-model="desktopSyncSettings.enabledByDefault" size="medium" />
          <span class="switch-text">{{ desktopSyncSettings.enabledByDefault ? '默认勾选' : '默认不勾选' }}</span>
        </AFormItem>

        <AFormItem label="管理员权限" help="管理员默认具备同步资格；普通员工必须同时在下方点名，并使用管理员指定项目模式。">
          <ATag color="arcoblue">仅管理员角色自动授权</ATag>
        </AFormItem>

        <AFormItem label="单独允许的员工" help="点名员工不会自动获得全部项目，只能同步管理员在下方明确指定的项目。">
          <ASelect
            v-model="desktopSyncSettings.allowedUserIds"
            mode="multiple"
            allow-clear
            :loading="loadingDesktopUsers"
            :options="desktopUserSelectOptions"
            placeholder="选择允许同步的用户"
          />
          <p v-if="desktopUsersEmptyText" class="desktop-sync-empty">{{ desktopUsersEmptyText }}</p>
        </AFormItem>

        <AFormItem label="项目选择方式" help="管理员自由选择模式仅供管理员使用；普通员工必须采用管理员指定项目模式。">
          <div class="desktop-sync-segmented" role="group" aria-label="项目选择方式">
            <button
              v-for="mode in desktopProjectModeOptions"
              :key="mode.value"
              type="button"
              :class="{ active: desktopSyncSettings.projectSelectionMode === mode.value }"
              @click="desktopSyncSettings.projectSelectionMode = mode.value"
            >
              {{ mode.label }}
            </button>
          </div>
        </AFormItem>

        <AFormItem
          v-if="desktopSyncSettings.projectSelectionMode === 'admin_assigned'"
          label="管理员指定项目"
          help="优先读取桌面同步授权项目；策略尚未启用或接口不可用时，回退为当前管理员可见的真实项目。"
        >
          <ASelect
            v-model="desktopSyncSettings.allowedProjectRefs"
            mode="multiple"
            allow-clear
            :loading="loadingDesktopProjects"
            :options="desktopProjectSelectOptions"
            placeholder="选择允许同步的项目"
          />
          <p v-if="desktopProjectsEmptyText" class="desktop-sync-empty">{{ desktopProjectsEmptyText }}</p>
        </AFormItem>

        <AFormItem label="允许的资料分类" help="不选择时不额外限制分类；列表来自项目资料分类配置。">
          <ASelect
            v-model="desktopSyncSettings.allowedCategoryKeys"
            mode="multiple"
            allow-clear
            :loading="loadingDesktopCategories"
            :options="desktopCategorySelectOptions"
            placeholder="选择允许同步的资料分类"
          />
          <p v-if="desktopCategoriesEmptyText" class="desktop-sync-empty">{{ desktopCategoriesEmptyText }}</p>
        </AFormItem>

        <AFormItem
          label="允许的文件格式"
          help="至少保留 1 种，最多 30 种；每个扩展名不超过 16 个字符。保存时会转为小写并补全英文句点。"
        >
          <ASelect
            v-model="desktopSyncSettings.allowedExtensions"
            mode="multiple"
            allow-create
            :options="desktopExtensionOptions"
            placeholder="例如 .pdf、.docx"
          />
        </AFormItem>

        <div class="desktop-sync-number-grid">
          <AFormItem label="单文件上限">
            <AInputNumber v-model="desktopSyncSettings.maxFileSizeMb" :min="1" :max="500" />
            <span class="switch-text">MB</span>
          </AFormItem>
          <AFormItem label="本地空间上限">
            <AInputNumber v-model="desktopSyncSettings.maxLocalStorageGb" :min="1" :max="500" />
            <span class="switch-text">GB</span>
          </AFormItem>
          <AFormItem label="自动检查间隔">
            <AInputNumber v-model="desktopSyncSettings.pollIntervalSeconds" :min="60" :max="3600" />
            <span class="switch-text">秒</span>
          </AFormItem>
        </div>

        <AFormItem label="允许员工选择本地文件夹" help="开启后，客户端可由员工选择只读镜像的保存位置。">
          <ASwitch v-model="desktopSyncSettings.allowFolderSelection" size="medium" />
          <span class="switch-text">{{ desktopSyncSettings.allowFolderSelection ? '允许选择' : '使用客户端默认位置' }}</span>
        </AFormItem>

        <AAlert type="info" class="desktop-sync-warning">
          权限撤销后客户端会立即停止后续同步，但已下载的本地副本不会被远程删除。请按公司资料管理制度处理离线副本。
        </AAlert>
      </AForm>
    </ACard>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import type { ISpec } from '@visactor/vchart/esm/core'
import {
  getCurrentTheme,
  getAdminUsers,
  getAuthToken,
  getSystemSetting,
  getThemeOptions,
  resetCurrentTheme,
  setSystemSetting,
  updateCurrentTheme,
} from '@/api/system'
import { fetchProjectMeta, fetchProjectRecords } from '@/api/projects'
import VChartPanel from '@/components/VChartPanel.vue'
import { useAuthStore } from '@/store/auth'
import { MessagePlugin } from '@/ui/message'
import {
  applyTheme,
  loadArcoThemePackage,
  normalizeArcoThemePackage,
  workspaceBackgroundCssValue,
} from '@/ui/theme'
import type {
  DesktopSyncPolicySetting,
  LoginRulesSetting,
  RegistrationSetting,
  ThemeOption,
  ThemeSetting,
  UploadSetting,
} from '@/types'
import PageHeader from '@/components/PageHeader.vue'

const authStore = useAuthStore()
const router = useRouter()
const savingReg = ref(false)
const savingLogin = ref(false)
const savingTheme = ref(false)
const savingUpload = ref(false)
const savingDesktopSync = ref(false)
const desktopSyncPolicyLoading = ref(false)
const desktopSyncPolicyLoaded = ref(false)
const desktopSyncPolicyLoadError = ref('')
const desktopSyncValidationError = ref('')
const loadingDesktopUsers = ref(false)
const loadingDesktopProjects = ref(false)
const loadingDesktopCategories = ref(false)
const desktopUsersLoadFailed = ref(false)
const desktopProjectsLoadFailed = ref(false)
const desktopCategoriesLoadFailed = ref(false)
const workspaceBackgroundInput = ref<HTMLInputElement | null>(null)
const themeOptions = ref<ThemeOption[]>([])
const themePackageInput = ref('')
const brandFollowDialogVisible = ref(false)
const pendingThemePackage = ref('')
const pendingThemeBrandColor = ref('#165DFF')
const brandFollowDecisionHandled = ref(false)

type SelectOption = { label: string; value: string }
type DesktopSyncProjectRoot = {
  projectRef: string
  projectName: string
  projectCode?: string
}

const DEFAULT_DESKTOP_EXTENSIONS = [
  '.pdf', '.doc', '.docx', '.xls', '.xlsx',
  '.jpg', '.jpeg', '.png', '.webp', '.txt',
]
const MAX_DESKTOP_EXTENSION_COUNT = 30
const MAX_DESKTOP_EXTENSION_LENGTH = 16
const desktopUserOptions = ref<SelectOption[]>([])
const desktopProjectOptions = ref<SelectOption[]>([])
const desktopCategoryOptions = ref<SelectOption[]>([])

const desktopProjectModeOptions: Array<{
  label: string
  value: DesktopSyncPolicySetting['projectSelectionMode']
}> = [
  { label: '员工选择授权项目', value: 'user_select' },
  { label: '管理员指定项目', value: 'admin_assigned' },
]
const desktopExtensionOptions = DEFAULT_DESKTOP_EXTENSIONS.map((value) => ({ label: value, value }))

const regSettings = reactive<RegistrationSetting>({ enabled: false, requireApproval: true })
const loginRulesSettings = reactive<LoginRulesSetting>({
  minPasswordLength: 1, maxLoginAttempts: 5, sessionTimeoutMinutes: 480, allowConcurrentSessions: true,
})
const uploadSettings = reactive<UploadSetting>({ maxFileSizeMb: 100 })
const desktopSyncSettings = reactive<DesktopSyncPolicySetting>({
  enabled: false,
  enabledByDefault: false,
  allowedRoles: ['admin'],
  allowedUserIds: [],
  projectSelectionMode: 'user_select',
  allowedProjectRefs: [],
  allowedCategoryKeys: [],
  allowedExtensions: [...DEFAULT_DESKTOP_EXTENSIONS],
  maxFileSizeMb: 100,
  maxLocalStorageGb: 10,
  pollIntervalSeconds: 300,
  allowFolderSelection: true,
  removeLocalFilesOnRevocation: false,
  policyVersion: 1,
})
const themeSettings = reactive<ThemeSetting>({
  themeKey: 'arco-theme-0000',
  darkMode: false,
  compactMode: false,
  applyScope: 'global',
  brandColor: '#165DFF',
  themePackage: '',
  sidebarLogoVariant: 'color',
  workspaceBackgroundImage: '',
})

const hasCustomWorkspaceBackground = computed(() => Boolean(themeSettings.workspaceBackgroundImage))
const workspaceBackgroundPreviewStyle = computed(() => ({
  backgroundImage: workspaceBackgroundCssValue(themeSettings.workspaceBackgroundImage),
}))

function withRetainedDesktopOptions(options: SelectOption[], values: string[]) {
  const retained = [...options]
  const knownValues = new Set(options.map((option) => option.value))
  for (const value of uniqueDesktopSyncStrings(values)) {
    if (knownValues.has(value)) continue
    retained.push({ label: `已保留配置：${value}`, value })
  }
  return retained
}

const desktopUserSelectOptions = computed(() => withRetainedDesktopOptions(
  desktopUserOptions.value,
  desktopSyncSettings.allowedUserIds,
))
const desktopProjectSelectOptions = computed(() => withRetainedDesktopOptions(
  desktopProjectOptions.value,
  desktopSyncSettings.allowedProjectRefs,
))
const desktopCategorySelectOptions = computed(() => withRetainedDesktopOptions(
  desktopCategoryOptions.value,
  desktopSyncSettings.allowedCategoryKeys,
))

const desktopUsersEmptyText = computed(() => {
  if (loadingDesktopUsers.value || desktopUserOptions.value.length) return ''
  return desktopUsersLoadFailed.value ? '用户列表暂时无法读取，请稍后重试。' : '用户管理中暂无可用账号。'
})
const desktopProjectsEmptyText = computed(() => {
  if (loadingDesktopProjects.value || desktopProjectOptions.value.length) return ''
  return desktopProjectsLoadFailed.value ? '项目列表暂时无法读取，请稍后重试。' : '当前没有可授权的真实项目。'
})
const desktopCategoriesEmptyText = computed(() => {
  if (loadingDesktopCategories.value || desktopCategoryOptions.value.length) return ''
  return desktopCategoriesLoadFailed.value ? '资料分类暂时无法读取，请稍后重试。' : '当前没有已启用的资料分类。'
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

const normalizedBrandColor = computed(() => normalizeHexColor(themeSettings.brandColor) || '#165DFF')

const brandColorError = computed(() => {
  return normalizeHexColor(themeSettings.brandColor) ? '' : '请输入例如 #165DFF 的 6 位色号'
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
  return theme.themeName.replace(/Arco|Theme|主题包|默认兼容/gi, '').trim() || '自定义风格'
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

function uniqueDesktopSyncStrings(value: unknown) {
  if (!Array.isArray(value)) return []
  const result: string[] = []
  for (const item of value) {
    if (typeof item !== 'string') continue
    const normalized = item.trim()
    if (normalized && !result.includes(normalized)) result.push(normalized)
  }
  return result
}

function trustedDesktopSyncBoolean(value: unknown, fallback: boolean) {
  return typeof value === 'boolean' ? value : fallback
}

function boundedDesktopSyncInteger(value: unknown, fallback: number, minimum: number, maximum: number) {
  if (typeof value === 'boolean' || value === null || value === '') return fallback
  let normalized: number
  if (typeof value === 'number') {
    normalized = Math.trunc(value)
  } else if (typeof value === 'string' && /^[+-]?\d+$/.test(value.trim())) {
    normalized = Number(value)
  } else {
    return fallback
  }
  if (!Number.isFinite(normalized)) return fallback
  return Math.max(minimum, Math.min(maximum, normalized))
}

function inspectDesktopSyncExtensions(value: unknown) {
  const result: string[] = []
  let hasInvalidValue = false
  for (const item of uniqueDesktopSyncStrings(value)) {
    const suffix = item.toLowerCase().startsWith('.') ? item.toLowerCase() : `.${item.toLowerCase()}`
    if (!/^\.[a-z0-9]+$/.test(suffix) || suffix.length > MAX_DESKTOP_EXTENSION_LENGTH) {
      hasInvalidValue = true
      continue
    }
    if (!result.includes(suffix)) result.push(suffix)
  }
  return {
    values: result,
    hasInvalidValue,
    exceedsCount: result.length > MAX_DESKTOP_EXTENSION_COUNT,
  }
}

function normalizeDesktopSyncExtensions(value: unknown) {
  const inspected = inspectDesktopSyncExtensions(value)
  const values = inspected.values.slice(0, MAX_DESKTOP_EXTENSION_COUNT)
  return values.length ? values : [...DEFAULT_DESKTOP_EXTENSIONS]
}

function desktopDisplayUnit(
  value: Record<string, unknown>,
  displayKey: string,
  byteKey: string,
  fallback: number,
  bytesPerUnit: number,
) {
  if (displayKey in value) {
    return boundedDesktopSyncInteger(value[displayKey], fallback, 1, 500)
  }
  if (byteKey in value) {
    const bytes = boundedDesktopSyncInteger(value[byteKey], fallback * bytesPerUnit, bytesPerUnit, 500 * bytesPerUnit)
    return Math.max(1, Math.min(500, Math.floor(bytes / bytesPerUnit)))
  }
  return fallback
}

function normalizeDesktopSyncPolicy(value: unknown): DesktopSyncPolicySetting {
  const raw = value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
  const projectSelectionMode = raw.projectSelectionMode === 'admin_assigned'
    ? 'admin_assigned'
    : 'user_select'
  return {
    enabled: trustedDesktopSyncBoolean(raw.enabled, false),
    enabledByDefault: trustedDesktopSyncBoolean(raw.enabledByDefault, false),
    allowedRoles: ['admin'],
    allowedUserIds: uniqueDesktopSyncStrings(raw.allowedUserIds),
    projectSelectionMode,
    allowedProjectRefs: uniqueDesktopSyncStrings(raw.allowedProjectRefs),
    allowedCategoryKeys: uniqueDesktopSyncStrings(raw.allowedCategoryKeys),
    allowedExtensions: normalizeDesktopSyncExtensions(raw.allowedExtensions),
    maxFileSizeMb: desktopDisplayUnit(raw, 'maxFileSizeMb', 'maxFileSizeBytes', 100, 1024 * 1024),
    maxLocalStorageGb: desktopDisplayUnit(raw, 'maxLocalStorageGb', 'maxLocalStorageBytes', 10, 1024 * 1024 * 1024),
    pollIntervalSeconds: boundedDesktopSyncInteger(raw.pollIntervalSeconds, 300, 60, 3600),
    allowFolderSelection: trustedDesktopSyncBoolean(raw.allowFolderSelection, true),
    removeLocalFilesOnRevocation: false,
    policyVersion: boundedDesktopSyncInteger(raw.policyVersion, 1, 1, 2 ** 31 - 1),
  }
}

function validateDesktopSyncSettings() {
  if (!desktopSyncPolicyLoaded.value) {
    return '同步策略尚未成功加载，请重新加载后再保存。'
  }
  const extensions = inspectDesktopSyncExtensions(desktopSyncSettings.allowedExtensions)
  if (extensions.hasInvalidValue) {
    return `文件扩展名只能包含英文和数字，且含句点总长度不能超过 ${MAX_DESKTOP_EXTENSION_LENGTH} 个字符。`
  }
  if (extensions.exceedsCount) {
    return `允许同步的文件格式最多为 ${MAX_DESKTOP_EXTENSION_COUNT} 种。`
  }
  if (!extensions.values.length) {
    return '请至少保留一种允许同步的文件格式。'
  }
  return ''
}

async function fetchDesktopSyncProjectRoots() {
  const apiBase = import.meta.env.VITE_AUDIT_API_BASE || '/api'
  const token = getAuthToken()
  const response = await fetch(`${apiBase}/desktop/sync/projects`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  const payload = await response.json() as {
    success: boolean
    data?: DesktopSyncProjectRoot[]
    error?: string
  }
  if (!response.ok || !payload.success || !Array.isArray(payload.data)) {
    throw new Error(payload.error || `请求失败: ${response.status}`)
  }
  return payload.data
}

async function fetchAllVisibleProjects() {
  const records: Awaited<ReturnType<typeof fetchProjectRecords>>['data'] = []
  const pageSize = 200
  let page = 1
  let total = 0
  do {
    const result = await fetchProjectRecords({ page, pageSize })
    records.push(...result.data)
    total = result.total
    if (!result.data.length) break
    page += 1
  } while (records.length < total)
  return records
}

async function loadDesktopSyncUsers() {
  loadingDesktopUsers.value = true
  desktopUsersLoadFailed.value = false
  try {
    const users = await getAdminUsers()
    desktopUserOptions.value = users
      .filter((user) => user.isActive)
      .map((user) => ({
        label: `${user.displayName || user.username}（${user.username}）`,
        value: user.id,
      }))
  } catch {
    desktopUsersLoadFailed.value = true
  } finally {
    loadingDesktopUsers.value = false
  }
}

async function loadDesktopSyncProjects() {
  loadingDesktopProjects.value = true
  desktopProjectsLoadFailed.value = false
  try {
    const roots = await fetchDesktopSyncProjectRoots()
    desktopProjectOptions.value = roots.map((item) => ({
      label: item.projectCode
        ? `${item.projectName}（${item.projectCode}）`
        : item.projectName,
      value: item.projectRef,
    }))
  } catch {
    try {
      const projects = await fetchAllVisibleProjects()
      desktopProjectOptions.value = projects.map((project) => ({
        label: project.projectCode
          ? `${project.projectName}（${project.projectCode}）`
          : project.projectName,
        value: `project:${project.id}`,
      }))
    } catch {
      desktopProjectsLoadFailed.value = true
    }
  } finally {
    loadingDesktopProjects.value = false
  }
}

async function loadDesktopSyncCategories() {
  loadingDesktopCategories.value = true
  desktopCategoriesLoadFailed.value = false
  try {
    const meta = await fetchProjectMeta()
    desktopCategoryOptions.value = meta.categories
      .filter((category) => category.enabled)
      .map((category) => ({ label: category.categoryName, value: category.categoryKey }))
  } catch {
    desktopCategoriesLoadFailed.value = true
  } finally {
    loadingDesktopCategories.value = false
  }
}

async function loadDesktopSyncResources() {
  await Promise.all([
    loadDesktopSyncUsers(),
    loadDesktopSyncProjects(),
    loadDesktopSyncCategories(),
  ])
}

async function loadDesktopSyncPolicy() {
  desktopSyncPolicyLoading.value = true
  desktopSyncPolicyLoaded.value = false
  desktopSyncPolicyLoadError.value = ''
  desktopSyncValidationError.value = ''
  try {
    const setting = await getSystemSetting('desktop_sync_policy')
    const policy = normalizeDesktopSyncPolicy(setting?.value)
    Object.assign(desktopSyncSettings, policy)
    desktopSyncPolicyLoaded.value = true
  } catch {
    desktopSyncPolicyLoadError.value = '本地资料同步策略加载失败。为避免覆盖已有配置，当前禁止保存。'
  } finally {
    desktopSyncPolicyLoading.value = false
  }
}

async function retryDesktopSyncPolicy() {
  await loadDesktopSyncPolicy()
}

onMounted(async () => {
  void loadDesktopSyncResources()
  void loadDesktopSyncPolicy()
  try {
    const [reg, login, upload, themes, currentTheme] = await Promise.all([
      getSystemSetting('registration_open'),
      getSystemSetting('login_rules'),
      getSystemSetting('upload_settings'),
      getThemeOptions(),
      getCurrentTheme(),
    ])
    if (reg) Object.assign(regSettings, reg.value as RegistrationSetting)
    if (login) Object.assign(loginRulesSettings, login.value as LoginRulesSetting)
    if (upload) Object.assign(uploadSettings, normalizeUploadSettings(upload.value as UploadSetting))
    themeOptions.value = themes
    Object.assign(themeSettings, {
      themeKey: currentTheme.themeKey,
      darkMode: currentTheme.darkMode,
      compactMode: currentTheme.compactMode,
      applyScope: currentTheme.applyScope,
      brandColor: currentTheme.brandColor || '#165DFF',
      themePackage: currentTheme.themePackage || '',
      sidebarLogoVariant: currentTheme.sidebarLogoVariant || 'color',
      workspaceBackgroundImage: currentTheme.workspaceBackgroundImage || '',
    })
    themePackageInput.value = currentTheme.themePackage || ''
    applyTheme(currentTheme)
  } catch { /* 默认值 */ }
})

function normalizeUploadSettings(value?: Partial<UploadSetting>) {
  const maxFileSizeMb = Math.max(1, Math.min(500, Number(value?.maxFileSizeMb || 100)))
  return { maxFileSizeMb }
}

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

function chooseWorkspaceBackground() {
  workspaceBackgroundInput.value?.click()
}

function readWorkspaceBackground(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('背景图片读取失败，请重新选择。'))
    reader.readAsDataURL(file)
  })
}

async function handleWorkspaceBackgroundFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
    MessagePlugin.warning('工作台背景仅支持 PNG、JPG 或 WebP 图片')
    return
  }
  if (file.size > 2 * 1024 * 1024) {
    MessagePlugin.warning('工作台背景不能超过 2 MB')
    return
  }
  try {
    const dataUrl = await readWorkspaceBackground(file)
    await saveWorkspaceBackground(dataUrl, '工作台背景已更新')
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '背景图片读取失败，请重新选择。')
  }
}

async function restoreDefaultWorkspaceBackground() {
  await saveWorkspaceBackground('', '已恢复系统默认背景')
}

async function saveWorkspaceBackground(value: string, successMessage: string) {
  const previous = themeSettings.workspaceBackgroundImage || ''
  savingTheme.value = true
  try {
    const next = await updateCurrentTheme({
      ...themeSettings,
      brandColor: normalizedBrandColor.value,
      workspaceBackgroundImage: value,
    })
    themeSettings.workspaceBackgroundImage = next.workspaceBackgroundImage || ''
    applyTheme(next)
    MessagePlugin.success(successMessage)
  } catch (err) {
    themeSettings.workspaceBackgroundImage = previous
    MessagePlugin.error(err instanceof Error ? err.message : '工作台背景保存失败，请稍后重试。')
  } finally {
    savingTheme.value = false
  }
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
      workspaceBackgroundImage: next.workspaceBackgroundImage || '',
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
      brandColor: next.brandColor || '#165DFF',
      themePackage: next.themePackage || '',
      sidebarLogoVariant: next.sidebarLogoVariant || 'color',
      workspaceBackgroundImage: next.workspaceBackgroundImage || '',
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
      workspaceBackgroundImage: next.workspaceBackgroundImage || '',
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
      workspaceBackgroundImage: next.workspaceBackgroundImage || '',
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
      workspaceBackgroundImage: next.workspaceBackgroundImage || '',
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

async function saveUploadSettings() {
  savingUpload.value = true
  try {
    Object.assign(uploadSettings, normalizeUploadSettings(uploadSettings))
    await setSystemSetting('upload_settings', { ...uploadSettings }, authStore.username)
    MessagePlugin.success('文件上传设置已保存')
  } catch {
    MessagePlugin.error('文件上传设置保存失败，请稍后重试。')
  } finally {
    savingUpload.value = false
  }
}

async function saveDesktopSyncSettings() {
  desktopSyncValidationError.value = validateDesktopSyncSettings()
  if (desktopSyncValidationError.value) {
    MessagePlugin.warning(desktopSyncValidationError.value)
    return
  }
  const allowedExtensions = inspectDesktopSyncExtensions(desktopSyncSettings.allowedExtensions).values
  savingDesktopSync.value = true
  try {
    const normalized = normalizeDesktopSyncPolicy({
      ...desktopSyncSettings,
      allowedRoles: ['admin'],
      allowedExtensions,
      removeLocalFilesOnRevocation: false,
    })
    Object.assign(desktopSyncSettings, normalized)
    await setSystemSetting(
      'desktop_sync_policy',
      { ...normalized },
      authStore.username,
    )
    desktopSyncValidationError.value = ''
    MessagePlugin.success('本地资料同步策略已保存')
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '同步策略保存失败，请稍后重试。')
  } finally {
    savingDesktopSync.value = false
  }
}
</script>

<style scoped>
.admin-settings {
  max-width: 1120px;
  min-width: 0;
}
.page-header { margin-bottom: var(--space-4); }
.page-title { font-size: var(--text-2xl); font-weight: 700; color: var(--text-primary); margin: 0 0 var(--space-1); }
.page-desc { font-size: var(--text-sm); color: var(--text-secondary); margin: 0; }
.settings-card { margin-bottom: var(--space-5); }
.settings-form { padding-top: var(--space-2); }
.settings-note {
  margin: var(--space-2) 0 0;
  color: var(--text-secondary);
  font-size: var(--text-sm);
}
.switch-text { margin-left: var(--space-3); font-size: var(--text-sm); color: var(--text-secondary); }
.desktop-sync-intro,
.desktop-sync-validation-error,
.desktop-sync-warning {
  margin-bottom: var(--space-4);
}
.desktop-sync-load-error {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.desktop-sync-load-error :deep(.arco-alert) {
  flex: 1;
  min-width: 0;
}
.desktop-sync-form :deep(.arco-form-item-content-flex) {
  min-width: 0;
}
.desktop-sync-form :deep(.arco-select-view) {
  width: min(100%, 680px);
}
.desktop-sync-checkboxes {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
}
.desktop-sync-segmented {
  display: inline-grid;
  grid-template-columns: repeat(2, minmax(150px, 1fr));
  gap: 2px;
  padding: 3px;
  border: 1px solid var(--color-border-2);
  border-radius: var(--radius-md);
  background: var(--color-fill-2);
}
.desktop-sync-segmented button {
  min-height: 34px;
  padding: 0 var(--space-4);
  border: 0;
  border-radius: calc(var(--radius-md) - 2px);
  color: var(--text-secondary);
  background: transparent;
  cursor: pointer;
}
.desktop-sync-segmented button.active {
  color: var(--color-brand-600);
  background: var(--color-bg-2);
  box-shadow: var(--shadow-sm);
}
.desktop-sync-empty {
  width: 100%;
  margin: var(--space-2) 0 0;
  color: var(--text-tertiary);
  font-size: var(--text-sm);
}
.desktop-sync-number-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}
.desktop-sync-number-grid :deep(.arco-form-item) {
  margin-bottom: var(--space-4);
}
.desktop-sync-number-grid :deep(.arco-input-number) {
  width: 128px;
}
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
.workspace-background-panel,
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
.workspace-background-panel strong,
.theme-package-panel strong {
  display: block;
  margin: 2px 0;
  color: var(--text-primary);
  font-size: var(--text-lg);
}
.brand-color-panel em,
.logo-color-panel em,
.workspace-background-panel em,
.theme-package-panel em {
  display: block;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
}
.workspace-background-editor {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto;
  gap: var(--space-3);
  align-items: center;
}
.workspace-background-preview {
  position: relative;
  min-height: 96px;
  overflow: hidden;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background-color: var(--bg-muted);
  background-position: center top;
  background-size: cover;
  background-repeat: no-repeat;
  box-shadow: var(--shadow-sm);
}
.workspace-background-preview span {
  position: absolute;
  right: var(--space-2);
  bottom: var(--space-2);
  padding: 2px 7px;
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  background: rgba(255, 255, 255, .78);
  border: 1px solid rgba(255, 255, 255, .84);
  font-size: var(--text-xs);
  backdrop-filter: blur(8px);
}
.workspace-background-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.workspace-background-input {
  display: none;
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
  .workspace-background-panel,
  .theme-package-panel,
  .theme-scope-panel,
  .theme-preview-board { grid-template-columns: 1fr; }
  .brand-color-controls { grid-template-columns: 44px minmax(0, 1fr); }
  .brand-color-controls :deep(.arco-btn) { grid-column: 1 / -1; }
  .theme-package-controls { grid-template-columns: 1fr; }
  .logo-color-switch { grid-template-columns: 1fr; }
  .workspace-background-editor { grid-template-columns: 1fr; }
  .scope-switch { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .desktop-sync-number-grid { grid-template-columns: 1fr; }
  .desktop-sync-segmented { width: 100%; grid-template-columns: 1fr; }
  .preview-shell { grid-template-columns: 76px minmax(0, 1fr); }
  .theme-preview-card { padding: var(--space-3); }
  .theme-facts { grid-template-columns: 1fr; }
}
</style>

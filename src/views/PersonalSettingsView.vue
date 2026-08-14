<template>
  <main class="personal-settings">
    <PageHeader title="个人设置" description="维护个人资料、本机同步位置、账号安全和客户端版本">
      <template #meta>
        <ATag variant="light" theme="primary">{{ roleLabel }}</ATag>
        <ATag variant="light">{{ desktopAvailable ? 'Windows 客户端' : '网页端' }}</ATag>
      </template>
    </PageHeader>

    <section v-if="activeSection === 'profile'" class="settings-panel">
      <header class="settings-panel__head">
        <div>
          <span>个人资料</span>
          <h2>让协作成员准确识别你</h2>
          <p>姓名和头像会用于项目负责人、操作记录及协作提示；账号修改后用于下次登录。</p>
        </div>
        <AButton theme="primary" :loading="savingProfile" @click="saveProfile">保存资料</AButton>
      </header>

      <div class="profile-layout">
        <div class="avatar-editor">
          <button type="button" class="avatar-editor__button" @click="chooseAvatar">
            <img v-if="profileForm.avatarUrl" :src="profileForm.avatarUrl" alt="当前用户头像" />
            <span v-else>{{ userInitial }}</span>
            <i><AIcon name="edit" /></i>
          </button>
          <strong>{{ profileForm.displayName || profileForm.username }}</strong>
          <small>PNG、JPG 或 WebP，系统将压缩为 256 × 256</small>
          <input
            ref="avatarInput"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            hidden
            @change="handleAvatarChange"
          />
          <AButton v-if="profileForm.avatarUrl" size="small" variant="text" @click="removeAvatar">移除头像</AButton>
        </div>

        <AForm :model="profileForm" class="profile-form" layout="vertical">
          <div class="form-grid">
            <AFormItem label="姓名" required>
              <AInput v-model.trim="profileForm.displayName" :maxlength="50" placeholder="请输入真实姓名" />
            </AFormItem>
            <AFormItem label="登录账号" required>
              <AInput v-model.trim="profileForm.username" :maxlength="32" placeholder="字母、数字、点、下划线或短横线" />
            </AFormItem>
            <AFormItem label="邮箱">
              <AInput v-model.trim="profileForm.email" :maxlength="120" placeholder="用于工作联系" />
            </AFormItem>
            <AFormItem label="联系电话">
              <AInput v-model.trim="profileForm.phone" :maxlength="30" placeholder="请输入联系电话" />
            </AFormItem>
            <AFormItem label="所属部门">
              <AInput v-model.trim="profileForm.department" :maxlength="80" placeholder="如：工程管理部" />
            </AFormItem>
            <AFormItem label="职务">
              <AInput v-model.trim="profileForm.jobTitle" :maxlength="80" placeholder="如：项目经理" />
            </AFormItem>
            <AFormItem label="角色">
              <AInput :model-value="roleLabel" disabled />
            </AFormItem>
            <AFormItem label="账号创建时间">
              <AInput :model-value="createdAtLabel" disabled />
            </AFormItem>
            <AFormItem class="form-grid__full" label="个人说明">
              <ATextarea
                v-model="profileForm.bio"
                :maxlength="300"
                :auto-size="{ minRows: 3, maxRows: 5 }"
                placeholder="可填写负责范围或协作说明"
              />
            </AFormItem>
          </div>
        </AForm>
      </div>
    </section>

    <section v-else-if="activeSection === 'sync'" class="settings-panel">
      <header class="settings-panel__head">
        <div>
          <span>文件同步</span>
          <h2>设置这台电脑的资料同步位置</h2>
          <p>这里只设置本机文件夹。可同步的用户、项目、资料类型和容量由管理员在后台管理中统一控制。</p>
        </div>
        <AButton v-if="desktopAvailable" variant="outline" :loading="loadingSync" @click="refreshSyncState">刷新状态</AButton>
      </header>

      <div v-if="desktopAvailable" class="sync-settings">
        <div class="sync-status">
          <span class="sync-status__icon"><AIcon name="folder" /></span>
          <div>
            <small>当前状态</small>
            <strong>{{ syncStatusLabel }}</strong>
            <p>{{ syncState?.message || '尚未读取桌面同步状态' }}</p>
          </div>
          <ATag :theme="syncStatusTheme" variant="light">{{ syncStatusLabel }}</ATag>
        </div>

        <div class="sync-folder-row">
          <div>
            <small>本机同步文件夹</small>
            <strong>{{ syncState?.localRoot || '尚未选择' }}</strong>
            <p>建议选择“文档”中的独立文件夹，不要选择应用安装目录或系统目录。</p>
          </div>
          <div class="sync-folder-actions">
            <AButton theme="primary" :loading="selectingFolder" @click="selectSyncFolder">
              <AIcon name="folder" />
              {{ syncState?.localRoot ? '更换文件夹' : '选择文件夹' }}
            </AButton>
            <AButton variant="outline" :disabled="!syncState?.localRoot" @click="openSyncFolder">
              <AIcon name="folder" />
              打开文件夹
            </AButton>
          </div>
        </div>

        <div class="sync-metrics">
          <div><small>已完成文件</small><strong>{{ syncState?.completedFiles || 0 }}</strong></div>
          <div><small>本次总文件</small><strong>{{ syncState?.totalFiles || 0 }}</strong></div>
          <div><small>失败文件</small><strong>{{ syncState?.failedFiles || 0 }}</strong></div>
          <div><small>最近成功同步</small><strong>{{ syncLastSuccessLabel }}</strong></div>
        </div>
      </div>

      <div v-else class="desktop-unavailable">
        <span><AIcon name="setting" /></span>
        <div>
          <h3>本地文件夹同步仅在 Windows 客户端中可用</h3>
          <p>网页端仍可正常查看和上传资料，但无法直接选择电脑文件夹。请使用集庆工程管理 Windows 客户端完成此项设置。</p>
        </div>
      </div>
    </section>

    <section v-else-if="activeSection === 'security'" class="settings-panel">
      <header class="settings-panel__head">
        <div>
          <span>账号安全</span>
          <h2>修改当前账号的登录密码</h2>
          <p>修改成功后，下次登录请使用新密码。系统不会向任何页面展示你的密码。</p>
        </div>
        <AButton theme="primary" :loading="savingPassword" @click="savePassword">修改密码</AButton>
      </header>

      <AForm :model="passwordForm" class="security-form" layout="vertical">
        <AFormItem label="当前密码" required>
          <AInput v-model="passwordForm.currentPassword" type="password" autocomplete="current-password" placeholder="请输入当前密码" />
        </AFormItem>
        <AFormItem label="新密码" required>
          <AInput v-model="passwordForm.newPassword" type="password" autocomplete="new-password" :placeholder="`至少 ${minimumPasswordLength} 个字符`" />
        </AFormItem>
        <AFormItem label="确认新密码" required>
          <AInput v-model="passwordForm.confirmPassword" type="password" autocomplete="new-password" placeholder="请再次输入新密码" />
        </AFormItem>
      </AForm>
    </section>

    <section v-else class="settings-panel">
      <header class="settings-panel__head">
        <div>
          <span>关于与更新</span>
          <h2>集庆工程管理 Windows 客户端</h2>
          <p>查看当前安装版本和发布通道。检查到新版本后，客户端会下载更新，并由你确认重启安装。</p>
        </div>
        <AButton
          v-if="desktopAvailable"
          variant="outline"
          :loading="checkingUpdate"
          :disabled="!updateState?.canCheck"
          @click="checkForUpdates"
        >
          <template #icon><AIcon name="refresh" /></template>
          检查更新
        </AButton>
      </header>

      <div v-if="desktopAvailable" class="about-settings">
        <div class="version-mark">
          <span><AIcon name="info-circle" /></span>
          <div>
            <small>当前版本</small>
            <strong>V{{ clientVersion }}</strong>
            <p>{{ releaseChannelLabel }} · Windows x64</p>
          </div>
        </div>

        <div class="update-status-card">
          <div class="update-status-card__copy">
            <small>在线更新状态</small>
            <strong>{{ updateStatusLabel }}</strong>
            <p>{{ updateState?.message || '正在读取客户端更新状态' }}</p>
            <p v-if="updateState?.lastCheckedAt">上次检查：{{ formatDateTime(updateState.lastCheckedAt) }}</p>
          </div>
          <ATag :theme="updateStatusTheme" variant="light">{{ updateStatusLabel }}</ATag>
        </div>

        <div v-if="showUpdateProgress" class="update-progress" aria-live="polite">
          <div>
            <span>正在下载 V{{ updateState?.availableVersion || '新版本' }}</span>
            <strong>{{ updateState?.progressPercent || 0 }}%</strong>
          </div>
          <progress :value="updateState?.progressPercent || 0" max="100" />
        </div>

        <div v-if="updateState?.canInstall" class="install-update-row">
          <div>
            <strong>V{{ updateState.availableVersion }} 已准备完成</strong>
            <p>保存正在编辑的内容后重启安装。应用会关闭并完成更新。</p>
          </div>
          <AButton theme="primary" @click="installUpdate">立即重启安装</AButton>
        </div>
      </div>

      <div v-else class="desktop-unavailable">
        <span><AIcon name="info-circle" /></span>
        <div>
          <h3>当前是网页端</h3>
          <p>客户端版本号和在线更新仅在已安装的 Windows 客户端中显示。网页系统由服务器统一更新。</p>
        </div>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import { changeCurrentUserPassword, updateCurrentUserProfile } from '@/api/system'
import { useAuthStore } from '@/store/auth'
import { MessagePlugin } from '@/ui/message'
import type {
  DesktopCapabilities,
  DesktopSyncState,
  DesktopUpdateState,
} from '@/types/desktop'

type SettingsSection = 'profile' | 'sync' | 'security' | 'about'

const route = useRoute()
const authStore = useAuthStore()
const avatarInput = ref<HTMLInputElement | null>(null)
const savingProfile = ref(false)
const savingPassword = ref(false)
const loadingSync = ref(false)
const selectingFolder = ref(false)
const checkingUpdate = ref(false)
const syncState = ref<DesktopSyncState | null>(null)
const desktopCapabilities = ref<DesktopCapabilities | null>(null)
const updateState = ref<DesktopUpdateState | null>(null)
let unsubscribeSync: (() => void) | null = null
let unsubscribeUpdate: (() => void) | null = null

const profileForm = reactive({
  username: '',
  displayName: '',
  email: '',
  avatarUrl: '',
  phone: '',
  department: '',
  jobTitle: '',
  bio: '',
})
const passwordForm = reactive({
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const activeSection = computed<SettingsSection>(() => {
  const section = String(route.query.section || 'profile')
  return section === 'sync' || section === 'security' || section === 'about'
    ? section
    : 'profile'
})
const desktopAvailable = computed(() => Boolean(window.jiqingDesktop))
const roleLabel = computed(() => ({
  admin: '系统管理员',
  editor: '业务编辑者',
  viewer: '查看者',
})[authStore.userRole] || '普通用户')
const userInitial = computed(() => (
  profileForm.displayName || profileForm.username || '用'
).trim().slice(0, 1))
const createdAtLabel = computed(() => formatDateTime(authStore.user?.createdAt || ''))
const minimumPasswordLength = computed(() => authStore.loginRules.minPasswordLength || 8)
const syncStatusLabel = computed(() => ({
  disabled: '管理员未启用',
  waiting_for_login: '等待登录',
  checking_policy: '正在检查权限',
  syncing: '正在同步',
  paused: '已暂停',
  completed: '同步完成',
  partial_failure: '部分失败',
  permission_changed: '权限已变化',
  offline: '网络不可用',
})[syncState.value?.status || 'paused'])
const syncStatusTheme = computed(() => {
  switch (syncState.value?.status) {
    case 'completed': return 'success'
    case 'syncing': return 'primary'
    case 'partial_failure':
    case 'offline': return 'warning'
    case 'permission_changed': return 'danger'
    default: return 'default'
  }
})
const syncLastSuccessLabel = computed(() => (
  syncState.value?.lastSuccessAt ? formatDateTime(syncState.value.lastSuccessAt) : '暂无记录'
))
const clientVersion = computed(() => (
  updateState.value?.currentVersion
  || desktopCapabilities.value?.clientVersion
  || '未知'
))
const releaseChannelLabel = computed(() => ({
  development: '开发环境',
  'internal-test': '内部测试通道',
  production: '正式发布通道',
})[desktopCapabilities.value?.releaseChannel || 'development'])
const updateStatusLabel = computed(() => ({
  unavailable: '当前环境不支持',
  idle: '可以检查更新',
  checking: '正在检查',
  available: '发现新版本',
  downloading: '正在下载',
  downloaded: '等待安装',
  up_to_date: '已是最新版本',
  error: '检查失败',
})[updateState.value?.status || 'idle'])
const updateStatusTheme = computed(() => {
  switch (updateState.value?.status) {
    case 'up_to_date': return 'success'
    case 'available':
    case 'downloading':
    case 'downloaded': return 'primary'
    case 'error': return 'danger'
    default: return 'default'
  }
})
const showUpdateProgress = computed(() => (
  updateState.value?.status === 'available'
  || updateState.value?.status === 'downloading'
))

function hydrateProfile() {
  const user = authStore.user
  if (!user) return
  profileForm.username = user.username || ''
  profileForm.displayName = user.displayName || ''
  profileForm.email = user.email || ''
  profileForm.avatarUrl = user.avatarUrl || ''
  profileForm.phone = user.phone || ''
  profileForm.department = user.department || ''
  profileForm.jobTitle = user.jobTitle || ''
  profileForm.bio = user.bio || ''
}

function formatDateTime(value: string) {
  if (!value) return '暂无'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { hour12: false })
}

function chooseAvatar() {
  avatarInput.value?.click()
}

async function resizeAvatar(file: File): Promise<string> {
  if (file.size > 5 * 1024 * 1024) throw new Error('头像文件不能超过 5 MB')
  const source = URL.createObjectURL(file)
  try {
    const image = new Image()
    image.src = source
    await image.decode()
    const size = Math.min(image.naturalWidth, image.naturalHeight)
    const sx = Math.max(0, (image.naturalWidth - size) / 2)
    const sy = Math.max(0, (image.naturalHeight - size) / 2)
    const canvas = document.createElement('canvas')
    canvas.width = 256
    canvas.height = 256
    const context = canvas.getContext('2d')
    if (!context) throw new Error('当前浏览器无法处理头像图片')
    context.drawImage(image, sx, sy, size, size, 0, 0, 256, 256)
    return canvas.toDataURL('image/jpeg', 0.86)
  } finally {
    URL.revokeObjectURL(source)
  }
}

async function handleAvatarChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  try {
    profileForm.avatarUrl = await resizeAvatar(file)
  } catch (error) {
    MessagePlugin.error(error instanceof Error ? error.message : '头像处理失败')
  }
}

function removeAvatar() {
  profileForm.avatarUrl = ''
}

async function saveProfile() {
  if (!profileForm.displayName.trim()) {
    MessagePlugin.warning('请输入姓名')
    return
  }
  if (!/^[A-Za-z0-9._-]{3,32}$/.test(profileForm.username)) {
    MessagePlugin.warning('账号仅支持 3-32 位字母、数字、点、下划线或短横线')
    return
  }
  savingProfile.value = true
  try {
    const profile = await updateCurrentUserProfile({ ...profileForm })
    authStore.setCurrentUserProfile(profile)
    hydrateProfile()
    MessagePlugin.success('个人资料已保存')
  } catch (error) {
    MessagePlugin.error(error instanceof Error ? error.message : '个人资料保存失败')
  } finally {
    savingProfile.value = false
  }
}

async function savePassword() {
  if (!passwordForm.currentPassword) {
    MessagePlugin.warning('请输入当前密码')
    return
  }
  if (passwordForm.newPassword.length < minimumPasswordLength.value) {
    MessagePlugin.warning(`新密码至少需要 ${minimumPasswordLength.value} 个字符`)
    return
  }
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    MessagePlugin.warning('两次输入的新密码不一致')
    return
  }
  savingPassword.value = true
  try {
    await changeCurrentUserPassword({
      currentPassword: passwordForm.currentPassword,
      newPassword: passwordForm.newPassword,
    })
    passwordForm.currentPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirmPassword = ''
    MessagePlugin.success('密码已修改')
  } catch (error) {
    MessagePlugin.error(error instanceof Error ? error.message : '密码修改失败')
  } finally {
    savingPassword.value = false
  }
}

async function refreshSyncState() {
  if (!window.jiqingDesktop) return
  loadingSync.value = true
  try {
    syncState.value = await window.jiqingDesktop.getSyncState()
  } catch (error) {
    MessagePlugin.error(error instanceof Error ? error.message : '读取同步状态失败')
  } finally {
    loadingSync.value = false
  }
}

async function selectSyncFolder() {
  if (!window.jiqingDesktop) return
  selectingFolder.value = true
  try {
    await window.jiqingDesktop.selectSyncFolder()
    await refreshSyncState()
  } catch (error) {
    MessagePlugin.error(error instanceof Error ? error.message : '选择同步文件夹失败')
  } finally {
    selectingFolder.value = false
  }
}

async function openSyncFolder() {
  try {
    await window.jiqingDesktop?.openSyncFolder()
  } catch (error) {
    MessagePlugin.error(error instanceof Error ? error.message : '打开同步文件夹失败')
  }
}

async function refreshUpdateState() {
  if (!window.jiqingDesktop) return
  try {
    const [capabilities, state] = await Promise.all([
      window.jiqingDesktop.getCapabilities(),
      window.jiqingDesktop.getUpdateState(),
    ])
    desktopCapabilities.value = capabilities
    updateState.value = state
  } catch (error) {
    MessagePlugin.error(error instanceof Error ? error.message : '读取客户端版本失败')
  }
}

async function checkForUpdates() {
  if (!window.jiqingDesktop) return
  checkingUpdate.value = true
  try {
    updateState.value = await window.jiqingDesktop.checkForUpdates()
  } catch (error) {
    MessagePlugin.error(error instanceof Error ? error.message : '检查更新失败')
  } finally {
    checkingUpdate.value = false
  }
}

async function installUpdate() {
  try {
    await window.jiqingDesktop?.installUpdate()
  } catch (error) {
    MessagePlugin.error(error instanceof Error ? error.message : '启动更新安装失败')
  }
}

watch(() => authStore.user, hydrateProfile, { immediate: true })
watch(activeSection, (section) => {
  if (section === 'sync') void refreshSyncState()
  if (section === 'about') void refreshUpdateState()
})

onMounted(() => {
  if (window.jiqingDesktop) {
    unsubscribeSync = window.jiqingDesktop.onSyncState((state) => {
      syncState.value = state
    })
    unsubscribeUpdate = window.jiqingDesktop.onUpdateState((state) => {
      updateState.value = state
    })
    if (activeSection.value === 'sync') void refreshSyncState()
    if (activeSection.value === 'about') void refreshUpdateState()
  }
})

onBeforeUnmount(() => {
  unsubscribeSync?.()
  unsubscribeSync = null
  unsubscribeUpdate?.()
  unsubscribeUpdate = null
})
</script>

<style scoped>
.personal-settings {
  display: grid;
  gap: 16px;
  padding: 20px 24px 32px;
}

.settings-panel {
  overflow: hidden;
  border: 1px solid rgba(143, 164, 201, 0.32);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 12px 32px rgba(58, 91, 145, 0.08);
  backdrop-filter: blur(18px);
}

.settings-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 22px 24px;
  border-bottom: 1px solid rgba(143, 164, 201, 0.24);
  background: rgba(248, 251, 255, 0.72);
}

.settings-panel__head span {
  color: #165dff;
  font-size: 12px;
  font-weight: 700;
}

.settings-panel__head h2 {
  margin: 4px 0 6px;
  color: #14213d;
  font-size: 20px;
}

.settings-panel__head p,
.sync-status p,
.sync-folder-row p,
.desktop-unavailable p {
  margin: 0;
  color: #6b7892;
  line-height: 1.7;
}

.profile-layout {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 28px;
  padding: 28px 24px;
}

.avatar-editor {
  display: flex;
  align-items: center;
  flex-direction: column;
  gap: 10px;
  padding: 8px 12px;
  text-align: center;
}

.avatar-editor__button {
  position: relative;
  width: 112px;
  height: 112px;
  overflow: hidden;
  display: grid;
  place-items: center;
  padding: 0;
  color: #fff;
  font-size: 38px;
  font-weight: 800;
  border: 1px solid rgba(255, 255, 255, 0.92);
  border-radius: 50%;
  background: linear-gradient(145deg, #165dff, #0f43d6);
  box-shadow: 0 10px 24px rgba(22, 93, 255, 0.2);
  cursor: pointer;
}

.avatar-editor__button img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.avatar-editor__button i {
  position: absolute;
  right: 4px;
  bottom: 4px;
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: rgba(15, 33, 61, 0.86);
}

.avatar-editor small {
  max-width: 180px;
  color: #86909c;
  line-height: 1.6;
}

.profile-form {
  min-width: 0;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px 18px;
}

.form-grid__full {
  grid-column: 1 / -1;
}

.sync-settings {
  display: grid;
  gap: 18px;
  padding: 24px;
}

.sync-status,
.sync-folder-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px;
  border: 1px solid rgba(143, 164, 201, 0.26);
  border-radius: 8px;
  background: rgba(248, 251, 255, 0.78);
}

.sync-status > div,
.sync-folder-row > div:first-child {
  min-width: 0;
  flex: 1;
}

.sync-status__icon,
.desktop-unavailable > span {
  width: 44px;
  height: 44px;
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  color: #165dff;
  font-size: 21px;
  border-radius: 8px;
  background: #e8f3ff;
}

.sync-status small,
.sync-folder-row small,
.sync-metrics small {
  display: block;
  margin-bottom: 5px;
  color: #86909c;
}

.sync-status strong,
.sync-folder-row strong {
  display: block;
  overflow: hidden;
  margin-bottom: 4px;
  color: #14213d;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sync-folder-actions {
  display: flex;
  flex: 0 0 auto;
  gap: 10px;
}

.sync-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.sync-metrics > div {
  min-height: 82px;
  padding: 16px;
  border-left: 3px solid #165dff;
  background: rgba(248, 251, 255, 0.72);
}

.sync-metrics strong {
  color: #14213d;
  font-size: 18px;
}

.desktop-unavailable {
  display: flex;
  align-items: flex-start;
  gap: 18px;
  margin: 24px;
  padding: 22px;
  border: 1px solid rgba(143, 164, 201, 0.28);
  border-radius: 8px;
  background: rgba(248, 251, 255, 0.72);
}

.desktop-unavailable h3 {
  margin: 0 0 8px;
  color: #14213d;
}

.security-form {
  width: min(560px, 100%);
  padding: 28px 24px 32px;
}

.about-settings {
  display: grid;
  grid-template-columns: minmax(220px, 0.72fr) minmax(0, 1.28fr);
  gap: 16px;
  padding: 24px;
}

.version-mark,
.update-status-card,
.install-update-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  border: 1px solid rgba(143, 164, 201, 0.26);
  border-radius: 8px;
  background: rgba(248, 251, 255, 0.78);
}

.version-mark > span {
  width: 48px;
  height: 48px;
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  color: #165dff;
  font-size: 23px;
  border-radius: 8px;
  background: #e8f3ff;
}

.version-mark div,
.update-status-card__copy,
.install-update-row > div {
  min-width: 0;
  flex: 1;
}

.version-mark small,
.update-status-card small {
  display: block;
  margin-bottom: 5px;
  color: #86909c;
}

.version-mark strong,
.update-status-card strong,
.install-update-row strong {
  color: #14213d;
  font-size: 18px;
}

.version-mark p,
.update-status-card p,
.install-update-row p {
  margin: 5px 0 0;
  color: #6b7892;
  line-height: 1.6;
}

.update-progress,
.install-update-row {
  grid-column: 1 / -1;
}

.update-progress {
  padding: 16px 20px;
  border-radius: 8px;
  background: rgba(232, 243, 255, 0.72);
}

.update-progress > div {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 10px;
  color: #14213d;
}

.update-progress progress {
  width: 100%;
  height: 8px;
  overflow: hidden;
  border: 0;
  border-radius: 4px;
  accent-color: #165dff;
}

@media (max-width: 880px) {
  .personal-settings { padding: 16px; }
  .profile-layout { grid-template-columns: 1fr; }
  .avatar-editor { padding-bottom: 18px; }
  .sync-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .about-settings { grid-template-columns: 1fr; }
  .update-progress,
  .install-update-row { grid-column: auto; }
}

@media (max-width: 640px) {
  .settings-panel__head,
  .sync-folder-row {
    align-items: stretch;
    flex-direction: column;
  }
  .form-grid,
  .sync-metrics {
    grid-template-columns: 1fr;
  }
  .sync-folder-actions {
    width: 100%;
    flex-wrap: wrap;
  }
}
</style>

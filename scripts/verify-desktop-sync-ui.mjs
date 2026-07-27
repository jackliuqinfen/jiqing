import { existsSync, readFileSync } from 'node:fs'

const paths = {
  library: 'src/views/admin/AdminFileLibrary.vue',
  dialog: 'src/components/desktop/DesktopSyncDialog.vue',
  composable: 'src/composables/useDesktopSync.ts',
  systemApi: 'src/api/system.ts',
  authStore: 'src/store/auth.ts',
}

for (const [name, path] of Object.entries(paths)) {
  if (!existsSync(path)) {
    throw new Error(`Missing desktop sync ${name}: ${path}`)
  }
}

const library = readFileSync(paths.library, 'utf8')
const dialog = readFileSync(paths.dialog, 'utf8')
const composable = readFileSync(paths.composable, 'utf8')
const systemApi = readFileSync(paths.systemApi, 'utf8')
const authStore = readFileSync(paths.authStore, 'utf8')

for (const marker of ['本地同步', 'DesktopSyncDialog', 'isDesktop']) {
  if (!library.includes(marker)) throw new Error(`Missing file-center marker: ${marker}`)
}

for (const marker of [
  '服务器到本地只读同步',
  '选择本地文件夹',
  '立即同步',
  '暂停同步',
  '打开本地文件夹',
  '本地新增或修改不会自动上传',
]) {
  if (!dialog.includes(marker)) throw new Error(`Missing dialog marker: ${marker}`)
}

if (dialog.includes('rgb(var(--danger-6))')) {
  throw new Error('Desktop sync dialog must use the shared system danger color token')
}

for (const marker of [
  'fetchDesktopSyncProjects',
  'getAuthToken',
  'createDesktopSyncProjectLoadCycle',
  'invalidateProjectLoads',
  'startSync',
  'pauseSync',
  'openSyncFolder',
  'permission_changed',
  'onSyncState',
]) {
  if (!composable.includes(marker)) throw new Error(`Missing sync composable marker: ${marker}`)
}

for (const invalidationReason of [
  'dialog_close',
  'auth_change',
  'permission_changed',
  'unmount',
]) {
  if (!composable.includes(invalidationReason)) {
    throw new Error(`Missing project-load invalidation: ${invalidationReason}`)
  }
}

const currentLoadGuardCount = composable.split('isCurrentProjectLoad(loadTicket)').length - 1
if (currentLoadGuardCount < 3) {
  throw new Error('Project load success, failure, and finally paths must all reject stale cycles')
}

if (composable.includes('applyState(await bridge.value.startSync')) {
  throw new Error('Starting a long-running sync must not block the pause command')
}

if (dialog.includes(':disabled="!isSyncing || actionPending"')) {
  throw new Error('Pause must remain available while a synchronization run is active')
}

if (!systemApi.includes("decodeDesktopSyncProjects(await request<unknown>('/desktop/sync/projects'))")) {
  throw new Error('Desktop sync projects must strictly decode the authenticated real-data endpoint')
}

const pauseIndex = authStore.indexOf('window.jiqingDesktop?.pauseSync()')
const logoutIndex = authStore.indexOf('logoutSession()')
if (pauseIndex < 0 || logoutIndex < 0 || pauseIndex > logoutIndex) {
  throw new Error('Desktop synchronization must pause before logout clears the token')
}

console.log('Desktop sync UI contract verified')

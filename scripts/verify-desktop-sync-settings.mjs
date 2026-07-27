import { readFileSync } from 'node:fs'

const settings = readFileSync('src/views/admin/AdminSystemSettings.vue', 'utf8')
const types = readFileSync('src/types/index.ts', 'utf8')

for (const marker of [
  '本地资料同步',
  '服务器到本地只读同步',
  'allowedRoles',
  'enabledByDefault',
  'projectSelectionMode',
  'maxLocalStorageGb',
  'pollIntervalSeconds',
  'removeLocalFilesOnRevocation',
]) {
  if (!settings.includes(marker)) throw new Error(`Missing settings marker: ${marker}`)
}

if (!types.includes("'desktop_sync_policy'")) {
  throw new Error('desktop_sync_policy is missing from SystemSettingKey')
}
if (!types.includes('interface DesktopSyncPolicySetting')) {
  throw new Error('DesktopSyncPolicySetting is missing')
}

for (const marker of [
  'normalizeDesktopSyncPolicy',
  'normalizeDesktopSyncExtensions',
  "desktopDisplayUnit(raw, 'maxFileSizeMb', 'maxFileSizeBytes', 100",
  "desktopDisplayUnit(raw, 'maxLocalStorageGb', 'maxLocalStorageBytes', 10",
  'boundedDesktopSyncInteger(raw.pollIntervalSeconds, 300, 60, 3600)',
  'typeof value ===',
  'Number.isFinite',
]) {
  if (!settings.includes(marker)) throw new Error(`Missing normalization marker: ${marker}`)
}

for (const marker of [
  'desktopSyncPolicyLoaded',
  ':disabled="!desktopSyncPolicyLoaded',
  'desktopSyncPolicyLoadError',
  'retryDesktopSyncPolicy',
  'withRetainedDesktopOptions',
  'MAX_DESKTOP_EXTENSION_COUNT = 30',
  'MAX_DESKTOP_EXTENSION_LENGTH = 16',
  'validateDesktopSyncSettings',
  '请至少保留一个允许使用的角色',
  '请至少保留一种允许同步的文件格式',
]) {
  if (!settings.includes(marker)) throw new Error(`Missing fail-closed marker: ${marker}`)
}

const extensionLabelIndex = settings.indexOf('label="允许的文件格式"')
const extensionFieldStart = settings.lastIndexOf('<AFormItem', extensionLabelIndex)
const extensionFieldEnd = settings.indexOf('</AFormItem>', extensionLabelIndex)
const extensionField = extensionLabelIndex >= 0 && extensionFieldStart >= 0 && extensionFieldEnd >= 0
  ? settings.slice(extensionFieldStart, extensionFieldEnd)
  : ''
if (!extensionField) throw new Error('Desktop sync extension field is missing')
if (extensionField.includes('allow-clear')) {
  throw new Error('Desktop sync extension field must not advertise a clear-all action')
}

const mountedStart = settings.indexOf('onMounted(async () =>')
const mountedEnd = settings.indexOf('function normalizeUploadSettings', mountedStart)
const mountedBlock = settings.slice(mountedStart, mountedEnd)
if (mountedBlock.includes("getSystemSetting('desktop_sync_policy')")) {
  throw new Error('Desktop sync policy must load independently from unrelated settings')
}

const saveStart = settings.indexOf('async function saveDesktopSyncSettings')
const saveEnd = settings.indexOf('</script>', saveStart)
const saveBlock = settings.slice(saveStart, saveEnd)
if (
  saveBlock.indexOf('validateDesktopSyncSettings()') < 0
  || saveBlock.indexOf('validateDesktopSyncSettings()') > saveBlock.indexOf('savingDesktopSync.value = true')
) {
  throw new Error('Desktop sync validation must run before save begins')
}

for (const forbidden of [
  'desktopUserOptions.value = []',
  'desktopProjectOptions.value = []',
  'desktopCategoryOptions.value = []',
]) {
  if (settings.includes(forbidden)) {
    throw new Error(`Option load failures must retain prior real values: ${forbidden}`)
  }
}

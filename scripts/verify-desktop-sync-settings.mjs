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

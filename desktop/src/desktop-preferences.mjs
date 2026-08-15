import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from 'node:fs'
import { dirname, join } from 'node:path'

const MAX_SYNC_ROOT_LENGTH = 32767
const PROJECT_REF_PATTERN = /^(project|audit):[A-Za-z0-9-]+$/
const MAX_PROJECT_REFS = 500

function normalizePreferences(value) {
  const localRoot = typeof value?.localRoot === 'string'
    ? value.localRoot.trim()
    : ''
  const selectedProjectRefs = Array.isArray(value?.selectedProjectRefs)
    ? [...new Set(value.selectedProjectRefs.filter((item) => (
      typeof item === 'string'
      && PROJECT_REF_PATTERN.test(item)
    )))].slice(0, MAX_PROJECT_REFS)
    : []
  return Object.freeze({
    localRoot: localRoot.length <= MAX_SYNC_ROOT_LENGTH ? localRoot : '',
    selectedProjectRefs: Object.freeze(selectedProjectRefs),
  })
}

export function desktopPreferencesPath(userDataPath) {
  return join(userDataPath, 'desktop-preferences.json')
}

export function readDesktopPreferences(userDataPath) {
  const target = desktopPreferencesPath(userDataPath)
  if (!existsSync(target)) return normalizePreferences({})
  try {
    return normalizePreferences(JSON.parse(readFileSync(target, 'utf8')))
  } catch {
    return normalizePreferences({})
  }
}

export function writeDesktopPreferences(userDataPath, value) {
  const target = desktopPreferencesPath(userDataPath)
  const temporaryPath = `${target}.${process.pid}.tmp`
  const normalized = normalizePreferences(value)
  mkdirSync(dirname(target), { recursive: true })
  writeFileSync(temporaryPath, `${JSON.stringify(normalized, null, 2)}\n`, {
    encoding: 'utf8',
    mode: 0o600,
  })
  renameSync(temporaryPath, target)
  return normalized
}

import { createHash, randomUUID } from 'node:crypto'
import {
  mkdir,
  open,
  readFile,
  rename,
  rm,
} from 'node:fs/promises'
import {
  dirname,
  isAbsolute,
  join,
  normalize,
  resolve,
} from 'node:path'

const SCHEMA_VERSION = 1
const RECOVERY_ENTRY_KEYS = Object.freeze([
  'accountedBytes',
  'cleanupFiles',
  'createdAt',
  'id',
  'physicalFiles',
  'previousSourceRevision',
  'rootPath',
  'sourceKey',
  'sourceRevision',
  'type',
])
const RECOVERY_TRANSACTION_ID = /^[a-f0-9]{32}$/
const saveQueues = new Map()

function environmentKey(origin) {
  return createHash('sha256').update(origin, 'utf8').digest('hex')
}

function userFilename(userId) {
  return `user-${createHash('sha256').update(userId, 'utf8').digest('hex')}.json`
}

function isPlainObject(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const prototype = Object.getPrototypeOf(value)
  return prototype === Object.prototype || prototype === null
}

function isStringArray(value) {
  return Array.isArray(value)
    && value.every((item) => typeof item === 'string' && item.length > 0)
}

function hasExactKeys(value, expectedKeys) {
  const keys = Object.keys(value).sort()
  return keys.length === expectedKeys.length
    && keys.every((key, index) => key === expectedKeys[index])
}

function isCanonicalAbsolutePath(value) {
  return typeof value === 'string'
    && value.length > 0
    && value.length <= 4096
    && isAbsolute(value)
    && normalize(value) === value
    && resolve(value) === value
}

function isRecoveryRelativePath(value, transactionId) {
  return value === `.jiqing-backup-${transactionId}`
    || value === `.jiqing-rollback-${transactionId}`
}

function isIsoTimestamp(value) {
  if (typeof value !== 'string') return false
  const parsed = new Date(value)
  return !Number.isNaN(parsed.valueOf()) && parsed.toISOString() === value
}

function hasValidRecoveryShape(entry, transactionId) {
  const backupPath = `.jiqing-backup-${transactionId}`
  const rollbackPath = `.jiqing-rollback-${transactionId}`
  if (entry.type === 'cleanup_pending') {
    return entry.physicalFiles.length === 1
      && entry.cleanupFiles.length === 1
      && entry.physicalFiles[0] === entry.cleanupFiles[0]
  }
  return entry.type === 'manual_recovery'
    && entry.cleanupFiles.length === 0
    && (
      (
        entry.physicalFiles.length === 1
        && entry.physicalFiles[0] === backupPath
      )
      || (
        entry.physicalFiles.length === 2
        && entry.physicalFiles[0] === rollbackPath
        && entry.physicalFiles[1] === backupPath
      )
    )
}

function isValidRecoveryEntries(entries) {
  return isPlainObject(entries)
    && Object.entries(entries).every(([id, entry]) => (
      isPlainObject(entry)
      && hasExactKeys(entry, RECOVERY_ENTRY_KEYS)
      && RECOVERY_TRANSACTION_ID.test(id)
      && entry.id === id
      && typeof entry.sourceKey === 'string'
      && entry.sourceKey.length > 0
      && entry.sourceKey.length <= 1024
      && typeof entry.previousSourceRevision === 'string'
      && entry.previousSourceRevision.length <= 1024
      && typeof entry.sourceRevision === 'string'
      && entry.sourceRevision.length > 0
      && entry.sourceRevision.length <= 1024
      && ['cleanup_pending', 'manual_recovery'].includes(entry.type)
      && isCanonicalAbsolutePath(entry.rootPath)
      && isStringArray(entry.physicalFiles)
      && entry.physicalFiles.length > 0
      && new Set(entry.physicalFiles).size === entry.physicalFiles.length
      && entry.physicalFiles.every(
        (relativePath) => isRecoveryRelativePath(relativePath, id),
      )
      && isStringArray(entry.cleanupFiles)
      && new Set(entry.cleanupFiles).size === entry.cleanupFiles.length
      && entry.cleanupFiles.every(
        (relativePath) => entry.physicalFiles.includes(relativePath),
      )
      && hasValidRecoveryShape(entry, id)
      && Number.isSafeInteger(entry.accountedBytes)
      && entry.accountedBytes >= 0
      && isIsoTimestamp(entry.createdAt)
    ))
}

function isValidIndex(index, environmentOrigin, userId) {
  return (
    isPlainObject(index)
    && index.schemaVersion === SCHEMA_VERSION
    && index.environmentOrigin === environmentOrigin
    && index.userId === userId
    && isPlainObject(index.cursorBySelection)
    && isPlainObject(index.files)
    && (
      index.recoveryEntries === undefined
      || isValidRecoveryEntries(index.recoveryEntries)
    )
  )
}

function quarantineTimestamp(now) {
  return now().toISOString().replace(/[:.]/g, '-')
}

export function createEmptyIndex(environmentOrigin, userId) {
  return {
    schemaVersion: SCHEMA_VERSION,
    environmentOrigin,
    userId,
    cursorBySelection: {},
    files: {},
    recoveryEntries: {},
  }
}

export class SyncIndexStore {
  constructor({
    appDataPath,
    environmentOrigin,
    userId,
    now = () => new Date(),
  }) {
    if (
      typeof appDataPath !== 'string'
      || !appDataPath
      || typeof environmentOrigin !== 'string'
      || !environmentOrigin
      || typeof userId !== 'string'
      || !userId
    ) {
      throw new Error('invalid sync index configuration')
    }
    this.environmentOrigin = environmentOrigin
    this.userId = userId
    this.now = now
    this.directoryPath = join(
      appDataPath,
      'sync-index',
      environmentKey(environmentOrigin),
    )
    this.filePath = join(this.directoryPath, userFilename(userId))
  }

  async load() {
    let serialized
    try {
      serialized = await readFile(this.filePath, 'utf8')
    } catch (error) {
      if (error?.code === 'ENOENT') {
        return createEmptyIndex(this.environmentOrigin, this.userId)
      }
      throw error
    }

    try {
      const parsed = JSON.parse(serialized)
      if (!isValidIndex(parsed, this.environmentOrigin, this.userId)) {
        throw new Error('invalid sync index')
      }
      return parsed
    } catch {
      await mkdir(dirname(this.filePath), { recursive: true })
      await rename(
        this.filePath,
        `${this.filePath}.corrupt-${quarantineTimestamp(this.now)}`,
      )
      return createEmptyIndex(this.environmentOrigin, this.userId)
    }
  }

  async save(index, { beforeCommit = () => {} } = {}) {
    if (!isValidIndex(index, this.environmentOrigin, this.userId)) {
      throw new Error('invalid sync index')
    }

    const previousSave = saveQueues.get(this.filePath) ?? Promise.resolve()
    let releaseSave
    const currentSave = new Promise((resolve) => {
      releaseSave = resolve
    })
    saveQueues.set(this.filePath, currentSave)
    await previousSave

    try {
      await mkdir(this.directoryPath, { recursive: true })
      const temporaryPath = `${this.filePath}.tmp-${randomUUID()}`
      let handle
      try {
        handle = await open(temporaryPath, 'w', 0o600)
        await handle.writeFile(`${JSON.stringify(index, null, 2)}\n`, 'utf8')
        await handle.sync()
        await handle.close()
        handle = null
        await beforeCommit()
        await rename(temporaryPath, this.filePath)
      } catch (error) {
        await handle?.close().catch(() => {})
        await rm(temporaryPath, { force: true }).catch(() => {})
        throw error
      }
    } finally {
      releaseSave()
      if (saveQueues.get(this.filePath) === currentSave) {
        saveQueues.delete(this.filePath)
      }
    }
  }
}

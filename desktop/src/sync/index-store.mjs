import { createHash, randomUUID } from 'node:crypto'
import {
  mkdir,
  open,
  readFile,
  rename,
  rm,
} from 'node:fs/promises'
import { dirname, join } from 'node:path'

const SCHEMA_VERSION = 1
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

function isValidIndex(index, environmentOrigin, userId) {
  return (
    isPlainObject(index)
    && index.schemaVersion === SCHEMA_VERSION
    && index.environmentOrigin === environmentOrigin
    && index.userId === userId
    && isPlainObject(index.cursorBySelection)
    && isPlainObject(index.files)
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

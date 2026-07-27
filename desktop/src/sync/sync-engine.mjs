import { createHash, randomUUID } from 'node:crypto'
import { createReadStream } from 'node:fs'
import {
  access,
  chmod,
  mkdir,
  rename,
  rm,
  stat,
} from 'node:fs/promises'
import { dirname, posix } from 'node:path'

import { SyncApiError } from './api-client.mjs'
import { SyncIndexStore } from './index-store.mjs'
import {
  appendFilenameSuffix,
  buildRelativePath,
  resolvePhysicalPath,
  safeSegment,
} from './path-policy.mjs'

const MAX_MANIFEST_ITEMS = 200
const MAX_MANIFEST_PAGES = 10_000
const MAX_ID_LENGTH = 256
const MAX_CONCURRENT_DOWNLOADS = 2

class RunPausedError extends Error {
  constructor() {
    super('The synchronization run is no longer active')
    this.name = 'RunPausedError'
  }
}

class FileSyncError extends Error {
  constructor(code, message = code) {
    super(message)
    this.name = 'FileSyncError'
    this.code = code
  }
}

class AsyncMutex {
  constructor() {
    this.tail = Promise.resolve()
  }

  async run(callback) {
    let release
    const turn = new Promise((resolve) => {
      release = resolve
    })
    const previous = this.tail
    this.tail = previous.then(() => turn)
    await previous
    try {
      return await callback()
    } finally {
      release()
    }
  }
}

function createInitialState(localRoot = '') {
  return {
    status: 'paused',
    localRoot,
    selectedProjectRefs: [],
    completedFiles: 0,
    totalFiles: 0,
    failedFiles: 0,
    bytesDownloaded: 0,
    lastSuccessAt: '',
    message: '本地同步尚未启动，未下载任何文件',
  }
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function isNonEmptyString(value, maximumLength = MAX_ID_LENGTH) {
  return typeof value === 'string'
    && value.trim().length > 0
    && value.length <= maximumLength
}

function cloneRecord(record) {
  return record ? structuredClone(record) : undefined
}

function sourceKey(item) {
  return `${item.sourceType}:${item.sourceId}`
}

function itemSnapshot(item) {
  return {
    projectRef: item.projectRef,
    projectCode: item.projectCode,
    projectName: item.projectName,
    sourceType: item.sourceType,
    sourceId: item.sourceId,
    sourceRevision: item.sourceRevision,
    originalName: item.originalName,
    displayName: item.displayName,
    categoryKey: item.categoryKey,
    categoryName: item.categoryName,
    versionNo: item.versionNo,
    fileSize: item.fileSize,
    sha256: item.sha256,
    availability: item.availability,
    downloadPath: item.downloadPath,
  }
}

function validateManifestItem(item) {
  if (!isPlainObject(item)
    || !isNonEmptyString(item.projectRef)
    || typeof item.projectCode !== 'string'
    || typeof item.projectName !== 'string'
    || !isNonEmptyString(item.sourceType)
    || !isNonEmptyString(item.sourceId)
    || !isNonEmptyString(item.sourceRevision)
    || !isNonEmptyString(item.originalName, 1024)
    || typeof item.categoryName !== 'string'
    || !/^[a-f0-9]{64}$/i.test(item.sha256)
    || item.availability !== 'available'
    || !isNonEmptyString(item.downloadPath, 2048)
    || !Number.isSafeInteger(item.fileSize)
    || item.fileSize < 0) {
    throw new SyncApiError('Malformed manifest item', 'request_failed')
  }
}

function validateManifestPage(page) {
  if (!isPlainObject(page)
    || !Array.isArray(page.items)
    || page.items.length > MAX_MANIFEST_ITEMS
    || typeof page.hasMore !== 'boolean'
    || !isNonEmptyString(page.nextCursor, 4096)
    || !Number.isSafeInteger(page.policyVersion)
    || page.policyVersion <= 0) {
    throw new SyncApiError('Malformed manifest page', 'request_failed')
  }
  for (const item of page.items) validateManifestItem(item)
  return page
}

function validateIdentity(identity, rendererUserId) {
  if (!isPlainObject(identity)
    || !isNonEmptyString(identity.id)
    || identity.isActive !== true
    || identity.id !== rendererUserId) {
    throw new SyncApiError(
      'Authenticated user does not match the requested session',
      'permission_changed',
    )
  }
  return identity.id
}

function normalizePhysicalFiles(record) {
  const values = Array.isArray(record?.physicalFiles)
    ? record.physicalFiles
    : record?.relativePath
      ? [record.relativePath]
      : []
  return [...new Set(values.filter((value) => isNonEmptyString(value, 220)))]
}

function recordFromItem(item, relativePath, previous = null) {
  const physicalFiles = normalizePhysicalFiles(previous)
  if (!physicalFiles.includes(relativePath)) physicalFiles.push(relativePath)
  return {
    ...itemSnapshot(item),
    relativePath,
    physicalFiles,
    status: 'synced',
    lastErrorCode: null,
    pendingItem: null,
    lastVerifiedAt: new Date().toISOString(),
  }
}

function itemFromRecord(record) {
  if (isPlainObject(record?.pendingItem)) return record.pendingItem
  return itemSnapshot(record)
}

async function pathExists(filePath) {
  try {
    await access(filePath)
    return true
  } catch {
    return false
  }
}

async function sha256File(filePath) {
  const hash = createHash('sha256')
  for await (const chunk of createReadStream(filePath)) hash.update(chunk)
  return hash.digest('hex')
}

function manifestScopeKey(projectRefs) {
  return [...projectRefs].sort().join(',')
}

function errorCode(error) {
  return typeof error?.code === 'string' ? error.code : 'download_failed'
}

function isFatalApiError(error) {
  return error instanceof SyncApiError
    && ['waiting_for_login', 'permission_changed', 'offline'].includes(error.code)
}

export class SyncEngine {
  constructor({
    apiClient,
    appDataPath,
    environmentOrigin,
    emitState = () => {},
    now = () => new Date(),
    indexStoreFactory,
    hashFile = sha256File,
    prepareReadOnly = (filePath) => chmod(filePath, 0o444),
  }) {
    if (!apiClient
      || !isNonEmptyString(appDataPath, 4096)
      || !isNonEmptyString(environmentOrigin, 2048)
      || typeof emitState !== 'function') {
      throw new Error('invalid synchronization engine configuration')
    }
    this.apiClient = apiClient
    this.appDataPath = appDataPath
    this.environmentOrigin = environmentOrigin
    this.emitState = emitState
    this.now = now
    this.indexStoreFactory = indexStoreFactory || ((userId) => new SyncIndexStore({
      appDataPath,
      environmentOrigin,
      userId,
      now,
    }))
    this.hashFile = hashFile
    this.prepareReadOnly = prepareReadOnly
    this.state = createInitialState()
    this.activeRun = null
    this.nextRunId = 1
    this.locks = new Map()
  }

  getState() {
    return structuredClone(this.state)
  }

  setLocalRoot(localRoot) {
    if (!isNonEmptyString(localRoot, 4096)) {
      throw new Error('invalid local sync root')
    }
    this.cancelActiveRun()
    this.state = createInitialState(localRoot)
    this.state.message = '已选择本地资料文件夹，尚未开始下载'
    this.emit()
    return this.getState()
  }

  pause() {
    this.cancelActiveRun()
    this.state = {
      ...this.state,
      status: 'paused',
      message: '本地同步已暂停，登录凭证已从桌面内存清除',
    }
    this.emit()
    return this.getState()
  }

  clearSession() {
    this.cancelActiveRun()
    this.state = createInitialState(this.state.localRoot)
    this.state.message = '桌面同步会话已清除'
    this.emit()
    return this.getState()
  }

  hasActiveSession() {
    return Boolean(this.activeRun?.token)
  }

  async start({ authToken, userId, projectRefs }) {
    if (!this.state.localRoot) {
      throw new Error('sync folder is not selected')
    }

    this.cancelActiveRun()
    const run = {
      id: this.nextRunId++,
      token: authToken,
      cancelled: false,
      root: this.state.localRoot,
      commitMutex: new AsyncMutex(),
      authoritativeUserId: null,
      reservedBytes: 0,
    }
    this.activeRun = run
    let initialEmissionCompleted = false

    this.state = {
      ...createInitialState(run.root),
      status: 'checking_policy',
      selectedProjectRefs: [...projectRefs],
      message: '正在检查桌面同步策略',
    }

    try {
      this.emit()
      initialEmissionCompleted = true

      const identity = await this.apiClient.getCurrentUser(run.token)
      this.assertActive(run)
      run.authoritativeUserId = validateIdentity(identity, userId)

      await mkdir(run.root, { recursive: true })
      this.assertActive(run)
      const physicalRoot = await resolvePhysicalPath(run.root, '.')
      this.assertActive(run)

      const lockKey = `${run.authoritativeUserId}\n${physicalRoot.toLocaleLowerCase('en-US')}`
      const lock = this.getLock(lockKey)
      await lock.run(async () => {
        this.assertActive(run)
        await this.runLocked(run, projectRefs)
      })
    } catch (error) {
      if (!initialEmissionCompleted) throw error
      if (error instanceof RunPausedError) return this.getState()
      this.applyRunError(run, error)
    } finally {
      run.token = null
      if (this.activeRun === run) this.activeRun = null
    }

    return this.getState()
  }

  async runLocked(run, projectRefs) {
    let policy = await this.apiClient.getPolicy(run.token)
    this.assertActive(run)
    if (policy.enabled !== true || policy.enabledForCurrentUser !== true) {
      this.state = {
        ...this.state,
        status: 'disabled',
        message: '当前账号未启用桌面资料同步',
      }
      this.emitIfActive(run)
      return
    }

    const projects = await this.apiClient.getProjectRoots(run.token)
    this.assertActive(run)
    const accessibleRefs = new Set(projects.map((project) => project.projectRef))
    if (projectRefs.some((projectRef) => !accessibleRefs.has(projectRef))) {
      throw new SyncApiError('Project permission changed', 'permission_changed')
    }

    const store = this.indexStoreFactory(run.authoritativeUserId)
    const index = await store.load()
    this.assertActive(run)
    index.userId = run.authoritativeUserId
    index.files ??= {}
    index.cursorBySelection ??= {}

    this.state.status = 'syncing'
    this.state.message = '正在同步服务器资料到本地'
    this.emitIfActive(run)

    const processed = new Set()
    await this.retryFailures(run, store, index, policy, processed)

    const scopeKey = manifestScopeKey(projectRefs)
    let cursor = index.cursorBySelection[scopeKey] || ''
    const seenCursors = new Set(cursor === '' ? [] : [cursor])
    let pageCount = 0

    while (true) {
      this.assertActive(run)
      if (++pageCount > MAX_MANIFEST_PAGES) {
        throw new SyncApiError(
          'Manifest pagination exceeded the safety limit',
          'request_failed',
        )
      }

      const page = validateManifestPage(
        await this.apiClient.getManifest(run.token, {
          projectRefs,
          cursor,
          limit: MAX_MANIFEST_ITEMS,
        }),
      )
      this.assertActive(run)
      if (page.policyVersion !== policy.policyVersion) {
        policy = await this.apiClient.getPolicy(run.token)
        this.assertActive(run)
        if (policy.enabled !== true
          || policy.enabledForCurrentUser !== true
          || page.policyVersion !== policy.policyVersion) {
          throw new SyncApiError(
            'Desktop policy changed during synchronization',
            'permission_changed',
          )
        }
      }
      if (page.hasMore
        && (page.nextCursor === cursor || seenCursors.has(page.nextCursor))) {
        throw new SyncApiError('Manifest cursor did not advance', 'request_failed')
      }

      this.state.totalFiles += page.items.filter(
        (item) => !processed.has(sourceKey(item)),
      ).length
      this.emitIfActive(run)

      await this.processItems(run, store, index, policy, page.items, processed)
      this.assertActive(run)

      await this.commitCursor(run, store, index, scopeKey, page.nextCursor)
      cursor = page.nextCursor
      seenCursors.add(cursor)
      if (!page.hasMore) break
    }

    this.assertActive(run)
    this.state = {
      ...this.state,
      status: this.state.failedFiles > 0 ? 'partial_failure' : 'completed',
      lastSuccessAt: this.state.failedFiles > 0 ? '' : this.now().toISOString(),
      message: this.state.failedFiles > 0
        ? '部分资料同步失败，可稍后手动重试'
        : '服务器资料已同步到本地',
    }
    this.emitIfActive(run)
  }

  async retryFailures(run, store, index, policy, processed) {
    const records = Object.values(index.files)
      .filter((record) => ['failed', 'update_failed'].includes(record?.status))

    this.state.totalFiles += records.length
    this.emitIfActive(run)

    for (const record of records) {
      this.assertActive(run)
      const item = itemFromRecord(record)
      try {
        await this.processItem(run, store, index, policy, item)
        const updated = index.files[sourceKey(item)]
        if (updated?.sourceRevision === item.sourceRevision
          && ['synced', 'local_modified'].includes(updated.status)) {
          processed.add(sourceKey(item))
        }
      } catch (error) {
        if (error instanceof RunPausedError || isFatalApiError(error)) throw error
        await this.recordFailure(run, store, index, item, error)
      }
    }
  }

  async processItems(run, store, index, policy, items, processed) {
    const queue = items.filter((item) => !processed.has(sourceKey(item)))
    let nextIndex = 0
    let fatalError = null

    const worker = async () => {
      while (fatalError === null) {
        const itemIndex = nextIndex++
        if (itemIndex >= queue.length) return
        const item = queue[itemIndex]
        try {
          await this.processItem(run, store, index, policy, item)
          processed.add(sourceKey(item))
        } catch (error) {
          if (error instanceof RunPausedError || isFatalApiError(error)) {
            fatalError = error
            return
          }
          await this.recordFailure(run, store, index, item, error)
          processed.add(sourceKey(item))
        }
      }
    }

    const workers = Array.from(
      { length: Math.min(MAX_CONCURRENT_DOWNLOADS, queue.length) },
      () => worker(),
    )
    await Promise.all(workers)
    if (fatalError) throw fatalError
  }

  async processItem(run, store, index, policy, item) {
    this.assertActive(run)
    if (!this.state.selectedProjectRefs.includes(item.projectRef)) {
      throw new SyncApiError(
        'Manifest item is outside the selected project scope',
        'permission_changed',
      )
    }
    if (item.availability !== 'available') {
      throw new FileSyncError('file_unavailable')
    }
    if (item.fileSize > Number(policy.maxFileSizeBytes)
      || !Number.isSafeInteger(policy.maxLocalStorageBytes)
      || policy.maxLocalStorageBytes < 0) {
      throw new FileSyncError('policy_size_limit')
    }

    const key = sourceKey(item)
    const skipped = await run.commitMutex.run(async () => {
      this.assertActive(run)
      const record = index.files[key]
      if (record?.sourceRevision !== item.sourceRevision || !record.relativePath) return false

      const filePath = await resolvePhysicalPath(run.root, record.relativePath)
      this.assertActive(run)
      if (!await pathExists(filePath)) return false
      const localHash = await this.hashFile(filePath)
      this.assertActive(run)
      if (localHash !== item.sha256) return false

      const previous = cloneRecord(record)
      index.files[key] = {
        ...record,
        status: record.status === 'local_modified'
          ? 'local_modified'
          : 'synced',
        lastErrorCode: null,
        pendingItem: null,
        lastVerifiedAt: new Date().toISOString(),
      }
      try {
        await this.saveIndex(run, store, index)
      } catch (error) {
        index.files[key] = previous
        await this.persistRollback(store, index, error)
        throw error
      }
      this.assertActive(run)
      this.state.completedFiles += 1
      this.emitIfActive(run)
      return true
    })
    if (skipped) return

    let reservedBytes = 0
    await run.commitMutex.run(async () => {
      this.assertActive(run)
      const record = index.files[key]
      if (normalizePhysicalFiles(record).length > 0) return
      const usedBytes = await this.indexedStorageBytes(run, index)
      this.assertActive(run)
      if (usedBytes + run.reservedBytes + item.fileSize > policy.maxLocalStorageBytes) {
        throw new FileSyncError('policy_storage_limit')
      }
      reservedBytes = item.fileSize
      run.reservedBytes += reservedBytes
    })

    const partRelativePath = `.jiqing-part-${safeSegment(item.sourceId, { maximumLength: 40 })}-${randomUUID()}`
    const partPath = await resolvePhysicalPath(run.root, partRelativePath)
    this.assertActive(run)

    try {
      await this.apiClient.download(
        run.token,
        item.downloadPath,
        partPath,
        (downloadedBytes) => {
          this.assertActive(run)
          if (!Number.isSafeInteger(downloadedBytes)
            || downloadedBytes < 0
            || downloadedBytes > item.fileSize) {
            throw new FileSyncError('invalid_download_progress')
          }
          run.downloadedByItem ??= new Map()
          const previousBytes = run.downloadedByItem.get(key) ?? 0
          const additionalBytes = Math.max(0, downloadedBytes - previousBytes)
          run.downloadedByItem.set(key, Math.max(previousBytes, downloadedBytes))
          if (additionalBytes > 0) {
            this.state.bytesDownloaded += additionalBytes
            this.emitIfActive(run)
          }
        },
      )
      this.assertActive(run)

      const partStats = await stat(partPath)
      this.assertActive(run)
      if (partStats.size !== item.fileSize) throw new FileSyncError('size_mismatch')
      const downloadedHash = await this.hashFile(partPath)
      this.assertActive(run)
      if (downloadedHash !== item.sha256) throw new FileSyncError('integrity_mismatch')

      await run.commitMutex.run(async () => {
        await this.publishItem(
          run,
          store,
          index,
          policy,
          item,
          partPath,
          reservedBytes,
        )
      })
    } finally {
      await rm(partPath, { force: true }).catch(() => {})
      if (reservedBytes > 0) {
        await run.commitMutex.run(async () => {
          run.reservedBytes = Math.max(0, run.reservedBytes - reservedBytes)
        })
      }
    }
  }

  async publishItem(run, store, index, policy, item, partPath, reservedBytes) {
    this.assertActive(run)
    const key = sourceKey(item)
    const previousRecord = cloneRecord(index.files[key])
    const desiredRelativePath = buildRelativePath(item)
    const destination = await this.chooseDestination(
      run,
      index,
      key,
      desiredRelativePath,
      previousRecord,
    )
    this.assertActive(run)

    const destinationDirectory = await resolvePhysicalPath(
      run.root,
      posix.dirname(destination.relativePath),
    )
    this.assertActive(run)
    await mkdir(destinationDirectory, { recursive: true })
    this.assertActive(run)
    await resolvePhysicalPath(run.root, posix.dirname(destination.relativePath))
    this.assertActive(run)

    const destinationPath = await resolvePhysicalPath(run.root, destination.relativePath)
    this.assertActive(run)

    const usedBytes = await this.indexedStorageBytes(run, index)
    this.assertActive(run)
    const replacedSize = destination.ownedExisting
      ? await stat(destinationPath).then((details) => details.size).catch(() => 0)
      : 0
    this.assertActive(run)
    const otherReservations = Math.max(0, run.reservedBytes - reservedBytes)
    if (usedBytes
      + otherReservations
      - replacedSize
      + item.fileSize > policy.maxLocalStorageBytes) {
      throw new FileSyncError('policy_storage_limit')
    }

    const currentExists = await pathExists(destinationPath)
    this.assertActive(run)
    if (destination.ownedExisting) {
      if (!currentExists) throw new FileSyncError('path_changed_during_sync')
      const currentHash = await this.hashFile(destinationPath)
      this.assertActive(run)
      if (currentHash !== destination.expectedHash) {
        throw new FileSyncError('path_changed_during_sync')
      }
    } else if (currentExists) {
      throw new FileSyncError('path_conflict_race')
    }

    await this.prepareReadOnly(partPath)
    this.assertActive(run)
    await resolvePhysicalPath(run.root, destination.relativePath)
    this.assertActive(run)

    const backupPath = destination.ownedExisting
      ? `${destinationPath}.jiqing-backup-${randomUUID()}`
      : null
    let backupCreated = false
    let destinationPublished = false

    try {
      if (backupPath) {
        this.assertActive(run)
        await rename(destinationPath, backupPath)
        backupCreated = true
        this.assertActive(run)
      }

      this.assertActive(run)
      await rename(partPath, destinationPath)
      destinationPublished = true
      this.assertActive(run)

      index.files[key] = {
        ...recordFromItem(item, destination.relativePath, previousRecord),
        status: destination.conflict ? 'local_modified' : 'synced',
      }
      this.assertActive(run)
      await this.saveIndex(run, store, index)
      this.assertActive(run)

      if (backupCreated) {
        await rm(backupPath, { force: true })
        this.assertActive(run)
      }

      this.state.completedFiles += 1
      this.emitIfActive(run)
    } catch (error) {
      if (previousRecord === undefined) delete index.files[key]
      else index.files[key] = previousRecord
      await this.persistRollback(store, index, error)

      if (destinationPublished) {
        await rm(destinationPath, { force: true }).catch(() => {})
      }
      if (backupCreated) {
        await rename(backupPath, destinationPath).catch(() => {})
      }
      throw error
    }
  }

  async chooseDestination(run, index, key, desiredRelativePath, previousRecord) {
    const previousRelativePath = previousRecord?.relativePath
    if (previousRelativePath) {
      const previousPath = await resolvePhysicalPath(run.root, previousRelativePath)
      this.assertActive(run)
      if (await pathExists(previousPath)) {
        const previousHash = await this.hashFile(previousPath)
        this.assertActive(run)
        if (previousHash === previousRecord.sha256) {
          return {
            relativePath: previousRelativePath,
            ownedExisting: true,
            expectedHash: previousHash,
            conflict: false,
          }
        }
      }
    }

    const desiredPath = await resolvePhysicalPath(run.root, desiredRelativePath)
    this.assertActive(run)
    if (!await pathExists(desiredPath)
      && !this.isIndexedPhysical(index, desiredRelativePath, key)) {
      return {
        relativePath: desiredRelativePath,
        ownedExisting: false,
        expectedHash: null,
        conflict: false,
      }
    }

    for (let sequence = 1; sequence <= 10_000; sequence += 1) {
      const suffix = sequence === 1 ? '_服务器新版' : `_服务器新版_${sequence}`
      const candidate = appendFilenameSuffix(desiredRelativePath, suffix)
      const candidatePath = await resolvePhysicalPath(run.root, candidate)
      this.assertActive(run)
      if (!await pathExists(candidatePath) && !this.isIndexedPhysical(index, candidate, key)) {
        return {
          relativePath: candidate,
          ownedExisting: false,
          expectedHash: null,
          conflict: true,
        }
      }
    }
    throw new FileSyncError('path_conflict_exhausted')
  }

  isIndexedPhysical(index, relativePath, exceptKey = null) {
    return Object.entries(index.files).some(([key, record]) => (
      key !== exceptKey && normalizePhysicalFiles(record).includes(relativePath)
    ))
  }

  async indexedStorageBytes(run, index) {
    const relativePaths = new Set()
    for (const record of Object.values(index.files)) {
      for (const relativePath of normalizePhysicalFiles(record)) {
        relativePaths.add(relativePath)
      }
    }

    let total = 0
    for (const relativePath of relativePaths) {
      const filePath = await resolvePhysicalPath(run.root, relativePath)
      this.assertActive(run)
      const details = await stat(filePath).catch(() => null)
      this.assertActive(run)
      if (details?.isFile()) total += details.size
    }
    return total
  }

  async recordFailure(run, store, index, item, error) {
    await run.commitMutex.run(async () => {
      this.assertActive(run)
      const key = sourceKey(item)
      const previous = cloneRecord(index.files[key])
      const trustedBaseline = previous?.relativePath
        && isNonEmptyString(previous.sha256, 128)
        && previous.status !== 'failed'

      if (trustedBaseline) {
        index.files[key] = {
          ...previous,
          status: 'update_failed',
          lastErrorCode: errorCode(error),
          pendingItem: itemSnapshot(item),
        }
      } else {
        index.files[key] = {
          ...itemSnapshot(item),
          relativePath: previous?.relativePath ?? null,
          physicalFiles: normalizePhysicalFiles(previous),
          status: 'failed',
          lastErrorCode: errorCode(error),
          pendingItem: itemSnapshot(item),
        }
      }

      try {
        this.assertActive(run)
        await this.saveIndex(run, store, index)
      } catch (saveError) {
        if (previous === undefined) delete index.files[key]
        else index.files[key] = previous
        await this.persistRollback(store, index, saveError)
        throw saveError
      }

      this.assertActive(run)
      this.state.failedFiles += 1
      this.emitIfActive(run)
    })
  }

  async commitCursor(run, store, index, scopeKey, nextCursor) {
    await run.commitMutex.run(async () => {
      this.assertActive(run)
      const hadCursor = Object.hasOwn(index.cursorBySelection, scopeKey)
      const previousCursor = index.cursorBySelection[scopeKey]
      index.cursorBySelection[scopeKey] = nextCursor
      try {
        this.assertActive(run)
        await this.saveIndex(run, store, index)
      } catch (error) {
        if (hadCursor) index.cursorBySelection[scopeKey] = previousCursor
        else delete index.cursorBySelection[scopeKey]
        await this.persistRollback(store, index, error)
        throw error
      }
      this.assertActive(run)
    })
  }

  async saveIndex(run, store, index) {
    this.assertActive(run)
    await store.save(index, {
      beforeCommit: () => this.assertActive(run),
    })
    this.assertActive(run)
  }

  async persistRollback(store, index, originalError) {
    try {
      await store.save(index)
    } catch (rollbackError) {
      originalError.rollbackError = rollbackError
    }
  }

  getLock(key) {
    let lock = this.locks.get(key)
    if (!lock) {
      lock = new AsyncMutex()
      this.locks.set(key, lock)
    }
    return lock
  }

  cancelActiveRun() {
    if (!this.activeRun) return
    this.activeRun.cancelled = true
    this.activeRun.token = null
    this.apiClient.abortAll()
  }

  assertActive(run) {
    if (this.activeRun !== run || run.cancelled || !run.token) {
      throw new RunPausedError()
    }
  }

  emitIfActive(run) {
    this.assertActive(run)
    this.emit()
  }

  emit() {
    this.emitState(this.getState())
  }

  applyRunError(run, error) {
    if (this.activeRun !== run) return
    const statusByCode = {
      waiting_for_login: 'waiting_for_login',
      permission_changed: 'permission_changed',
      offline: 'offline',
    }
    const status = statusByCode[errorCode(error)] ?? 'partial_failure'
    this.state = {
      ...this.state,
      status,
      message: {
        waiting_for_login: '登录状态已失效，请重新登录后手动开始同步',
        permission_changed: '资料同步权限已变化，请重新确认同步范围',
        offline: '当前无法连接服务器，同步未完成',
        partial_failure: '部分资料同步失败，可稍后手动重试',
      }[status],
    }
    this.emitIfActive(run)
  }
}

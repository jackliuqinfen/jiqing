import { createHash } from 'node:crypto'
import { createReadStream } from 'node:fs'
import {
  access,
  chmod,
  mkdir,
  rename,
  rm,
  stat,
} from 'node:fs/promises'
import { dirname } from 'node:path'

import { SyncApiError } from './api-client.mjs'
import { SyncIndexStore } from './index-store.mjs'
import {
  appendFilenameSuffix,
  buildRelativePath,
  resolveWithinRoot,
  safeSegment,
} from './path-policy.mjs'

class RunPausedError extends Error {}

function initialState(localRoot = '') {
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

function publicState(state) {
  return Object.freeze({
    ...state,
    selectedProjectRefs: Object.freeze([...state.selectedProjectRefs]),
  })
}

function selectionKey(projectRefs) {
  return [...projectRefs].sort().join(',')
}

async function pathExists(path) {
  try {
    await access(path)
    return true
  } catch {
    return false
  }
}

async function sha256File(path) {
  const hash = createHash('sha256')
  for await (const chunk of createReadStream(path)) hash.update(chunk)
  return hash.digest('hex')
}

function manifestItemIsUsable(item) {
  return (
    item
    && typeof item === 'object'
    && typeof item.projectRef === 'string'
    && typeof item.projectCode === 'string'
    && typeof item.projectName === 'string'
    && typeof item.sourceType === 'string'
    && typeof item.sourceId === 'string'
    && typeof item.sourceRevision === 'string'
    && typeof item.originalName === 'string'
    && typeof item.categoryName === 'string'
    && Number.isSafeInteger(item.fileSize)
    && item.fileSize >= 0
    && typeof item.sha256 === 'string'
    && /^[a-f0-9]{64}$/i.test(item.sha256)
    && item.availability === 'available'
    && typeof item.downloadPath === 'string'
    && item.downloadPath.length > 0
  )
}

function recordFromItem(item, {
  relativePath,
  lastVerifiedAt,
  status,
  lastErrorCode = '',
}) {
  return {
    projectRef: item.projectRef,
    projectCode: item.projectCode,
    projectName: item.projectName,
    sourceType: item.sourceType,
    sourceId: item.sourceId,
    sourceRevision: item.sourceRevision,
    originalName: item.originalName,
    displayName: item.displayName || item.originalName,
    categoryKey: item.categoryKey || '',
    categoryName: item.categoryName,
    versionNo: item.versionNo ?? null,
    downloadPath: item.downloadPath,
    sha256: item.sha256,
    relativePath,
    fileSize: item.fileSize,
    lastVerifiedAt,
    status,
    ...(lastErrorCode ? { lastErrorCode } : {}),
  }
}

function itemFromRecord(record) {
  return {
    projectRef: record.projectRef,
    projectCode: record.projectCode,
    projectName: record.projectName,
    sourceType: record.sourceType,
    sourceId: record.sourceId,
    sourceRevision: record.sourceRevision,
    originalName: record.originalName,
    displayName: record.displayName,
    categoryKey: record.categoryKey,
    categoryName: record.categoryName,
    versionNo: record.versionNo,
    fileSize: record.fileSize,
    sha256: record.sha256,
    availability: 'available',
    downloadPath: record.downloadPath,
  }
}

function conflictRelativePath(relativePath, number = 1) {
  const suffix = number === 1 ? '_服务器新版' : `_服务器新版_${number}`
  return appendFilenameSuffix(relativePath, suffix)
}

export class SyncEngine {
  constructor({
    apiClient,
    appDataPath,
    environmentOrigin,
    emitState = () => {},
    now = () => new Date(),
    indexStoreFactory,
  }) {
    if (
      !apiClient
      || typeof appDataPath !== 'string'
      || !appDataPath
      || typeof environmentOrigin !== 'string'
      || !environmentOrigin
      || typeof emitState !== 'function'
    ) {
      throw new Error('invalid synchronization engine configuration')
    }
    this.apiClient = apiClient
    this.appDataPath = appDataPath
    this.environmentOrigin = environmentOrigin
    this.emitState = emitState
    this.now = now
    this.indexStoreFactory = indexStoreFactory || ((userId) => (
      new SyncIndexStore({
        appDataPath: this.appDataPath,
        environmentOrigin: this.environmentOrigin,
        userId,
        now: this.now,
      })
    ))
    this.state = initialState()
    this.token = null
    this.runId = 0
  }

  getState() {
    return publicState(this.state)
  }

  hasActiveSession() {
    return this.token !== null
  }

  setLocalRoot(localRoot) {
    if (typeof localRoot !== 'string' || !localRoot.trim()) {
      throw new Error('invalid local sync root')
    }
    this.updateState({
      localRoot,
      message: '已选择本地资料文件夹，尚未开始下载',
    })
    return this.getState()
  }

  pause() {
    this.runId += 1
    this.token = null
    this.apiClient.abortAll?.()
    this.updateState({
      status: 'paused',
      message: '本地同步已暂停，登录凭证已从桌面内存清除',
    })
    return this.getState()
  }

  clearSession() {
    const localRoot = this.state.localRoot
    this.runId += 1
    this.token = null
    this.apiClient.abortAll?.()
    this.state = initialState(localRoot)
    this.state.message = '桌面同步会话已清除'
    this.emit()
  }

  async start({ authToken, userId, projectRefs }) {
    if (!this.state.localRoot) throw new Error('sync folder is not selected')
    if (this.token !== null) this.apiClient.abortAll?.()
    const runId = ++this.runId
    this.token = authToken
    this.state = {
      ...initialState(this.state.localRoot),
      status: 'checking_policy',
      selectedProjectRefs: [...projectRefs],
      message: '正在检查桌面同步策略',
    }
    this.emit()

    try {
      await this.run(runId, userId, projectRefs)
    } catch (error) {
      if (error instanceof RunPausedError || runId !== this.runId) {
        return this.getState()
      }
      this.apiClient.abortAll?.()
      const status = error instanceof SyncApiError
        ? error.code
        : 'offline'
      if ([
        'waiting_for_login',
        'permission_changed',
        'offline',
      ].includes(status)) {
        this.updateState({
          status,
          message: {
            waiting_for_login: '登录状态已失效，请重新登录后手动开始同步',
            permission_changed: '资料同步权限已变化，请重新确认同步范围',
            offline: '当前无法连接服务器，同步未完成',
          }[status],
        })
      } else {
        this.updateState({
          status: 'partial_failure',
          message: '部分资料同步失败，可稍后手动重试',
        })
      }
    } finally {
      if (runId === this.runId) this.token = null
    }
    return this.getState()
  }

  async run(runId, userId, projectRefs) {
    this.assertActive(runId)
    let policy = await this.apiClient.getPolicy(this.token)
    this.assertActive(runId)
    if (policy.enabled !== true || policy.enabledForCurrentUser !== true) {
      this.updateState({
        status: 'disabled',
        message: '当前账号未启用桌面资料同步',
      })
      return
    }

    const roots = await this.apiClient.getProjectRoots(this.token)
    this.assertActive(runId)
    const accessibleRefs = new Set(roots.map((root) => root.projectRef))
    if (projectRefs.some((reference) => !accessibleRefs.has(reference))) {
      throw new SyncApiError('permission changed', 'permission_changed')
    }

    const store = this.indexStoreFactory(userId)
    const index = await store.load()
    const storage = {
      used: await this.indexedStorageBytes(index),
    }
    const processedRevisions = new Map()
    this.updateState({
      status: 'syncing',
      message: '正在同步服务器资料到本地',
    })

    const retryItems = []
    for (const [key, record] of Object.entries(index.files)) {
      if (!projectRefs.includes(record.projectRef)) continue
      let missing = true
      try {
        missing = !await pathExists(
          resolveWithinRoot(this.state.localRoot, record.relativePath),
        )
      } catch {
        missing = true
      }
      if (missing || record.status === 'failed') {
        retryItems.push(itemFromRecord(record))
        processedRevisions.set(key, record.sourceRevision)
      }
    }
    if (retryItems.length > 0) {
      this.updateState({
        totalFiles: this.state.totalFiles + retryItems.length,
      })
      try {
        await this.processItems(
          runId,
          retryItems,
          index,
          policy,
          storage,
        )
      } finally {
        await store.save(index)
      }
    }

    const cursorKey = selectionKey(projectRefs)
    let cursor = index.cursorBySelection[cursorKey] || ''
    while (true) {
      this.assertActive(runId)
      const manifest = await this.apiClient.getManifest(this.token, {
        projectRefs,
        cursor,
        limit: 200,
      })
      this.assertActive(runId)
      if (manifest.policyVersion !== policy.policyVersion) {
        policy = await this.apiClient.getPolicy(this.token)
        this.assertActive(runId)
        if (policy.enabled !== true || policy.enabledForCurrentUser !== true) {
          throw new SyncApiError('permission changed', 'permission_changed')
        }
        if (policy.policyVersion !== manifest.policyVersion) {
          throw new SyncApiError('permission changed', 'permission_changed')
        }
      }

      const items = manifest.items.filter((item) => {
        const key = `${item.sourceType}:${item.sourceId}`
        return processedRevisions.get(key) !== item.sourceRevision
      })
      this.updateState({
        totalFiles: this.state.totalFiles + items.length,
      })
      try {
        await this.processItems(runId, items, index, policy, storage)
      } catch (error) {
        await store.save(index)
        throw error
      }
      for (const item of items) {
        processedRevisions.set(
          `${item.sourceType}:${item.sourceId}`,
          item.sourceRevision,
        )
      }

      index.cursorBySelection[cursorKey] = manifest.nextCursor
      await store.save(index)
      cursor = manifest.nextCursor
      if (!manifest.hasMore) break
    }

    this.assertActive(runId)
    const failed = this.state.failedFiles > 0
    this.updateState({
      status: failed ? 'partial_failure' : 'completed',
      lastSuccessAt: failed ? '' : this.now().toISOString(),
      message: failed
        ? '部分资料同步失败，可稍后手动重试'
        : '服务器资料已同步到本地',
    })
  }

  async indexedStorageBytes(index) {
    let total = 0
    const counted = new Set()
    for (const record of Object.values(index.files)) {
      try {
        const path = resolveWithinRoot(this.state.localRoot, record.relativePath)
        if (counted.has(path)) continue
        const metadata = await stat(path)
        if (metadata.isFile()) {
          total += metadata.size
          counted.add(path)
        }
      } catch {
        // Missing and invalid records do not consume synchronized storage.
      }
    }
    return total
  }

  async processItems(runId, items, index, policy, storage) {
    let nextIndex = 0
    let fatalError = null
    const worker = async () => {
      while (nextIndex < items.length && !fatalError) {
        const item = items[nextIndex]
        nextIndex += 1
        try {
          await this.processItem(runId, item, index, policy, storage)
        } catch (error) {
          if (
            error instanceof RunPausedError
            || (
              error instanceof SyncApiError
              && ['waiting_for_login', 'permission_changed', 'offline']
                .includes(error.code)
            )
          ) {
            fatalError ||= error
            this.apiClient.abortAll?.()
          } else {
            this.recordFailure(index, item, 'download_failed')
          }
        }
      }
    }
    await Promise.all([worker(), worker()])
    if (fatalError) throw fatalError
  }

  async processItem(runId, item, index, policy, storage) {
    this.assertActive(runId)
    const key = `${item?.sourceType}:${item?.sourceId}`
    if (!manifestItemIsUsable(item)) {
      this.recordFailure(index, item, 'invalid_manifest_item')
      return
    }
    if (!this.state.selectedProjectRefs.includes(item.projectRef)) {
      this.updateState({
        failedFiles: this.state.failedFiles + 1,
      })
      return
    }
    if (
      item.fileSize > Number(policy.maxFileSizeBytes)
      || !Number.isSafeInteger(policy.maxLocalStorageBytes)
      || policy.maxLocalStorageBytes < 0
    ) {
      this.recordFailure(index, item, 'policy_size_limit')
      return
    }

    const desiredRelativePath = buildRelativePath(item)
    const record = index.files[key]
    let targetRelativePath = desiredRelativePath
    let existingSize = 0
    let trustedExistingHash = ''
    let conflict = false

    if (record) {
      let indexedPath
      try {
        indexedPath = resolveWithinRoot(
          this.state.localRoot,
          record.relativePath,
        )
      } catch {
        indexedPath = null
      }
      if (indexedPath && await pathExists(indexedPath)) {
        const metadata = await stat(indexedPath)
        existingSize = metadata.size
        trustedExistingHash = await sha256File(indexedPath)
        if (trustedExistingHash !== record.sha256) {
          conflict = true
          targetRelativePath = await this.availableConflictPath(
            desiredRelativePath,
          )
        } else if (
          record.sourceRevision === item.sourceRevision
          && trustedExistingHash === item.sha256
        ) {
          index.files[key] = recordFromItem(item, {
            relativePath: record.relativePath,
            lastVerifiedAt: this.now().toISOString(),
            status: record.status === 'local_modified'
              ? 'local_modified'
              : 'synced',
          })
          await chmod(indexedPath, 0o444)
          this.updateState({
            completedFiles: this.state.completedFiles + 1,
          })
          return
        } else {
          targetRelativePath = (
            record.relativePath === desiredRelativePath
            || record.status === 'local_modified'
          )
            ? record.relativePath
            : desiredRelativePath
        }
      } else if (record.sourceRevision === item.sourceRevision) {
        targetRelativePath = record.relativePath
      }
    }

    const targetPath = resolveWithinRoot(
      this.state.localRoot,
      targetRelativePath,
    )
    if (
      await pathExists(targetPath)
      && (!record || targetRelativePath !== record.relativePath)
    ) {
      conflict = true
      targetRelativePath = await this.availableConflictPath(
        desiredRelativePath,
      )
    }
    const finalPath = resolveWithinRoot(
      this.state.localRoot,
      targetRelativePath,
    )
    const replacingTrustedFile = (
      record
      && targetRelativePath === record.relativePath
      && trustedExistingHash === record.sha256
    )
    const additionalBytes = replacingTrustedFile
      ? Math.max(0, item.fileSize - existingSize)
      : item.fileSize
    if (storage.used + additionalBytes > policy.maxLocalStorageBytes) {
      this.recordFailure(index, item, 'policy_storage_limit')
      return
    }
    storage.used += additionalBytes

    await mkdir(dirname(finalPath), { recursive: true })
    const partPath = resolveWithinRoot(
      dirname(finalPath),
      `.jiqing-part-${safeSegment(item.sourceId)}`,
    )
    await rm(partPath, { force: true })
    let downloadedBytes = 0
    let accountedBytes = 0
    try {
      await this.apiClient.download(
        this.token,
        item.downloadPath,
        partPath,
        (received) => {
          downloadedBytes = received
          if (runId !== this.runId || this.token === null) return
          if (!Number.isSafeInteger(received) || received > item.fileSize) {
            throw new SyncApiError(
              'download exceeded manifest size',
              'request_failed',
            )
          }
          const additional = Math.max(0, received - accountedBytes)
          accountedBytes = Math.max(accountedBytes, received)
          if (additional > 0) {
            this.updateState({
              bytesDownloaded: this.state.bytesDownloaded + additional,
            })
          }
        },
      )
      this.assertActive(runId)
      const partMetadata = await stat(partPath)
      const downloadedHash = await sha256File(partPath)
      if (
        downloadedBytes !== item.fileSize
        || partMetadata.size !== item.fileSize
        || downloadedHash !== item.sha256
      ) {
        await rm(partPath, { force: true })
        storage.used -= additionalBytes
        this.recordFailure(index, item, 'integrity_mismatch')
        return
      }

      if (replacingTrustedFile) {
        const currentHash = await sha256File(finalPath)
        if (currentHash !== trustedExistingHash) {
          conflict = true
          const conflictPath = await this.availableConflictPath(
            desiredRelativePath,
          )
          targetRelativePath = conflictPath
        } else {
          await chmod(finalPath, 0o600).catch(() => {})
        }
      }
      const destination = resolveWithinRoot(
        this.state.localRoot,
        targetRelativePath,
      )
      await mkdir(dirname(destination), { recursive: true })
      await rename(partPath, destination)
      await chmod(destination, 0o444)
      index.files[key] = recordFromItem(item, {
        relativePath: targetRelativePath,
        lastVerifiedAt: this.now().toISOString(),
        status: conflict ? 'local_modified' : 'synced',
      })
      this.updateState({
        completedFiles: this.state.completedFiles + 1,
      })
    } catch (error) {
      await rm(partPath, { force: true }).catch(() => {})
      storage.used -= additionalBytes
      throw error
    }
  }

  async availableConflictPath(desiredRelativePath) {
    for (let number = 1; number < 10_000; number += 1) {
      const candidate = conflictRelativePath(desiredRelativePath, number)
      const path = resolveWithinRoot(this.state.localRoot, candidate)
      if (!await pathExists(path)) return candidate
    }
    throw new Error('unable to allocate conflict filename')
  }

  recordFailure(index, item, code) {
    if (manifestItemIsUsable(item)) {
      const key = `${item.sourceType}:${item.sourceId}`
      const previous = index.files[key]
      index.files[key] = recordFromItem(item, {
        relativePath: previous?.relativePath || buildRelativePath(item),
        lastVerifiedAt: previous?.lastVerifiedAt || '',
        status: 'failed',
        lastErrorCode: code,
      })
    }
    this.updateState({
      failedFiles: this.state.failedFiles + 1,
    })
  }

  assertActive(runId) {
    if (runId !== this.runId || this.token === null) {
      throw new RunPausedError('synchronization paused')
    }
  }

  updateState(patch) {
    this.state = { ...this.state, ...patch }
    this.emit()
  }

  emit() {
    this.emitState(this.getState())
  }
}

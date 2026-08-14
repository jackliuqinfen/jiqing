import test from 'node:test'
import assert from 'node:assert/strict'
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  realpathSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import {
  SyncIndexStore,
  createEmptyIndex,
} from '../src/sync/index-store.mjs'

function temporaryDirectory(t) {
  const directory = mkdtempSync(join(tmpdir(), 'jiqing-sync-index-'))
  t.after(() => rmSync(directory, { recursive: true, force: true }))
  return directory
}

test('partitions and atomically persists an index by environment and user', async (t) => {
  const appDataPath = temporaryDirectory(t)
  const store = new SyncIndexStore({
    appDataPath,
    environmentOrigin: 'https://erp.example.cn',
    userId: 'user-1',
  })
  const index = createEmptyIndex('https://erp.example.cn', 'user-1')
  index.cursorBySelection['project:p-1'] = 'resume-cursor'
  index.files['project_file:file-1'] = {
    sourceRevision: 'file-1:1:1024:2026-07-27T10:00:00',
    sha256: 'a'.repeat(64),
    relativePath: 'project/category/file.pdf',
    fileSize: 1024,
    lastVerifiedAt: '2026-07-27T10:05:00.000Z',
    status: 'synced',
  }

  await store.save(index)

  assert.deepEqual(await store.load(), index)
  assert.match(
    store.filePath,
    /sync-index[\\/][a-f0-9]{64}[\\/]user-[a-f0-9]{64}\.json$/,
  )
  assert.equal(existsSync(`${store.filePath}.tmp`), false)
  assert.deepEqual(
    JSON.parse(readFileSync(store.filePath, 'utf8')),
    index,
  )
})

test('uses hash-only Windows-safe user partitions without case or reserved-name collisions', () => {
  const options = {
    appDataPath: 'C:\\AppData',
    environmentOrigin: 'https://erp.example.cn',
  }
  const upper = new SyncIndexStore({ ...options, userId: 'User' })
  const lower = new SyncIndexStore({ ...options, userId: 'user' })
  const reserved = new SyncIndexStore({ ...options, userId: 'CON' })

  assert.notEqual(upper.filePath.toLowerCase(), lower.filePath.toLowerCase())
  for (const store of [upper, lower, reserved]) {
    assert.match(
      store.filePath.split(/[\\/]/).at(-1),
      /^user-[a-f0-9]{64}\.json$/,
    )
  }
})

test('keeps different environments and users in different index files', () => {
  const options = { appDataPath: 'C:\\AppData' }
  const first = new SyncIndexStore({
    ...options,
    environmentOrigin: 'https://erp.example.cn',
    userId: 'user-1',
  })
  const second = new SyncIndexStore({
    ...options,
    environmentOrigin: 'https://test.example.cn',
    userId: 'user-1',
  })
  const third = new SyncIndexStore({
    ...options,
    environmentOrigin: 'https://erp.example.cn',
    userId: 'user-2',
  })

  assert.notEqual(first.filePath, second.filePath)
  assert.notEqual(first.filePath, third.filePath)
})

test('bounds the index filename for a valid long Unicode user id', async (t) => {
  const appDataPath = temporaryDirectory(t)
  const userId = '用户'.repeat(64)
  const store = new SyncIndexStore({
    appDataPath,
    environmentOrigin: 'https://erp.example.cn',
    userId,
  })

  await store.save(createEmptyIndex('https://erp.example.cn', userId))

  assert.equal(existsSync(store.filePath), true)
  assert.ok(Buffer.byteLength(store.filePath.split(/[\\/]/).at(-1)) <= 200)
})

test('concurrent saves commit in invocation order with independent temporary files', async (t) => {
  const appDataPath = temporaryDirectory(t)
  const store = new SyncIndexStore({
    appDataPath,
    environmentOrigin: 'https://erp.example.cn',
    userId: 'user-1',
  })
  const first = createEmptyIndex('https://erp.example.cn', 'user-1')
  first.cursorBySelection.scope = 'first'
  const second = createEmptyIndex('https://erp.example.cn', 'user-1')
  second.cursorBySelection.scope = 'second'

  let releaseFirst
  let firstEntered
  const firstEnteredPromise = new Promise((resolve) => {
    firstEntered = resolve
  })
  const releaseFirstPromise = new Promise((resolve) => {
    releaseFirst = resolve
  })
  const firstSave = store.save(first, {
    async beforeCommit() {
      firstEntered()
      await releaseFirstPromise
    },
  })
  const boundary = await Promise.race([
    firstEnteredPromise.then(() => 'before-commit'),
    firstSave.then(() => 'completed'),
  ])
  assert.equal(boundary, 'before-commit')
  const secondSave = store.save(second)
  const ordering = await Promise.race([
    secondSave.then(() => 'completed'),
    new Promise((resolve) => setTimeout(() => resolve('waiting'), 20)),
  ])
  assert.equal(ordering, 'waiting')
  releaseFirst()
  await Promise.all([firstSave, secondSave])

  assert.equal((await store.load()).cursorBySelection.scope, 'second')
  assert.equal(
    readdirSync(store.directoryPath).some((name) => name.includes('.tmp-')),
    false,
  )
})

test('quarantines invalid JSON and starts empty without touching synchronized files', async (t) => {
  const appDataPath = temporaryDirectory(t)
  const store = new SyncIndexStore({
    appDataPath,
    environmentOrigin: 'https://erp.example.cn',
    userId: 'user-1',
    now: () => new Date('2026-07-27T10:05:00.000Z'),
  })
  await store.save(createEmptyIndex('https://erp.example.cn', 'user-1'))
  writeFileSync(store.filePath, '{not-json', 'utf8')
  const synchronizedFile = join(appDataPath, 'visible-sync-file.pdf')
  writeFileSync(synchronizedFile, 'keep-me', 'utf8')

  const recovered = await store.load()

  assert.deepEqual(
    recovered,
    createEmptyIndex('https://erp.example.cn', 'user-1'),
  )
  assert.equal(readFileSync(synchronizedFile, 'utf8'), 'keep-me')
  assert.equal(existsSync(store.filePath), false)
  const corruptFiles = readdirSync(store.directoryPath)
    .filter((name) => name.includes('.corrupt-'))
  assert.equal(corruptFiles.length, 1)
  assert.match(
    corruptFiles[0],
    /^user-[a-f0-9]{64}\.json\.corrupt-2026-07-27T10-05-00-000Z$/,
  )
})

test('rejects an index belonging to another environment or user', async (t) => {
  const appDataPath = temporaryDirectory(t)
  const store = new SyncIndexStore({
    appDataPath,
    environmentOrigin: 'https://erp.example.cn',
    userId: 'user-1',
  })
  await store.save(createEmptyIndex('https://erp.example.cn', 'user-1'))
  writeFileSync(store.filePath, JSON.stringify({
    ...createEmptyIndex('https://erp.example.cn', 'user-1'),
    userId: 'other-user',
  }), 'utf8')

  const recovered = await store.load()

  assert.deepEqual(
    recovered,
    createEmptyIndex('https://erp.example.cn', 'user-1'),
  )
})

test('quarantines every malformed recovery ledger shape', async (t) => {
  const transactionId = 'a'.repeat(32)
  const cases = [
    ['unexpected key', (entry) => ({ ...entry, arbitrary: true })],
    ['invalid transaction id', (entry) => ({
      ...entry,
      id: 'invalid',
    })],
    ['relative bound root', (entry) => ({
      ...entry,
      rootPath: 'relative-root',
    })],
    ['non-canonical bound root', (entry) => ({
      ...entry,
      rootPath: `${entry.rootPath}\\.`,
    })],
    ['traversal physical path', (entry) => ({
      ...entry,
      physicalFiles: ['../outside.txt'],
      cleanupFiles: ['../outside.txt'],
    })],
    ['arbitrary physical path', (entry) => ({
      ...entry,
      physicalFiles: ['keep.txt'],
      cleanupFiles: ['keep.txt'],
    })],
    ['mismatched recovery name', (entry) => ({
      ...entry,
      physicalFiles: [`.jiqing-backup-${'b'.repeat(32)}`],
      cleanupFiles: [`.jiqing-backup-${'b'.repeat(32)}`],
    })],
    ['cleanup outside physical files', (entry) => ({
      ...entry,
      cleanupFiles: [`.jiqing-rollback-${transactionId}`],
    })],
    ['cleanup with an extra physical file', (entry) => ({
      ...entry,
      physicalFiles: [
        `.jiqing-backup-${transactionId}`,
        `.jiqing-rollback-${transactionId}`,
      ],
    })],
  ]

  for (const [name, mutate] of cases) {
    await t.test(name, async (t) => {
      const appDataPath = temporaryDirectory(t)
      const store = new SyncIndexStore({
        appDataPath,
        environmentOrigin: 'https://erp.example.cn',
        userId: 'user-1',
      })
      const index = createEmptyIndex('https://erp.example.cn', 'user-1')
      const entry = {
        id: transactionId,
        sourceKey: 'project_file:doc-1',
        previousSourceRevision: 'r-1',
        sourceRevision: 'r-2',
        type: 'cleanup_pending',
        rootPath: realpathSync(appDataPath),
        physicalFiles: [`.jiqing-backup-${transactionId}`],
        cleanupFiles: [`.jiqing-backup-${transactionId}`],
        accountedBytes: 5,
        createdAt: '2026-07-27T10:05:00.000Z',
      }
      index.recoveryEntries[transactionId] = mutate(entry)
      await store.save(createEmptyIndex('https://erp.example.cn', 'user-1'))
      writeFileSync(store.filePath, JSON.stringify(index), 'utf8')

      assert.deepEqual(
        await store.load(),
        createEmptyIndex('https://erp.example.cn', 'user-1'),
      )
    })
  }
})

test('accepts only a nondeleting generated visible manual recovery path', async (t) => {
  const appDataPath = temporaryDirectory(t)
  const store = new SyncIndexStore({
    appDataPath,
    environmentOrigin: 'https://erp.example.cn',
    userId: 'user-1',
  })
  const transactionId = 'a'.repeat(32)
  const visibleRelativePath = '20260727-JQ-001_Project/Contracts/contract.pdf'
  const visibleDirectory = join(
    appDataPath,
    '20260727-JQ-001_Project',
    'Contracts',
  )
  const visibleFile = join(visibleDirectory, 'contract.pdf')
  mkdirSync(visibleDirectory, { recursive: true })
  writeFileSync(visibleFile, 'keep-me', 'utf8')

  const index = createEmptyIndex('https://erp.example.cn', 'user-1')
  index.recoveryEntries[transactionId] = {
    id: transactionId,
    sourceKey: 'project_file:doc-1',
    previousSourceRevision: '',
    sourceRevision: 'r-1',
    type: 'manual_recovery',
    rootPath: realpathSync(appDataPath),
    physicalFiles: [visibleRelativePath],
    cleanupFiles: [],
    accountedBytes: 7,
    createdAt: '2026-07-27T10:05:00.000Z',
  }

  await store.save(index)
  assert.deepEqual(await store.load(), index)

  index.recoveryEntries[transactionId].cleanupFiles = [visibleRelativePath]
  writeFileSync(store.filePath, JSON.stringify(index), 'utf8')

  assert.deepEqual(
    await store.load(),
    createEmptyIndex('https://erp.example.cn', 'user-1'),
  )
  assert.equal(readFileSync(visibleFile, 'utf8'), 'keep-me')
})

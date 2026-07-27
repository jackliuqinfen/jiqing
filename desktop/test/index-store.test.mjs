import test from 'node:test'
import assert from 'node:assert/strict'
import {
  existsSync,
  mkdtempSync,
  readFileSync,
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
    /sync-index[\\/][a-f0-9]{64}[\\/]user-1\.json$/,
  )
  assert.equal(existsSync(`${store.filePath}.tmp`), false)
  assert.deepEqual(
    JSON.parse(readFileSync(store.filePath, 'utf8')),
    index,
  )
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
  assert.deepEqual(
    readdirSync(store.directoryPath).filter((name) => name.includes('.corrupt-')),
    ['user-1.json.corrupt-2026-07-27T10-05-00-000Z'],
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

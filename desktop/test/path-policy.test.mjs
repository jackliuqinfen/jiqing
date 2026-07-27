import test from 'node:test'
import assert from 'node:assert/strict'
import {
  mkdirSync,
  mkdtempSync,
  rmSync,
  symlinkSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, sep } from 'node:path'

import {
  appendFilenameSuffix,
  buildRelativePath,
  canonicalizePath,
  pathsOverlap,
  resolvePhysicalPath,
  resolveWithinRoot,
  safeSegment,
} from '../src/sync/path-policy.mjs'

test('detects equal, parent, and child path overlap without matching siblings', () => {
  const installationDirectory = join('C:\\', 'Program Files', 'JiqingERP')
  assert.equal(pathsOverlap(
    installationDirectory,
    installationDirectory.toUpperCase(),
  ), true)
  assert.equal(pathsOverlap(
    dirname(installationDirectory),
    installationDirectory,
  ), true)
  assert.equal(pathsOverlap(
    join(installationDirectory, 'sync'),
    installationDirectory,
  ), true)
  assert.equal(pathsOverlap(
    join('C:\\', 'Program Files', 'JiqingERP Files'),
    installationDirectory,
  ), false)
})

test('physical path canonicalization fails closed on non-ENOENT errors', () => {
  const denied = Object.assign(new Error('access denied'), { code: 'EACCES' })
  assert.throws(
    () => canonicalizePath(
      join('C:\\', 'Program Files', 'JiqingERP'),
      () => {
        throw denied
      },
    ),
    /unable to resolve physical path boundary/i,
  )
})

test('normalizes unsafe Windows names deterministically', () => {
  assert.equal(safeSegment('合同:最终版?.pdf'), '合同_最终版_.pdf')
  assert.equal(safeSegment('CON'), '_CON')
  assert.equal(safeSegment('CON .txt'), '_CON .txt')
  assert.equal(safeSegment('项目. '), '项目')
  assert.equal(safeSegment('../合同'), '_合同')
})

test('builds a bounded relative project path', () => {
  const path = buildRelativePath({
    projectCode: '20260727-JQ-001',
    projectName: '区直学校维修',
    categoryName: '合同文件',
    originalName: '施工合同.pdf',
  })
  assert.equal(
    path,
    '20260727-JQ-001_区直学校维修/合同文件/施工合同.pdf',
  )
  assert.ok([...path].length < 220)
})

test('bounds Unicode segments and preserves the final extension', () => {
  const name = `${'资'.repeat(100)}.pdf`
  const segment = safeSegment(name, { preserveExtension: true })

  assert.equal([...segment].length, 80)
  assert.ok(segment.endsWith('.pdf'))
  assert.equal([...buildRelativePath({
    projectCode: 'P'.repeat(100),
    projectName: '项目'.repeat(100),
    categoryName: '分类'.repeat(100),
    originalName: name,
  })].length <= 220, true)
})

test('rejects a resolved path outside the selected root', () => {
  const root = join('C:\\', 'ERP Files')
  assert.equal(
    resolveWithinRoot(root, `项目${sep}合同.pdf`),
    join(root, '项目', '合同.pdf'),
  )
  assert.throws(
    () => resolveWithinRoot(root, `..${sep}outside.pdf`),
    /outside sync root/i,
  )
  assert.throws(
    () => resolveWithinRoot(root, join('C:\\', 'outside.pdf')),
    /outside sync root/i,
  )
})

test('keeps suffixed conflict paths within the relative path budget', () => {
  const relativePath = `${'项'.repeat(80)}/${'类'.repeat(80)}/${'文'.repeat(54)}.pdf`
  assert.equal([...relativePath].length, 220)

  const suffixed = appendFilenameSuffix(relativePath, '_服务器新版_9999')

  assert.ok([...suffixed].length <= 220)
  assert.ok(suffixed.endsWith('_服务器新版_9999.pdf'))
})

test('rejects an existing junction ancestor before publication', async (t) => {
  const base = mkdtempSync(join(tmpdir(), 'jiqing-path-policy-'))
  t.after(() => rmSync(base, { recursive: true, force: true }))
  const root = join(base, 'root')
  const outside = join(base, 'outside')
  mkdirSync(root)
  mkdirSync(outside)
  try {
    symlinkSync(outside, join(root, 'linked'), 'junction')
  } catch (error) {
    if (error?.code === 'EPERM') {
      t.skip('junction creation is unavailable on this Windows host')
      return
    }
    throw error
  }

  await assert.rejects(
    resolvePhysicalPath(root, `linked${sep}file.pdf`),
    /reparse|junction|symbolic/i,
  )
})

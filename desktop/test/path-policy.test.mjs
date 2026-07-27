import test from 'node:test'
import assert from 'node:assert/strict'
import { join, sep } from 'node:path'

import {
  buildRelativePath,
  resolveWithinRoot,
  safeSegment,
} from '../src/sync/path-policy.mjs'

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

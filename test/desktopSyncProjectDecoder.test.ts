import assert from 'node:assert/strict'
import test from 'node:test'

import { decodeDesktopSyncProjects } from '../src/api/desktopSyncProjectDecoder.ts'

const validProject = {
  projectRef: 'project:project-1',
  canonicalProjectId: 'project-1',
  auditProjectId: null,
  projectCode: 'XM-001',
  projectName: '区直学校校舍维修工程',
  fileCount: 3,
  totalFileSizeBytes: 2_097_160,
}

function decode(payload: unknown) {
  return decodeDesktopSyncProjects(payload)
}

test('strictly decodes the exact real project-root payload', () => {
  assert.deepEqual(decode([validProject]), [validProject])
})

test('accepts an audit-only historical project with the backend canonical empty code', () => {
  const auditOnlyProject = {
    projectRef: 'audit:audit-history-1',
    canonicalProjectId: null,
    auditProjectId: 'audit-history-1',
    projectCode: '',
    projectName: '历史审计项目',
    fileCount: 1,
    totalFileSizeBytes: 1_024,
  }

  assert.deepEqual(decode([auditOnlyProject]), [auditOnlyProject])
})

test('accepts only the empty sentinel or a canonical trimmed project code', () => {
  for (const projectCode of ['', 'XM-001']) {
    assert.deepEqual(
      decode([{ ...validProject, projectCode }]),
      [{ ...validProject, projectCode }],
    )
  }

  for (const projectCode of ['   ', ' XM-001', 'XM-001 ']) {
    assert.throws(
      () => decode([{ ...validProject, projectCode }]),
      /invalid desktop sync project/,
    )
  }
})

test('rejects non-array and oversized top-level payloads', () => {
  assert.throws(() => decode({ items: [validProject] }), /invalid desktop sync projects payload/)
  assert.throws(
    () => decode(Array.from({ length: 501 }, () => validProject)),
    /invalid desktop sync projects payload/,
  )
})

test('rejects extra, missing, empty, malformed, and overlong string fields', () => {
  const invalidRows = [
    { ...validProject, unexpected: true },
    { ...validProject, projectName: undefined },
    { ...validProject, projectRef: 'unsafe/project' },
    { ...validProject, projectRef: `project:${'a'.repeat(249)}` },
    { ...validProject, projectName: '   ' },
    { ...validProject, projectName: '项'.repeat(513) },
    { ...validProject, projectCode: 'A'.repeat(257) },
    { ...validProject, canonicalProjectId: '' },
    { ...validProject, canonicalProjectId: 'A'.repeat(257) },
    { ...validProject, auditProjectId: 1 },
  ]

  for (const row of invalidRows) {
    assert.throws(() => decode([row]), /invalid desktop sync project/)
  }
})

test('rejects negative, fractional, non-finite, and unsafe integer totals', () => {
  const invalidRows = [
    { ...validProject, fileCount: -1 },
    { ...validProject, fileCount: 1.5 },
    { ...validProject, fileCount: Number.NaN },
    { ...validProject, fileCount: Number.MAX_SAFE_INTEGER + 1 },
    { ...validProject, totalFileSizeBytes: -1 },
    { ...validProject, totalFileSizeBytes: 1.5 },
    { ...validProject, totalFileSizeBytes: Number.POSITIVE_INFINITY },
    { ...validProject, totalFileSizeBytes: Number.MAX_SAFE_INTEGER + 1 },
  ]

  for (const row of invalidRows) {
    assert.throws(() => decode([row]), /invalid desktop sync project/)
  }
})

test('rejects the entire response when any row is malformed', () => {
  assert.throws(
    () => decode([validProject, { ...validProject, projectName: '' }]),
    /invalid desktop sync project/,
  )
})

test('rejects duplicate project references instead of merging or fabricating rows', () => {
  assert.throws(
    () => decode([validProject, { ...validProject }]),
    /duplicate desktop sync project reference/,
  )
})

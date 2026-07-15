import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { buildProjectMutationPayload } from '../src/utils/projectMutationPayload.ts'
import { buildReviewDecisionInput } from '../src/utils/documentReviewDecision.ts'
import {
  flattenLoadedProjectPages,
  getLoadedProjectPageCount,
  settleLifecycleRefresh,
} from '../src/utils/projectLifecycleRefresh.ts'

test('omits backend-owned lifecycle and audit linkage fields from project edits', () => {
  const payload = buildProjectMutationPayload('edit', {
    id: 'project-1',
    projectName: 'North bridge',
    settlementStatus: 'not_started',
    projectStatus: 'under_construction',
    auditStage: 'first_audit',
    auditProjectId: 'audit-stale',
  })

  assert.deepEqual(payload, {
    id: 'project-1',
    projectName: 'North bridge',
    settlementStatus: 'not_started',
  })
})

test('blocks ordinary project creation so formal records can only come from contract confirmation', () => {
  assert.throws(
    () => buildProjectMutationPayload('create', { projectName: 'North bridge' }),
    /contract review confirmation/i,
  )
})

test('returns the exact AI value when a reviewer accepts a recognized field', () => {
  const aiValue = ['竣工验收合格后支付 60%']
  assert.deepEqual(
    buildReviewDecisionInput({ id: 'field-1', aiValue, sourceKind: 'ocr' }, 'accepted', ''),
    {
      fieldId: 'field-1',
      decision: 'accepted',
      confirmedValue: aiValue,
    },
  )
})

test('records an auditable reason when a reviewer modifies an OCR value', () => {
  assert.deepEqual(
    buildReviewDecisionInput({ id: 'field-2', aiValue: '错误日期', sourceKind: 'ocr' }, 'modified', '2026-07-14'),
    {
      fieldId: 'field-2',
      decision: 'modified',
      confirmedValue: '2026-07-14',
      reason: '人工复核修正 OCR 识别值',
    },
  )
})

test('records the actual source when correcting fallback values', () => {
  assert.equal(
    buildReviewDecisionInput(
      { id: 'manual-field', aiValue: '手工值', sourceKind: 'manual' },
      'modified',
      '核对后值',
    ).reason,
    '人工核对合同原文后修正手工录入值',
  )
  assert.equal(
    buildReviewDecisionInput(
      { id: 'external-field', aiValue: '外部建议', sourceKind: 'external_ai' },
      'modified',
      '核对后值',
    ).reason,
    '人工核对合同原文后修正外部 AI 建议',
  )
})

test('replaces all loaded mobile pages without dropping prior records', () => {
  assert.equal(getLoadedProjectPageCount(43, 20), 3)
  assert.deepEqual(
    flattenLoadedProjectPages([
      [{ id: '1' }, { id: '2' }],
      [{ id: '3' }, { id: '4' }],
      [{ id: '5' }],
    ]).map((project) => project.id),
    ['1', '2', '3', '4', '5'],
  )
})

test('starts the lifecycle snapshot refresh independently and retains partial refresh failures', async () => {
  const calls: string[] = []
  const result = await settleLifecycleRefresh({
    snapshot: async () => {
      calls.push('snapshot')
      return 'fresh snapshot'
    },
    ancillary: [
      async () => {
        calls.push('current')
        return 'fresh detail'
      },
      async () => {
        calls.push('list')
        throw new Error('list unavailable')
      },
    ],
  })

  assert.equal(calls[0], 'snapshot')
  assert.equal(result.snapshot.status, 'fulfilled')
  assert.deepEqual(result.ancillary.map((entry) => entry.status), ['fulfilled', 'rejected'])
})

test('desktop lifecycle refresh uses the partial-safe refresh coordinator', () => {
  const source = readFileSync(new URL('../src/views/ProjectManagementView.vue', import.meta.url), 'utf8')

  assert.match(source, /settleLifecycleRefresh\s*\(/)
})

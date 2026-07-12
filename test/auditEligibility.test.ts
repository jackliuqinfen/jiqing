import assert from 'node:assert/strict'
import test from 'node:test'
import { partitionAuditStartCandidates } from '../src/utils/auditEligibility.ts'

test('keeps only audit-eligible projects and classifies every skipped reason', () => {
  const result = partitionAuditStartCandidates([
    { id: 'eligible', auditProjectId: '', projectStatus: 'pending_submission', submittedAmount: 1 },
    { id: 'linked', auditProjectId: 'audit-1', projectStatus: 'pending_submission', submittedAmount: 1 },
    { id: 'wrong-stage', auditProjectId: '', projectStatus: 'awarded', submittedAmount: 1 },
    { id: 'missing-amount', auditProjectId: '', projectStatus: 'first_audit', submittedAmount: 0 },
  ])

  assert.deepEqual(result.eligible.map((project) => project.id), ['eligible'])
  assert.deepEqual(
    result.skipped.map(({ project, reason }) => [project.id, reason]),
    [
      ['linked', 'already_linked'],
      ['wrong-stage', 'stage_not_ready'],
      ['missing-amount', 'submitted_amount_required'],
    ],
  )
})

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { buildProjectMutationPayload } from '../src/utils/projectMutationPayload.ts'
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

test('uses only fixed lifecycle defaults for project creation and never reuses audit linkage', () => {
  const payload = buildProjectMutationPayload('create', {
    projectName: 'North bridge',
    projectStatus: 'under_construction',
    auditStage: 'first_audit',
    auditProjectId: 'audit-stale',
  })

  assert.deepEqual(payload, {
    projectName: 'North bridge',
    projectStatus: 'awarded',
    auditStage: 'not_linked',
  })
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

import assert from 'node:assert/strict'
import test from 'node:test'

import { SyncScheduler } from '../src/sync/sync-scheduler.mjs'

const request = {
  authToken: 'token',
  userId: 'user-1',
  projectRefs: ['project:p-1'],
}

function createHarness(policy = {
  enabled: true,
  enabledForCurrentUser: true,
  pollIntervalSeconds: 120,
}) {
  const timers = []
  const cleared = []
  const starts = []
  const controller = {
    hasActiveSession: () => false,
    async start(value) {
      starts.push(value)
      return { status: 'completed' }
    },
  }
  const scheduler = new SyncScheduler({
    controller,
    apiClient: { getPolicy: async () => policy },
    setTimeoutImpl(callback, delay) {
      const timer = { callback, delay }
      timers.push(timer)
      return timer
    },
    clearTimeoutImpl(timer) {
      cleared.push(timer)
    },
  })
  return { scheduler, timers, cleared, starts }
}

test('automatic sync follows the server polling interval and repeats after a run', async () => {
  const harness = createHarness()
  harness.scheduler.arm(request, { status: 'completed' })
  await Promise.resolve()
  assert.equal(harness.timers.length, 1)
  assert.equal(harness.timers[0].delay, 120000)

  const firstTimer = harness.timers[0]
  firstTimer.callback()
  await Promise.resolve()
  await Promise.resolve()
  assert.equal(harness.starts.length, 1)
  assert.equal(harness.timers.length, 2)
  assert.equal(harness.timers[1].delay, 120000)
})
test('automatic sync stops when the policy revokes access', async () => {
  const harness = createHarness({
    enabled: true,
    enabledForCurrentUser: false,
    pollIntervalSeconds: 60,
  })
  harness.scheduler.arm(request, { status: 'completed' })
  await Promise.resolve()
  assert.equal(harness.scheduler.isArmed(), false)
  assert.equal(harness.timers.length, 0)
})

test('stopping automatic sync clears the scheduled timer', async () => {
  const harness = createHarness()
  harness.scheduler.arm(request, { status: 'completed' })
  await Promise.resolve()
  harness.scheduler.stop()
  assert.equal(harness.scheduler.isArmed(), false)
  assert.deepEqual(harness.cleared, [harness.timers[0]])
})

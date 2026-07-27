import assert from 'node:assert/strict'
import test from 'node:test'

import { createDesktopSyncProjectLoadCycle } from '../src/composables/desktopSyncLoadCycle.ts'

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((nextResolve) => {
    resolve = nextResolve
  })
  return { promise, resolve }
}

test('only the newest out-of-order response publishes and stale finally cannot clear loading', async () => {
  const cycle = createDesktopSyncProjectLoadCycle()
  const olderResponse = deferred<string>()
  const newerResponse = deferred<string>()
  const older = cycle.begin('user-a')
  const newer = cycle.begin('user-a')
  let published = ''
  let loading = true

  async function settle(
    ticket: ReturnType<typeof cycle.begin>,
    response: Promise<string>,
  ) {
    try {
      const value = await response
      if (cycle.isCurrent(ticket, 'user-a')) published = value
    } finally {
      if (cycle.isCurrent(ticket, 'user-a')) loading = false
    }
  }

  const olderSettled = settle(older, olderResponse.promise)
  const newerSettled = settle(newer, newerResponse.promise)

  olderResponse.resolve('stale-projects')
  await olderSettled
  assert.equal(published, '')
  assert.equal(loading, true)

  newerResponse.resolve('current-projects')
  await newerSettled
  assert.equal(published, 'current-projects')
  assert.equal(loading, false)
})

test('dialog close invalidates its in-flight project load and stale finally', () => {
  const cycle = createDesktopSyncProjectLoadCycle()
  const openDialogLoad = cycle.begin('user-a')

  cycle.invalidate('dialog_close')

  assert.equal(cycle.isCurrent(openDialogLoad, 'user-a'), false)
})

test('auth identity change prevents the previous user response from publishing', () => {
  const cycle = createDesktopSyncProjectLoadCycle()
  const userALoad = cycle.begin('user-a')

  cycle.invalidate('auth_change')
  const userBLoad = cycle.begin('user-b')

  assert.equal(cycle.isCurrent(userALoad, 'user-b'), false)
  assert.equal(cycle.isCurrent(userBLoad, 'user-a'), false)
  assert.equal(cycle.isCurrent(userBLoad, 'user-b'), true)
})

test('permission change invalidates the current response before a fresh check', () => {
  const cycle = createDesktopSyncProjectLoadCycle()
  const load = cycle.begin('user-a')

  cycle.invalidate('permission_changed')

  assert.equal(cycle.isCurrent(load, 'user-a'), false)
})

test('unmount invalidates the in-flight response', () => {
  const cycle = createDesktopSyncProjectLoadCycle()
  const load = cycle.begin('user-a')

  cycle.invalidate('unmount')

  assert.equal(cycle.isCurrent(load, 'user-a'), false)
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'

import { createDesktopUpdateController } from '../src/update-controller.mjs'

class FakeUpdater extends EventEmitter {
  constructor() {
    super()
    this.autoDownload = false
    this.autoInstallOnAppQuit = false
    this.checkCount = 0
    this.installCount = 0
  }

  async checkForUpdates() {
    this.checkCount += 1
  }

  quitAndInstall() {
    this.installCount += 1
  }
}

test('unpackaged desktop reports a truthful unavailable update state', async () => {
  const updater = new FakeUpdater()
  const controller = createDesktopUpdateController({
    currentVersion: '1.0.3',
    enabled: false,
    updater,
  })

  assert.deepEqual(controller.getState(), {
    status: 'unavailable',
    currentVersion: '1.0.3',
    availableVersion: '',
    progressPercent: 0,
    canCheck: false,
    canInstall: false,
    lastCheckedAt: '',
    message: '在线更新仅在已安装的 Windows 客户端中可用',
  })
  await assert.rejects(controller.check(), /unavailable/i)
  assert.equal(updater.checkCount, 0)
})

test('update controller exposes real check, download, and install progress', async () => {
  const updater = new FakeUpdater()
  const emitted = []
  const controller = createDesktopUpdateController({
    currentVersion: '1.0.3',
    enabled: true,
    updater,
    now: () => '2026-07-29T04:00:00.000Z',
    emitState: (state) => emitted.push(state),
  })

  assert.equal(updater.autoDownload, true)
  assert.equal(updater.autoInstallOnAppQuit, true)

  await controller.check()
  assert.equal(updater.checkCount, 1)
  assert.equal(controller.getState().status, 'checking')

  updater.emit('update-available', { version: '1.0.4' })
  assert.equal(controller.getState().status, 'available')
  assert.equal(controller.getState().availableVersion, '1.0.4')

  updater.emit('download-progress', { percent: 42.7 })
  assert.equal(controller.getState().status, 'downloading')
  assert.equal(controller.getState().progressPercent, 43)

  updater.emit('update-downloaded', { version: '1.0.4' })
  assert.equal(controller.getState().status, 'downloaded')
  assert.equal(controller.getState().canInstall, true)

  controller.install()
  assert.equal(updater.installCount, 1)
  assert.ok(emitted.length >= 4)
})

test('update controller reports current version when no update exists', async () => {
  const updater = new FakeUpdater()
  const controller = createDesktopUpdateController({
    currentVersion: '1.0.3',
    enabled: true,
    updater,
    now: () => '2026-07-29T04:05:00.000Z',
  })

  await controller.check()
  updater.emit('update-not-available', { version: '1.0.3' })

  assert.deepEqual(controller.getState(), {
    status: 'up_to_date',
    currentVersion: '1.0.3',
    availableVersion: '',
    progressPercent: 0,
    canCheck: true,
    canInstall: false,
    lastCheckedAt: '2026-07-29T04:05:00.000Z',
    message: '当前已是最新版本',
  })
  assert.throws(() => controller.install(), /not ready/i)
})

test('update controller prevents duplicate checks and bounds remote progress', async () => {
  const updater = new FakeUpdater()
  const controller = createDesktopUpdateController({
    currentVersion: '1.0.3',
    enabled: true,
    updater,
  })

  await controller.check()
  await assert.rejects(controller.check(), /already/i)
  updater.emit('download-progress', { percent: 900 })
  assert.equal(controller.getState().progressPercent, 100)
  updater.emit('error', new Error('network unavailable'))
  assert.equal(controller.getState().status, 'error')
  assert.equal(controller.getState().canCheck, true)
  assert.doesNotMatch(controller.getState().message, /stack|file:\/\//i)
})

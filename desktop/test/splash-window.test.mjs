import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createEnterpriseSplashWindow,
  createSplashWindowOptions,
  SPLASH_PARTITION,
  SPLASH_URL,
} from '../src/splash-window.mjs'

test('enterprise splash window is a fixed secure branded surface', () => {
  const options = createSplashWindowOptions({
    iconPath: 'C:\\Program Files\\JiqingERP\\resources\\assets\\icon.ico',
  })

  assert.equal(options.width, 680)
  assert.equal(options.height, 420)
  assert.equal(options.frame, false)
  assert.equal(options.show, false)
  assert.equal(options.resizable, false)
  assert.equal(options.maximizable, false)
  assert.equal(options.fullscreenable, false)
  assert.equal(options.skipTaskbar, true)
  assert.equal(options.backgroundColor, '#f5f8ff')
  assert.equal(options.webPreferences.nodeIntegration, false)
  assert.equal(options.webPreferences.contextIsolation, true)
  assert.equal(options.webPreferences.sandbox, true)
  assert.equal(options.webPreferences.webSecurity, true)
  assert.equal(options.webPreferences.partition, SPLASH_PARTITION)
  assert.equal(Object.hasOwn(options.webPreferences, 'preload'), false)
})

test('enterprise splash loads the fixed app page before it becomes visible', async () => {
  const calls = []
  const fakeWindow = {
    destroyed: false,
    async loadURL(url) {
      calls.push(['loadURL', url])
    },
    isDestroyed() {
      return this.destroyed
    },
    show() {
      calls.push(['show'])
    },
  }
  class FakeBrowserWindow {
    constructor(options) {
      calls.push(['construct', options])
      return fakeWindow
    }
  }

  const result = await createEnterpriseSplashWindow({
    BrowserWindow: FakeBrowserWindow,
    iconPath: 'C:\\Program Files\\JiqingERP\\resources\\assets\\icon.ico',
  })

  assert.equal(result, fakeWindow)
  assert.deepEqual(calls.map(([name]) => name), [
    'construct',
    'loadURL',
    'show',
  ])
  assert.equal(calls[1][1], SPLASH_URL)
})

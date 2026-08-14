import test from 'node:test'
import assert from 'node:assert/strict'

import {
  desktopWindowTitle,
  installEnvironmentTitleGuard,
} from '../src/window-title.mjs'

test('internal-test title remains visible after page title updates', () => {
  let listener = null
  let currentTitle = ''
  const guarded = installEnvironmentTitleGuard({
    environmentLabel: '内部测试',
    webContents: {
      on(eventName, callback) {
        assert.equal(eventName, 'page-title-updated')
        listener = callback
      },
    },
    window: {
      setTitle(value) {
        currentTitle = value
      },
    },
  })
  let prevented = false
  listener({
    preventDefault() {
      prevented = true
    },
  })

  assert.equal(guarded, true)
  assert.equal(prevented, true)
  assert.equal(currentTitle, '集庆工程管理 - 内部测试')
})

test('production keeps remote and fallback page title behavior', () => {
  let subscriptions = 0
  const guarded = installEnvironmentTitleGuard({
    environmentLabel: '',
    webContents: {
      on() {
        subscriptions += 1
      },
    },
    window: {
      setTitle() {
        assert.fail('production title must not be forced')
      },
    },
  })

  assert.equal(desktopWindowTitle(''), '集庆工程管理')
  assert.equal(guarded, false)
  assert.equal(subscriptions, 0)
})

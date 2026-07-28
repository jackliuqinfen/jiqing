import test from 'node:test'
import assert from 'node:assert/strict'

import {
  createIntegratedTitleBarOptions,
  DESKTOP_TITLE_BAR_HEIGHT,
  hasLiveWindowWebContents,
  INTEGRATED_TITLE_BAR_CSS,
} from '../src/window-chrome.mjs'

test('integrated title bar keeps native Windows controls without a second title row', () => {
  const options = createIntegratedTitleBarOptions()

  assert.equal(options.titleBarStyle, 'hidden')
  assert.deepEqual(options.titleBarOverlay, {
    color: '#F8FBFF',
    symbolColor: '#53627A',
    height: DESKTOP_TITLE_BAR_HEIGHT,
  })
})

test('integrated title bar reserves native control space and preserves interactions', () => {
  assert.match(INTEGRATED_TITLE_BAR_CSS, /\.platform-topbar/)
  assert.match(INTEGRATED_TITLE_BAR_CSS, /-webkit-app-region:\s*drag/)
  assert.match(INTEGRATED_TITLE_BAR_CSS, /padding-right:\s*158px/)
  assert.match(INTEGRATED_TITLE_BAR_CSS, /\.platform-topbar \.platform-nav/)
  assert.match(INTEGRATED_TITLE_BAR_CSS, /-webkit-app-region:\s*no-drag/)
  assert.match(INTEGRATED_TITLE_BAR_CSS, /\.login-page::before/)
})

test('window lifecycle rejects an already destroyed webContents', () => {
  const window = {
    isDestroyed: () => false,
    webContents: {
      isDestroyed: () => true,
    },
  }

  assert.equal(hasLiveWindowWebContents(window), false)
  assert.equal(hasLiveWindowWebContents(null), false)
})

test('window lifecycle accepts only a live window and live webContents', () => {
  const window = {
    isDestroyed: () => false,
    webContents: {
      isDestroyed: () => false,
    },
  }

  assert.equal(hasLiveWindowWebContents(window), true)
  assert.equal(
    hasLiveWindowWebContents({
      isDestroyed: () => true,
      webContents: window.webContents,
    }),
    false,
  )
})

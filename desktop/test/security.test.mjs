import test from 'node:test'
import assert from 'node:assert/strict'

import {
  assertTrustedSender,
  createSecureWebPreferences,
  isAllowedNavigation,
  isReviewedExternalUrl,
  normalizeWindowBounds,
} from '../src/security.mjs'

const TRUSTED_ORIGIN = 'https://erp.example.cn'

test('navigation accepts only the exact configured origin', () => {
  assert.equal(
    isAllowedNavigation('https://erp.example.cn/#/finance', TRUSTED_ORIGIN),
    true,
  )
  assert.equal(
    isAllowedNavigation('https://erp.example.cn:444/#/finance', TRUSTED_ORIGIN),
    false,
  )
  assert.equal(
    isAllowedNavigation('https://erp.example.cn.evil.test/', TRUSTED_ORIGIN),
    false,
  )
  assert.equal(
    isAllowedNavigation('https://user:secret@erp.example.cn/', TRUSTED_ORIGIN),
    false,
  )
})

test('navigation rejects malformed and non-HTTP schemes', () => {
  for (const url of [
    'not a url',
    'javascript:alert(1)',
    'data:text/html,unsafe',
    'file:///C:/unsafe',
    'app://connecting',
    'jiqing://finance',
  ]) {
    assert.equal(isAllowedNavigation(url, TRUSTED_ORIGIN), false)
  }
})

test('IPC rejects an untrusted sender and accepts a trusted frame', () => {
  assert.doesNotThrow(() => {
    assertTrustedSender('https://erp.example.cn/#/materials', TRUSTED_ORIGIN)
  })
  assert.throws(
    () => assertTrustedSender('https://example.com/', TRUSTED_ORIGIN),
    /untrusted ipc sender/,
  )
})

test('only credential-free external HTTPS URLs are reviewed for system browser', () => {
  assert.equal(
    isReviewedExternalUrl('https://help.example.com/guide', TRUSTED_ORIGIN),
    true,
  )
  assert.equal(
    isReviewedExternalUrl('https://erp.example.cn/help', TRUSTED_ORIGIN),
    false,
  )
  assert.equal(
    isReviewedExternalUrl('https://user:secret@example.com/', TRUSTED_ORIGIN),
    false,
  )
  assert.equal(
    isReviewedExternalUrl('mailto:support@example.com', TRUSTED_ORIGIN),
    false,
  )
  assert.equal(
    isReviewedExternalUrl('file:///C:/unsafe', TRUSTED_ORIGIN),
    false,
  )
})

test('remote renderer preferences keep Node unavailable and use memory-only storage', () => {
  const preferences = createSecureWebPreferences({
    preload: 'C:\\app\\preload.mjs',
    partition: 'desktop-erp-memory',
  })

  assert.deepEqual(preferences, {
    preload: 'C:\\app\\preload.mjs',
    partition: 'desktop-erp-memory',
    nodeIntegration: false,
    contextIsolation: true,
    sandbox: true,
    webSecurity: true,
    allowRunningInsecureContent: false,
  })
  assert.equal(Object.isFrozen(preferences), true)
})

test('window bounds restore only usable values intersecting a known display', () => {
  const displays = [
    { workArea: { x: 0, y: 0, width: 1920, height: 1040 } },
    { workArea: { x: 1920, y: 0, width: 1280, height: 1024 } },
  ]

  assert.deepEqual(
    normalizeWindowBounds(
      { x: 120, y: 80, width: 1440, height: 900 },
      displays,
    ),
    { x: 120, y: 80, width: 1440, height: 900 },
  )
  assert.equal(
    normalizeWindowBounds(
      { x: 8000, y: 8000, width: 1440, height: 900 },
      displays,
    ),
    null,
  )
  assert.equal(
    normalizeWindowBounds(
      { x: 0, y: 0, width: 100000, height: 900 },
      displays,
    ),
    null,
  )
  assert.equal(
    normalizeWindowBounds(
      { x: 0, y: 0, width: '1440', height: 900 },
      displays,
    ),
    null,
  )
})

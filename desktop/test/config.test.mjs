import test from 'node:test'
import assert from 'node:assert/strict'

import { loadDesktopConfig } from '../src/config.mjs'

const INTERNAL_PROFILE = Object.freeze({
  schemaVersion: 1,
  releaseChannel: 'internal-test',
  serverOrigin: 'http://121.4.36.112:8088',
})

const PRODUCTION_PROFILE = Object.freeze({
  schemaVersion: 1,
  releaseChannel: 'production',
  serverOrigin: 'https://erp.example.cn',
})

test('packaged configuration works without runtime environment variables', () => {
  const config = loadDesktopConfig({
    isPackaged: true,
    env: {},
    embeddedProfile: INTERNAL_PROFILE,
  })

  assert.equal(config.releaseChannel, 'internal-test')
  assert.equal(config.origin, 'http://121.4.36.112:8088')
  assert.equal(config.environmentLabel, '内部测试')
})

test('packaged production profile rejects an HTTP origin', () => {
  assert.throws(
    () => loadDesktopConfig({
      isPackaged: true,
      env: {},
      embeddedProfile: {
        ...PRODUCTION_PROFILE,
        serverOrigin: 'http://121.4.36.112:8088',
      },
    }),
    /HTTPS/,
  )
})

test('packaged configuration fails closed for missing or unsupported profiles', () => {
  assert.throws(
    () => loadDesktopConfig({
      isPackaged: true,
      env: {},
      embeddedProfile: null,
    }),
    /embedded release profile/,
  )
  assert.throws(
    () => loadDesktopConfig({
      isPackaged: true,
      env: {},
      embeddedProfile: {
        ...INTERNAL_PROFILE,
        schemaVersion: 2,
      },
    }),
    /embedded release profile/,
  )
})

test('runtime environment cannot weaken a packaged production profile', () => {
  const config = loadDesktopConfig({
    isPackaged: true,
    embeddedProfile: PRODUCTION_PROFILE,
    env: {
      DESKTOP_RELEASE_CHANNEL: 'internal-test',
      DESKTOP_SERVER_URL: 'http://attacker.invalid',
    },
  })

  assert.equal(config.releaseChannel, 'production')
  assert.equal(config.origin, 'https://erp.example.cn')
  assert.equal(config.environmentLabel, '')
})

test('explicit unpackaged execution can use development or test overrides', () => {
  const config = loadDesktopConfig({
    isPackaged: false,
    embeddedProfile: PRODUCTION_PROFILE,
    env: {
      DESKTOP_RELEASE_CHANNEL: 'internal-test',
      DESKTOP_SERVER_URL: 'http://127.0.0.1:5173',
    },
  })

  assert.equal(config.releaseChannel, 'internal-test')
  assert.equal(config.origin, 'http://127.0.0.1:5173')
})

test('production requires an HTTPS server origin', () => {
  assert.throws(
    () => loadDesktopConfig({
      DESKTOP_RELEASE_CHANNEL: 'production',
      DESKTOP_SERVER_URL: 'http://121.4.36.112:8088',
    }),
    /HTTPS/,
  )
})

test('internal test keeps only the exact configured HTTP origin', () => {
  const config = loadDesktopConfig({
    DESKTOP_RELEASE_CHANNEL: 'internal-test',
    DESKTOP_SERVER_URL: 'http://127.0.0.1:5173/path?query=1#hash',
  })

  assert.equal(config.origin, 'http://127.0.0.1:5173')
  assert.equal(config.environmentLabel, '内部测试')
  assert.equal(config.healthUrl, 'http://127.0.0.1:5173/api/health')
  assert.equal(config.healthTimeoutMs, 8000)
})

test('development is visibly labelled and accepts a configured HTTPS origin', () => {
  const config = loadDesktopConfig({
    DESKTOP_RELEASE_CHANNEL: 'development',
    DESKTOP_SERVER_URL: 'https://dev.example.test:8443/app',
  })

  assert.equal(config.origin, 'https://dev.example.test:8443')
  assert.equal(config.environmentLabel, '开发环境')
})

test('production has no environment label', () => {
  const config = loadDesktopConfig({
    DESKTOP_RELEASE_CHANNEL: 'production',
    DESKTOP_SERVER_URL: 'https://erp.example.cn/',
  })

  assert.equal(config.environmentLabel, '')
})

test('configuration rejects unsupported channels and unsafe absolute URLs', () => {
  assert.throws(
    () => loadDesktopConfig({
      DESKTOP_RELEASE_CHANNEL: 'staging',
      DESKTOP_SERVER_URL: 'https://erp.example.cn',
    }),
    /release channel/,
  )
  for (const url of [
    'javascript:alert(1)',
    'data:text/html,unsafe',
    'file:///C:/Windows/System32/calc.exe',
    'app://connecting',
    'https://user:secret@erp.example.cn',
    '//erp.example.cn',
  ]) {
    assert.throws(
      () => loadDesktopConfig({
        DESKTOP_RELEASE_CHANNEL: 'internal-test',
        DESKTOP_SERVER_URL: url,
      }),
      /server URL/,
    )
  }
})

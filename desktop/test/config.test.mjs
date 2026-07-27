import test from 'node:test'
import assert from 'node:assert/strict'

import { loadDesktopConfig } from '../src/config.mjs'

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

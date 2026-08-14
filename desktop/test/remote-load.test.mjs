import test from 'node:test'
import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'

import {
  checkRemoteHealth,
  loadRemoteWithFallback,
  validateHealthResponse,
} from '../src/remote-load.mjs'

const ORIGIN = 'https://erp.example.cn'
const HEALTH_URL = `${ORIGIN}/api/health`

function healthyResponse(url = HEALTH_URL) {
  return {
    ok: true,
    url,
    json: async () => ({
      success: true,
      data: { status: 'ok' },
    }),
  }
}

test('health request rejects redirects and accepts an exact-origin response', async () => {
  let options
  const fetchImpl = async (_url, value) => {
    options = value
    return healthyResponse()
  }

  const result = await checkRemoteHealth({
    fetchImpl,
    healthUrl: HEALTH_URL,
    allowedOrigin: ORIGIN,
    timeoutMs: 8000,
  })

  assert.equal(result, true)
  assert.equal(options.redirect, 'error')
  assert.equal(options.method, 'GET')
  assert.equal(options.cache, 'no-store')
  assert.ok(options.signal instanceof AbortSignal)
})

test('health validation rejects a cross-origin final response URL', async () => {
  assert.equal(
    await validateHealthResponse(
      healthyResponse('https://login.example.com/api/health'),
      ORIGIN,
    ),
    false,
  )
})

test('health validation rejects an HTTPS to HTTP final URL downgrade', async () => {
  assert.equal(
    await validateHealthResponse(
      healthyResponse('http://erp.example.cn/api/health'),
      ORIGIN,
    ),
    false,
  )
})

test('health validation requires the ERP health payload', async () => {
  assert.equal(
    await validateHealthResponse({
      ok: true,
      url: HEALTH_URL,
      json: async () => ({ success: true, data: { status: 'starting' } }),
    }, ORIGIN),
    false,
  )
})

test('health validation accepts Electron net.fetch responses with an empty URL', async () => {
  const response = {
    ok: true,
    status: 200,
    url: '',
    async json() {
      return {
        success: true,
        data: { status: 'ok' },
      }
    },
  }

  assert.equal(
    await validateHealthResponse(
      response,
      ORIGIN,
      `${ORIGIN}/api/health`,
    ),
    true,
  )
})

function createFakeWindow(remoteLoad) {
  const webContents = new EventEmitter()
  const calls = []
  const window = {
    webContents,
    async loadURL(url) {
      calls.push(url)
      if (url === ORIGIN) return remoteLoad(webContents)
      return undefined
    },
  }
  return { calls, window }
}

test('remote load rejection shows the local unavailable page without bubbling', async () => {
  const { calls, window } = createFakeWindow(async () => {
    throw new Error('ERR_CONNECTION_RESET')
  })

  const loaded = await loadRemoteWithFallback({
    window,
    remoteUrl: ORIGIN,
  })

  assert.equal(loaded, false)
  assert.deepEqual(calls, [ORIGIN, 'app://unavailable/'])
})

test('terminal main-frame failure falls back even if loadURL resolves', async () => {
  const { calls, window } = createFakeWindow(async (webContents) => {
    webContents.emit(
      'did-fail-load',
      {},
      -105,
      'ERR_NAME_NOT_RESOLVED',
      ORIGIN,
      true,
    )
  })

  const loaded = await loadRemoteWithFallback({
    window,
    remoteUrl: ORIGIN,
  })

  assert.equal(loaded, false)
  assert.deepEqual(calls, [ORIGIN, 'app://unavailable/'])
})

test('subframe load failure does not replace a successful remote main frame', async () => {
  const { calls, window } = createFakeWindow(async (webContents) => {
    webContents.emit(
      'did-fail-load',
      {},
      -105,
      'ERR_NAME_NOT_RESOLVED',
      'https://cdn.example.cn/frame',
      false,
    )
  })

  const loaded = await loadRemoteWithFallback({
    window,
    remoteUrl: ORIGIN,
  })

  assert.equal(loaded, true)
  assert.deepEqual(calls, [ORIGIN])
})

test('an explicit initial navigation block is not treated as remote success', async () => {
  let blockedListener
  const subscribeNavigationBlocked = (listener) => {
    blockedListener = listener
    return () => {
      blockedListener = undefined
    }
  }
  const { calls, window } = createFakeWindow(async () => {
    blockedListener?.('https://unexpected.example.com')
  })

  const loaded = await loadRemoteWithFallback({
    window,
    remoteUrl: ORIGIN,
    subscribeNavigationBlocked,
  })

  assert.equal(loaded, false)
  assert.deepEqual(calls, [ORIGIN, 'app://unavailable/'])
  assert.equal(blockedListener, undefined)
})

test('a failing fallback page does not recurse or reject the caller', async () => {
  const webContents = new EventEmitter()
  const calls = []
  const window = {
    webContents,
    async loadURL(url) {
      calls.push(url)
      if (url === ORIGIN) throw new Error('remote failed')
      throw new Error('fallback failed')
    },
  }

  const loaded = await loadRemoteWithFallback({
    window,
    remoteUrl: ORIGIN,
  })

  assert.equal(loaded, false)
  assert.deepEqual(calls, [ORIGIN, 'app://unavailable/'])
})

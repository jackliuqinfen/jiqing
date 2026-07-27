import test from 'node:test'
import assert from 'node:assert/strict'
import {
  existsSync,
  mkdtempSync,
  readFileSync,
  rmSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import {
  DesktopApiClient,
  SyncApiError,
} from '../src/sync/api-client.mjs'

const ORIGIN = 'https://erp.example.cn'

function jsonResponse(data, {
  status = 200,
  url = `${ORIGIN}/api/desktop/policy`,
} = {}) {
  return new Response(JSON.stringify({ success: status < 400, data }), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

test('authenticated JSON requests remain on the configured origin and unwrap data', async () => {
  const requests = []
  const client = new DesktopApiClient({
    origin: ORIGIN,
    async fetchImpl(url, options) {
      requests.push({ url: String(url), options })
      return jsonResponse({ enabled: true }, { url: String(url) })
    },
  })

  assert.deepEqual(await client.getPolicy('secret-token'), { enabled: true })
  assert.equal(requests[0].url, `${ORIGIN}/api/desktop/policy`)
  assert.equal(requests[0].options.headers.Authorization, 'Bearer secret-token')
  assert.equal(requests[0].options.redirect, 'manual')
})

test('loads the authenticated server identity from auth me', async () => {
  let requestedUrl = ''
  const client = new DesktopApiClient({
    origin: ORIGIN,
    async fetchImpl(url) {
      requestedUrl = String(url)
      return jsonResponse({ id: 'server-user-1' })
    },
  })

  assert.deepEqual(
    await client.getCurrentUser('token'),
    { id: 'server-user-1' },
  )
  assert.equal(requestedUrl, `${ORIGIN}/api/auth/me`)
})

test('manifest query encodes selected refs, cursor, and fixed page limit', async () => {
  let requestedUrl = ''
  const client = new DesktopApiClient({
    origin: ORIGIN,
    async fetchImpl(url) {
      requestedUrl = String(url)
      return jsonResponse({
        items: [],
        nextCursor: 'resume',
        hasMore: false,
        policyVersion: 1,
      })
    },
  })

  await client.getManifest('token', {
    projectRefs: ['project:p-1', 'audit:a-2'],
    cursor: 'opaque+cursor',
    limit: 200,
  })

  const parsed = new URL(requestedUrl)
  assert.equal(parsed.origin, ORIGIN)
  assert.equal(
    parsed.searchParams.get('projectRefs'),
    'project:p-1,audit:a-2',
  )
  assert.equal(parsed.searchParams.get('cursor'), 'opaque+cursor')
  assert.equal(parsed.searchParams.get('limit'), '200')
})

test('download rejects an outside-origin URL before making a request', async (t) => {
  const directory = mkdtempSync(join(tmpdir(), 'jiqing-api-client-'))
  t.after(() => rmSync(directory, { recursive: true, force: true }))
  let calls = 0
  const client = new DesktopApiClient({
    origin: ORIGIN,
    async fetchImpl() {
      calls += 1
      return new Response('unexpected')
    },
  })

  await assert.rejects(
    client.download(
      'token',
      'https://evil.example/file.pdf',
      join(directory, 'file.part'),
      () => {},
    ),
    /outside configured origin/i,
  )
  assert.equal(calls, 0)
})

test('download rejects credentialed URLs before making a request', async (t) => {
  const directory = mkdtempSync(join(tmpdir(), 'jiqing-api-client-'))
  t.after(() => rmSync(directory, { recursive: true, force: true }))
  let calls = 0
  const client = new DesktopApiClient({
    origin: ORIGIN,
    async fetchImpl() {
      calls += 1
      return new Response('unexpected')
    },
  })

  await assert.rejects(
    client.download(
      'token',
      'https://user:password@erp.example.cn/file.pdf',
      join(directory, 'file.part'),
      () => {},
    ),
    /invalid desktop API URL/i,
  )
  assert.equal(calls, 0)
})

test('download writes authenticated bytes and reports cumulative progress', async (t) => {
  const directory = mkdtempSync(join(tmpdir(), 'jiqing-api-client-'))
  t.after(() => rmSync(directory, { recursive: true, force: true }))
  const destination = join(directory, 'file.part')
  const progress = []
  const client = new DesktopApiClient({
    origin: ORIGIN,
    async fetchImpl(_url, options) {
      assert.equal(options.headers.Authorization, 'Bearer token')
      return new Response('contract')
    },
  })

  const bytes = await client.download(
    'token',
    '/api/desktop/sync/files/project_file/file-1/download',
    destination,
    (received) => progress.push(received),
  )

  assert.equal(bytes, 8)
  assert.equal(readFileSync(destination, 'utf8'), 'contract')
  assert.deepEqual(progress, [8])
})

test('maps authentication and permission responses to synchronization states', async () => {
  for (const [status, code] of [
    [401, 'waiting_for_login'],
    [403, 'permission_changed'],
  ]) {
    const client = new DesktopApiClient({
      origin: ORIGIN,
      async fetchImpl() {
        return jsonResponse(null, { status })
      },
    })

    await assert.rejects(
      client.getProjectRoots('token'),
      (error) => error instanceof SyncApiError && error.code === code,
    )
  }
})

test('aborts a request after the configured timeout', async () => {
  const client = new DesktopApiClient({
    origin: ORIGIN,
    timeoutMs: 5,
    fetchImpl(_url, { signal }) {
      return new Promise((_resolve, reject) => {
        signal.addEventListener('abort', () => {
          reject(signal.reason)
        }, { once: true })
      })
    },
  })

  await assert.rejects(
    client.getPolicy('token'),
    (error) => error instanceof SyncApiError && error.code === 'offline',
  )
})

test('timeout remains active while a download body is stalled', async (t) => {
  const directory = mkdtempSync(join(tmpdir(), 'jiqing-api-client-'))
  t.after(() => rmSync(directory, { recursive: true, force: true }))
  const destination = join(directory, 'file.part')
  const client = new DesktopApiClient({
    origin: ORIGIN,
    timeoutMs: 5,
    async fetchImpl(_url, { signal }) {
      return new Response(new ReadableStream({
        start(controller) {
          controller.enqueue(Buffer.from('partial'))
          signal.addEventListener('abort', () => {
            controller.error(signal.reason)
          }, { once: true })
          setTimeout(() => {
            try {
              controller.error(new Error('body fallback timeout'))
            } catch {
              // The abort path already closed the stream.
            }
          }, 50)
        },
      }))
    },
  })

  await assert.rejects(
    client.download(
      'token',
      '/api/desktop/sync/files/project_file/file-1/download',
      destination,
      () => {},
    ),
    (error) => error instanceof SyncApiError && error.code === 'offline',
  )
  assert.equal(existsSync(destination), false)
})

test('progress resets the idle timeout for a long download', async (t) => {
  const directory = mkdtempSync(join(tmpdir(), 'jiqing-api-client-'))
  t.after(() => rmSync(directory, { recursive: true, force: true }))
  const destination = join(directory, 'file.part')
  const client = new DesktopApiClient({
    origin: ORIGIN,
    timeoutMs: 15,
    async fetchImpl() {
      let timer
      return new Response(new ReadableStream({
        start(controller) {
          let sent = 0
          const push = () => {
            controller.enqueue(Buffer.from('x'))
            sent += 1
            if (sent === 4) {
              controller.close()
              return
            }
            timer = setTimeout(push, 8)
          }
          push()
        },
        cancel() {
          clearTimeout(timer)
        },
      }))
    },
  })

  assert.equal(
    await client.download(
      'token',
      '/api/desktop/sync/files/project_file/file-1/download',
      destination,
      () => {},
    ),
    4,
  )
})

test('follows a bounded same-origin HTTPS redirect and reauthenticates each hop', async () => {
  const requests = []
  const client = new DesktopApiClient({
    origin: ORIGIN,
    async fetchImpl(url, options) {
      requests.push({ url: String(url), authorization: options.headers.Authorization })
      if (requests.length === 1) {
        return new Response(null, {
          status: 302,
          headers: { location: '/api/desktop/policy-v2' },
        })
      }
      return jsonResponse({ enabled: true })
    },
  })

  assert.deepEqual(await client.getPolicy('token'), { enabled: true })
  assert.deepEqual(requests, [
    {
      url: `${ORIGIN}/api/desktop/policy`,
      authorization: 'Bearer token',
    },
    {
      url: `${ORIGIN}/api/desktop/policy-v2`,
      authorization: 'Bearer token',
    },
  ])
})

test('rejects cross-origin and excessive redirect chains', async () => {
  const crossOrigin = new DesktopApiClient({
    origin: ORIGIN,
    async fetchImpl() {
      return new Response(null, {
        status: 302,
        headers: { location: 'https://evil.example/policy' },
      })
    },
  })
  await assert.rejects(
    crossOrigin.getPolicy('token'),
    /outside configured origin/i,
  )

  let redirects = 0
  const excessive = new DesktopApiClient({
    origin: ORIGIN,
    async fetchImpl() {
      redirects += 1
      return new Response(null, {
        status: 302,
        headers: { location: `/redirect-${redirects}` },
      })
    },
  })
  await assert.rejects(excessive.getPolicy('token'), /too many redirects/i)
  assert.equal(redirects, 4)
})

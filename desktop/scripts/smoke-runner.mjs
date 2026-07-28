import assert from 'node:assert/strict'
import {
  spawn,
  spawnSync,
} from 'node:child_process'
import {
  closeSync,
  existsSync,
  mkdtempSync,
  openSync,
  readFileSync,
  rmSync,
} from 'node:fs'
import { createServer } from 'node:http'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

import electronPath from 'electron'

import { createSmokeFailure } from './smoke-diagnostics.mjs'

const desktopRoot = fileURLToPath(new URL('..', import.meta.url))
const smokeAppPath = fileURLToPath(
  new URL('../test/smoke-app.mjs', import.meta.url),
)
const PROCESS_TIMEOUT_MS = 30000
const RESULT_TIMEOUT_MS = 20000

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds))
}

function childHasExited(child) {
  return child.exitCode !== null || child.signalCode !== null
}

function waitForChildExit(child, timeoutMs = 5000) {
  if (childHasExited(child)) return Promise.resolve()
  return new Promise((resolve) => {
    const timeout = setTimeout(done, timeoutMs)
    child.once('exit', done)

    function done() {
      clearTimeout(timeout)
      child.removeListener('exit', done)
      resolve()
    }
  })
}

async function terminateProcessTree(child) {
  if (!child || childHasExited(child)) return
  if (process.platform === 'win32') {
    spawnSync(
      'taskkill.exe',
      ['/PID', String(child.pid), '/T', '/F'],
      {
        stdio: 'ignore',
        windowsHide: true,
      },
    )
  } else {
    child.kill('SIGKILL')
  }
  await waitForChildExit(child)
  if (!childHasExited(child)) child.kill('SIGKILL')
}

async function waitForFile(path, timeoutMs = RESULT_TIMEOUT_MS) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (existsSync(path)) return
    await delay(50)
  }
  throw new Error(`timed out waiting for smoke file: ${path}`)
}

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'))
}

function listen(server) {
  return new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      server.removeListener('error', reject)
      resolve(server.address())
    })
  })
}

function closeServer(server) {
  return new Promise((resolve, reject) => {
    server.close((error) => {
      if (error) reject(error)
      else resolve()
    })
  })
}

function technicalPage({ externalNavigationUrl = '' } = {}) {
  const navigationScript = externalNavigationUrl
    ? `setTimeout(() => { window.location.href = ${JSON.stringify(externalNavigationUrl)} }, 100)`
    : ''
  return `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8">
    <title>桌面客户端技术验证</title>
  </head>
  <body>
    <main>
      <h1>工程管理系统技术登录页</h1>
      <form aria-label="技术烟测登录表单">
        <label>测试账号 <input autocomplete="username" disabled></label>
        <button type="button" disabled>技术验证</button>
      </form>
    </main>
    <script>
      window.__desktopSmokeReady = fetch('/api/desktop/bootstrap', {
        cache: 'no-store'
      }).then(async (response) => {
        const payload = await response.json()
        return response.ok && payload.success === true
      })
      ${navigationScript}
    </script>
  </body>
</html>`
}

async function startTechnicalServer(options = {}) {
  const requests = []
  const server = createServer((request, response) => {
    requests.push({
      method: request.method,
      url: request.url,
    })
    response.setHeader('Cache-Control', 'no-store')
    if (request.method === 'GET' && request.url === '/api/health') {
      response.writeHead(200, { 'Content-Type': 'application/json' })
      response.end(JSON.stringify({
        success: true,
        data: { status: 'ok' },
      }))
      return
    }
    if (
      request.method === 'GET'
      && request.url === '/api/desktop/bootstrap'
    ) {
      response.writeHead(200, { 'Content-Type': 'application/json' })
      response.end(JSON.stringify({
        success: true,
        data: {
          environmentId: 'desktop-technical-smoke',
          minimumDesktopVersion: '0.0.0',
        },
      }))
      return
    }
    if (request.method === 'GET' && request.url === '/') {
      response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
      response.end(technicalPage(options))
      return
    }
    response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' })
    response.end('Not found')
  })
  const address = await listen(server)
  return {
    close: () => closeServer(server),
    origin: `http://127.0.0.1:${address.port}`,
    requests,
  }
}

async function reserveUnavailableOrigin() {
  const server = createServer((_request, response) => {
    response.writeHead(503)
    response.end()
  })
  const address = await listen(server)
  await closeServer(server)
  return `http://127.0.0.1:${address.port}`
}

function launchElectron({
  caseName,
  origin,
  readyPath,
  releaseChannel = 'internal-test',
  resultPath,
  userDataPath,
}) {
  const child = spawn(
    electronPath,
    ['--disable-gpu', smokeAppPath],
    {
      cwd: desktopRoot,
      env: {
        ...process.env,
        DESKTOP_RELEASE_CHANNEL: releaseChannel,
        DESKTOP_SERVER_URL: origin,
        DESKTOP_SMOKE_CASE: caseName,
        DESKTOP_SMOKE_READY: readyPath || '',
        DESKTOP_SMOKE_RESULT: resultPath,
        DESKTOP_SMOKE_USER_DATA: userDataPath,
      },
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    },
  )
  let stdout = ''
  let stderr = ''
  child.stdout.setEncoding('utf8')
  child.stderr.setEncoding('utf8')
  child.stdout.on('data', (chunk) => {
    stdout += chunk
  })
  child.stderr.on('data', (chunk) => {
    stderr += chunk
  })

  const completed = new Promise((resolve, reject) => {
    let settled = false
    let spawnError = null
    let terminationError = null
    let timedOut = false
    let timeout
    const settle = (callback, value) => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      callback(value)
    }
    timeout = setTimeout(() => {
      if (settled) return
      timedOut = true
      void terminateProcessTree(child).catch((error) => {
        terminationError = error
      })
    }, PROCESS_TIMEOUT_MS)
    child.once('error', (error) => {
      spawnError = error
    })
    child.once('close', (code, signal) => {
      const result = { code, signal, stderr, stdout }
      if (spawnError || timedOut || terminationError) {
        settle(
          reject,
          createSmokeFailure({
            caseName,
            cause: spawnError || terminationError,
            completed: result,
            resultPath,
            timedOut,
          }),
        )
        return
      }
      settle(resolve, result)
    })
  })

  return {
    child,
    completed,
    snapshot: () => ({ stderr, stdout }),
    terminate: () => terminateProcessTree(child),
  }
}

async function withProcessDiagnostics({
  caseName,
  processResult,
  resultPath,
}, action) {
  try {
    return await action()
  } catch (error) {
    if (error?.smokeDiagnostic === true) throw error
    throw createSmokeFailure({
      caseName,
      cause: error,
      completed: processResult.snapshot(),
      resultPath,
    })
  }
}

function assertCleanExit(completed) {
  assert.equal(completed.code, 0)
  assert.equal(completed.signal, null)
}

async function runSuccessfulLoad(tempRoot) {
  const server = await startTechnicalServer()
  try {
    const resultPath = join(tempRoot, 'success.json')
    const processResult = launchElectron({
      caseName: 'successful-load',
      origin: server.origin,
      resultPath,
      userDataPath: join(tempRoot, 'success-user-data'),
    })
    await withProcessDiagnostics({
      caseName: 'successful-load',
      processResult,
      resultPath,
    }, async () => {
      const completed = await processResult.completed
      assertCleanExit(completed)
      assert.deepEqual(readJson(resultPath), {
        healthReady: true,
        remoteLoaded: true,
        nodeIntegration: false,
        contextIsolation: true,
        sandbox: true,
        loadedOrigin: server.origin,
      })
      assert.ok(server.requests.some(({ url }) => url === '/api/health'))
      assert.ok(server.requests.some(({ url }) => url === '/'))
      assert.ok(
        server.requests.some(({ url }) => url === '/api/desktop/bootstrap'),
      )
    })
  } finally {
    await server.close()
  }
}

async function runUnavailableServer(tempRoot) {
  const origin = await reserveUnavailableOrigin()
  const resultPath = join(tempRoot, 'unavailable.json')
  const processResult = launchElectron({
    caseName: 'server-unavailable',
    origin,
    resultPath,
    userDataPath: join(tempRoot, 'unavailable-user-data'),
  })
  await withProcessDiagnostics({
    caseName: 'server-unavailable',
    processResult,
    resultPath,
  }, async () => {
    const completed = await processResult.completed
    assertCleanExit(completed)
    assert.deepEqual(readJson(resultPath), {
      healthReady: false,
      remoteLoaded: false,
      loadedUrl: 'app://unavailable/',
    })
  })
}

async function runExternalNavigationDenied(tempRoot) {
  let server
  server = await startTechnicalServer({
    externalNavigationUrl: 'http://localhost:9/external-navigation',
  })
  try {
    const resultPath = join(tempRoot, 'navigation.json')
    const processResult = launchElectron({
      caseName: 'external-navigation',
      origin: server.origin,
      resultPath,
      userDataPath: join(tempRoot, 'navigation-user-data'),
    })
    await withProcessDiagnostics({
      caseName: 'external-navigation',
      processResult,
      resultPath,
    }, async () => {
      const completed = await processResult.completed
      assertCleanExit(completed)
      assert.deepEqual(readJson(resultPath), {
        externalNavigationDenied: true,
        blockedUrl: 'http://localhost:9/external-navigation',
        loadedOrigin: server.origin,
      })
    })
  } finally {
    await server.close()
  }
}

async function runProductionHttpRejected(tempRoot) {
  const resultPath = join(tempRoot, 'production-http.json')
  const processResult = launchElectron({
    caseName: 'production-http',
    origin: 'http://127.0.0.1:9',
    releaseChannel: 'production',
    resultPath,
    userDataPath: join(tempRoot, 'production-http-user-data'),
  })
  await withProcessDiagnostics({
    caseName: 'production-http',
    processResult,
    resultPath,
  }, async () => {
    const completed = await processResult.completed
    assert.notEqual(completed.code, 0)
    assert.deepEqual(readJson(resultPath), {
      configurationError: 'production desktop server URL requires HTTPS',
    })
  })
}

async function runSecondInstance(tempRoot) {
  const server = await startTechnicalServer()
  let primary = null
  let secondary = null
  try {
    const primaryResultPath = join(tempRoot, 'primary.json')
    const primaryReadyPath = join(tempRoot, 'primary.ready')
    const userDataPath = join(tempRoot, 'single-instance-user-data')
    primary = launchElectron({
      caseName: 'second-instance-primary',
      origin: server.origin,
      readyPath: primaryReadyPath,
      resultPath: primaryResultPath,
      userDataPath,
    })
    await withProcessDiagnostics({
      caseName: 'second-instance-primary-ready',
      processResult: primary,
      resultPath: primaryResultPath,
    }, () => waitForFile(primaryReadyPath))

    const secondaryResultPath = join(tempRoot, 'secondary.json')
    secondary = launchElectron({
      caseName: 'second-instance-secondary',
      origin: server.origin,
      resultPath: secondaryResultPath,
      userDataPath,
    })
    await withProcessDiagnostics({
      caseName: 'second-instance-secondary',
      processResult: secondary,
      resultPath: secondaryResultPath,
    }, async () => {
      const secondaryCompleted = await secondary.completed
      assertCleanExit(secondaryCompleted)
      assert.deepEqual(readJson(secondaryResultPath), {
        ownsSingleInstance: false,
      })
    })
    await withProcessDiagnostics({
      caseName: 'second-instance-primary',
      processResult: primary,
      resultPath: primaryResultPath,
    }, async () => {
      const primaryCompleted = await primary.completed
      assertCleanExit(primaryCompleted)
      assert.deepEqual(readJson(primaryResultPath), {
        secondInstanceFocused: true,
      })
    })
  } finally {
    await Promise.all([
      primary?.terminate(),
      secondary?.terminate(),
    ])
    await server.close()
  }
}

export async function runSmokeSuite() {
  if (!existsSync(electronPath)) {
    throw new Error(
      'Electron runtime is missing; run npm exec install-electron first',
    )
  }
  const tempRoot = mkdtempSync(join(tmpdir(), 'jiqing-desktop-smoke-'))
  try {
    closeSync(openSync(join(tempRoot, '.smoke-root'), 'wx', 0o600))
    await runSuccessfulLoad(tempRoot)
    process.stdout.write('smoke: successful remote load passed\n')
    await runUnavailableServer(tempRoot)
    process.stdout.write('smoke: unavailable server fallback passed\n')
    await runExternalNavigationDenied(tempRoot)
    process.stdout.write('smoke: external navigation denial passed\n')
    await runProductionHttpRejected(tempRoot)
    process.stdout.write('smoke: production HTTP rejection passed\n')
    await runSecondInstance(tempRoot)
    process.stdout.write('smoke: second-instance focus passed\n')
  } catch (error) {
    if (process.env.DESKTOP_SMOKE_KEEP_TEMP === '1') {
      process.stderr.write(`smoke: retained diagnostics at ${tempRoot}\n`)
    }
    throw error
  } finally {
    if (process.env.DESKTOP_SMOKE_KEEP_TEMP !== '1') {
      rmSync(tempRoot, { force: true, recursive: true })
    }
  }
}

await runSmokeSuite()

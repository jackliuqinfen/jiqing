import { open, rm } from 'node:fs/promises'

const REDIRECT_STATUSES = new Set([301, 302, 303, 307, 308])
const MAX_REDIRECTS = 3

export class SyncApiError extends Error {
  constructor(message, code, options = {}) {
    super(message, options)
    this.name = 'SyncApiError'
    this.code = code
  }
}

function validateToken(token) {
  if (typeof token !== 'string' || token.length === 0) {
    throw new SyncApiError('login required', 'waiting_for_login')
  }
}

export class DesktopApiClient {
  constructor({
    origin,
    fetchImpl = globalThis.fetch,
    timeoutMs = 30_000,
  }) {
    let parsedOrigin
    try {
      parsedOrigin = new URL(origin)
    } catch {
      throw new Error('invalid desktop API origin')
    }
    if (
      parsedOrigin.origin !== origin
      || !['http:', 'https:'].includes(parsedOrigin.protocol)
      || typeof fetchImpl !== 'function'
      || !Number.isInteger(timeoutMs)
      || timeoutMs < 1
    ) {
      throw new Error('invalid desktop API configuration')
    }
    this.origin = parsedOrigin.origin
    this.fetchImpl = fetchImpl
    this.timeoutMs = timeoutMs
    this.activeControllers = new Set()
  }

  resolveUrl(path) {
    let url
    try {
      url = new URL(path, `${this.origin}/`)
    } catch {
      throw new SyncApiError('invalid desktop API URL', 'request_failed')
    }
    if (url.username || url.password) {
      throw new SyncApiError('invalid desktop API URL', 'request_failed')
    }
    if (url.origin !== this.origin) {
      throw new SyncApiError(
        'desktop API URL is outside configured origin',
        'request_failed',
      )
    }
    return url
  }

  async request(token, path) {
    return this.withResponse(token, path, async (response) => {
      let payload
      try {
        payload = await response.json()
      } catch (cause) {
        throw new SyncApiError(
          'invalid desktop API response',
          'request_failed',
          { cause },
        )
      }
      if (
        !payload
        || payload.success !== true
        || !Object.hasOwn(payload, 'data')
      ) {
        throw new SyncApiError('desktop API request failed', 'request_failed')
      }
      return payload.data
    })
  }

  async withResponse(token, path, consume) {
    validateToken(token)
    let url = this.resolveUrl(path)
    const controller = new AbortController()
    this.activeControllers.add(controller)
    let timeout
    const resetIdleTimeout = () => {
      clearTimeout(timeout)
      timeout = setTimeout(() => {
        controller.abort(new Error('desktop API request idle timeout'))
      }, this.timeoutMs)
    }
    resetIdleTimeout()

    try {
      let response
      for (let redirectCount = 0; ; redirectCount += 1) {
        try {
          response = await this.fetchImpl(url, {
            method: 'GET',
            headers: {
              Accept: 'application/json',
              Authorization: `Bearer ${token}`,
            },
            redirect: 'manual',
            signal: controller.signal,
          })
        } catch (cause) {
          throw new SyncApiError('desktop API is unavailable', 'offline', {
            cause,
          })
        }
        resetIdleTimeout()
        if (!REDIRECT_STATUSES.has(response.status)) break
        if (redirectCount >= MAX_REDIRECTS) {
          throw new SyncApiError('too many redirects', 'request_failed')
        }
        const location = response.headers.get('location')
        if (!location) {
          throw new SyncApiError('invalid desktop API redirect', 'request_failed')
        }
        const redirected = this.resolveUrl(new URL(location, url).href)
        if (redirected.protocol !== 'https:') {
          throw new SyncApiError(
            'desktop API redirect requires HTTPS',
            'request_failed',
          )
        }
        url = redirected
      }
      if (response.url && new URL(response.url).origin !== this.origin) {
        throw new SyncApiError(
          'desktop API response is outside configured origin',
          'request_failed',
        )
      }
      if (response.status === 401) {
        throw new SyncApiError('login required', 'waiting_for_login')
      }
      if (response.status === 403) {
        throw new SyncApiError('permission changed', 'permission_changed')
      }
      if (!response.ok) {
        throw new SyncApiError('desktop API request failed', 'request_failed')
      }
      try {
        return await consume(response, resetIdleTimeout)
      } catch (error) {
        if (error instanceof SyncApiError) throw error
        if (controller.signal.aborted) {
          throw new SyncApiError('desktop API is unavailable', 'offline', {
            cause: error,
          })
        }
        throw error
      }
    } finally {
      clearTimeout(timeout)
      this.activeControllers.delete(controller)
    }
  }

  getPolicy(token) {
    return this.request(token, '/api/desktop/policy')
  }

  getCurrentUser(token) {
    return this.request(token, '/api/auth/me')
  }

  getProjectRoots(token) {
    return this.request(token, '/api/desktop/sync/projects')
  }

  getManifest(token, { projectRefs, cursor, limit = 200 }) {
    const params = new URLSearchParams()
    params.set('projectRefs', projectRefs.join(','))
    params.set('cursor', cursor || '')
    params.set('limit', String(limit))
    return this.request(
      token,
      `/api/desktop/sync/manifest?${params.toString()}`,
    )
  }

  async download(token, downloadPath, destinationPartPath, onProgress) {
    return this.withResponse(token, downloadPath, async (
      response,
      resetIdleTimeout,
    ) => {
      const handle = await open(destinationPartPath, 'w', 0o600)
      let received = 0
      try {
        if (response.body) {
          for await (const chunk of response.body) {
            resetIdleTimeout()
            const bytes = Buffer.from(chunk)
            await handle.write(bytes)
            received += bytes.length
            onProgress(received)
            resetIdleTimeout()
          }
        } else {
          const bytes = Buffer.from(await response.arrayBuffer())
          await handle.write(bytes)
          received = bytes.length
          onProgress(received)
        }
        await handle.sync()
        return received
      } catch (error) {
        await handle.close().catch(() => {})
        await rm(destinationPartPath, { force: true }).catch(() => {})
        throw error
      } finally {
        await handle.close().catch(() => {})
      }
    })
  }

  abortAll() {
    for (const controller of this.activeControllers) {
      controller.abort(new Error('desktop synchronization paused'))
    }
    this.activeControllers.clear()
  }
}

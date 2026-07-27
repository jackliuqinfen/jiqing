import { isAllowedNavigation } from './security.mjs'

const DEFAULT_UNAVAILABLE_URL = 'app://unavailable/'

export async function validateHealthResponse(
  response,
  allowedOrigin,
  requestedUrl = '',
) {
  const responseUrl = (
    typeof response?.url === 'string' && response.url.length > 0
  )
    ? response.url
    : requestedUrl
  if (
    !response
    || response.ok !== true
    || !isAllowedNavigation(responseUrl, allowedOrigin)
  ) {
    return false
  }

  try {
    const finalUrl = new URL(responseUrl)
    const trustedOrigin = new URL(allowedOrigin)
    if (
      finalUrl.origin !== trustedOrigin.origin
      || finalUrl.protocol !== trustedOrigin.protocol
    ) {
      return false
    }

    const payload = await response.json()
    return payload?.success === true && payload?.data?.status === 'ok'
  } catch {
    return false
  }
}

export async function checkRemoteHealth({
  fetchImpl,
  healthUrl,
  allowedOrigin,
  onDiagnostic,
  timeoutMs,
}) {
  if (
    typeof fetchImpl !== 'function'
    || !Number.isInteger(timeoutMs)
    || timeoutMs < 1
    || timeoutMs > 30000
  ) {
    return false
  }

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetchImpl(healthUrl, {
      method: 'GET',
      cache: 'no-store',
      redirect: 'error',
      signal: controller.signal,
    })
    const valid = await validateHealthResponse(
      response,
      allowedOrigin,
      healthUrl,
    )
    if (typeof onDiagnostic === 'function') {
      onDiagnostic({
        ok: response.ok,
        status: response.status,
        url: response.url,
        valid,
      })
    }
    return valid
  } catch (error) {
    if (typeof onDiagnostic === 'function') {
      onDiagnostic({
        error: error instanceof Error ? error.message : String(error),
      })
    }
    return false
  } finally {
    clearTimeout(timeout)
  }
}

export async function loadRemoteWithFallback({
  window,
  remoteUrl,
  unavailableUrl = DEFAULT_UNAVAILABLE_URL,
  onLoadError,
  subscribeNavigationBlocked,
}) {
  if (
    !window
    || typeof window.loadURL !== 'function'
    || !window.webContents
    || typeof window.webContents.on !== 'function'
    || typeof window.webContents.removeListener !== 'function'
  ) {
    throw new Error('invalid remote window')
  }

  let remoteFailed = false
  let fallbackPromise = null
  let unsubscribeNavigationBlocked = () => {}

  const removeFailureListener = () => {
    window.webContents.removeListener('did-fail-load', onDidFailLoad)
  }
  const showUnavailable = () => {
    remoteFailed = true
    if (!fallbackPromise) {
      removeFailureListener()
      unsubscribeNavigationBlocked()
      fallbackPromise = Promise.resolve()
        .then(() => window.loadURL(unavailableUrl))
        .then(
          () => true,
          () => false,
        )
    }
    return fallbackPromise
  }
  const onDidFailLoad = (
    _event,
    _errorCode,
    _errorDescription,
    _validatedUrl,
    isMainFrame,
  ) => {
    if (isMainFrame === true) void showUnavailable()
  }

  window.webContents.on('did-fail-load', onDidFailLoad)
  if (typeof subscribeNavigationBlocked === 'function') {
    const unsubscribe = subscribeNavigationBlocked(() => {
      void showUnavailable()
    })
    if (typeof unsubscribe === 'function') {
      unsubscribeNavigationBlocked = unsubscribe
    }
  }

  try {
    await window.loadURL(remoteUrl)
    if (remoteFailed) await fallbackPromise
    return !remoteFailed
  } catch (error) {
    if (typeof onLoadError === 'function') onLoadError(error)
    await showUnavailable()
    return false
  } finally {
    removeFailureListener()
    unsubscribeNavigationBlocked()
  }
}

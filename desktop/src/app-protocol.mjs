import { readFileSync } from 'node:fs'
import { join } from 'node:path'

const PAGE_FILES = Object.freeze({
  splash: 'splash.html',
  connecting: 'connecting.html',
  unavailable: 'unavailable.html',
  incompatible: 'incompatible.html',
})
const BRAND_FILES = Object.freeze({
  '/splash-logo.png': Object.freeze({
    filename: 'splash-logo.png',
    contentType: 'image/png',
  }),
})

export function resolveAppPage(target, uiRoot) {
  if (typeof uiRoot !== 'string' || uiRoot.length === 0) return null

  let url
  try {
    url = new URL(target)
  } catch {
    return null
  }

  if (
    url.protocol !== 'app:'
    || url.username
    || url.password
    || url.port
    || (url.pathname !== '' && url.pathname !== '/')
    || url.search
    || url.hash
  ) {
    return null
  }

  const filename = PAGE_FILES[url.hostname]
  return filename ? join(uiRoot, filename) : null
}

export function resolveAppResource(target, uiRoot, assetsRoot) {
  const pagePath = resolveAppPage(target, uiRoot)
  if (pagePath) {
    return Object.freeze({
      path: pagePath,
      contentType: 'text/html; charset=utf-8',
    })
  }

  if (typeof assetsRoot !== 'string' || assetsRoot.length === 0) return null

  let url
  try {
    url = new URL(target)
  } catch {
    return null
  }
  if (
    url.protocol !== 'app:'
    || url.hostname !== 'brand'
    || url.username
    || url.password
    || url.port
    || url.search
    || url.hash
  ) {
    return null
  }

  const resource = BRAND_FILES[url.pathname]
  return resource
    ? Object.freeze({
        path: join(assetsRoot, resource.filename),
        contentType: resource.contentType,
      })
    : null
}

export function registerAppProtocol(protocol, _net, uiRoot, assetsRoot = '') {
  protocol.handle('app', (request) => {
    const resource = resolveAppResource(request.url, uiRoot, assetsRoot)
    if (!resource) {
      return new Response('Not found', {
        status: 404,
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'Cache-Control': 'no-store',
        },
      })
    }
    try {
      return new Response(readFileSync(resource.path), {
        status: 200,
        headers: {
          'Content-Type': resource.contentType,
          'Cache-Control': 'no-store',
          'X-Content-Type-Options': 'nosniff',
        },
      })
    } catch {
      return new Response('Unavailable', {
        status: 500,
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'Cache-Control': 'no-store',
        },
      })
    }
  })
}

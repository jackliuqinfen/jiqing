import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

const PAGE_FILES = Object.freeze({
  connecting: 'connecting.html',
  unavailable: 'unavailable.html',
  incompatible: 'incompatible.html',
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

export function registerAppProtocol(protocol, net, uiRoot) {
  protocol.handle('app', (request) => {
    const pagePath = resolveAppPage(request.url, uiRoot)
    if (!pagePath) {
      return new Response('Not found', {
        status: 404,
        headers: {
          'Content-Type': 'text/plain; charset=utf-8',
          'Cache-Control': 'no-store',
        },
      })
    }
    return net.fetch(pathToFileURL(pagePath).toString())
  })
}

const MIN_WINDOW_WIDTH = 1100
const MIN_WINDOW_HEIGHT = 720
const MAX_WINDOW_WIDTH = 8192
const MAX_WINDOW_HEIGHT = 4320
const MIN_VISIBLE_WIDTH = 120
const MIN_VISIBLE_HEIGHT = 80

function parseHttpUrl(value) {
  if (typeof value !== 'string' || value.length === 0) return null

  try {
    const url = new URL(value)
    if (
      !['http:', 'https:'].includes(url.protocol)
      || !url.hostname
      || url.username
      || url.password
    ) {
      return null
    }
    return url
  } catch {
    return null
  }
}

function normalizeAllowedOrigin(value) {
  const url = parseHttpUrl(value)
  if (!url || url.origin !== value) return null
  return url.origin
}

export function isAllowedNavigation(target, allowedOrigin) {
  const origin = normalizeAllowedOrigin(allowedOrigin)
  const url = parseHttpUrl(target)
  return Boolean(origin && url && url.origin === origin)
}

export function assertTrustedSender(frameUrl, allowedOrigin) {
  if (!isAllowedNavigation(frameUrl, allowedOrigin)) {
    throw new Error('untrusted ipc sender')
  }
}

export function isReviewedExternalUrl(target, allowedOrigin) {
  const origin = normalizeAllowedOrigin(allowedOrigin)
  const url = parseHttpUrl(target)
  return Boolean(
    origin
    && url
    && url.protocol === 'https:'
    && url.origin !== origin,
  )
}

export function createSecureWebPreferences({ preload, partition }) {
  if (
    typeof preload !== 'string'
    || preload.length === 0
    || typeof partition !== 'string'
    || partition.length === 0
    || partition.startsWith('persist:')
  ) {
    throw new Error('invalid secure web preferences')
  }

  return Object.freeze({
    preload,
    partition,
    nodeIntegration: false,
    contextIsolation: true,
    sandbox: true,
    webSecurity: true,
    allowRunningInsecureContent: false,
  })
}

function isIntegerInRange(value, minimum, maximum) {
  return Number.isInteger(value) && value >= minimum && value <= maximum
}

function visibleIntersection(bounds, workArea) {
  const left = Math.max(bounds.x, workArea.x)
  const top = Math.max(bounds.y, workArea.y)
  const right = Math.min(bounds.x + bounds.width, workArea.x + workArea.width)
  const bottom = Math.min(bounds.y + bounds.height, workArea.y + workArea.height)
  return {
    width: Math.max(0, right - left),
    height: Math.max(0, bottom - top),
  }
}

export function normalizeWindowBounds(value, displays) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null

  const bounds = {
    x: value.x,
    y: value.y,
    width: value.width,
    height: value.height,
  }
  if (
    !isIntegerInRange(bounds.x, -100000, 100000)
    || !isIntegerInRange(bounds.y, -100000, 100000)
    || !isIntegerInRange(bounds.width, MIN_WINDOW_WIDTH, MAX_WINDOW_WIDTH)
    || !isIntegerInRange(bounds.height, MIN_WINDOW_HEIGHT, MAX_WINDOW_HEIGHT)
  ) {
    return null
  }

  const validDisplays = Array.isArray(displays) ? displays : []
  const isVisible = validDisplays.some((display) => {
    const area = display?.workArea
    if (
      !area
      || !Number.isFinite(area.x)
      || !Number.isFinite(area.y)
      || !Number.isFinite(area.width)
      || !Number.isFinite(area.height)
      || area.width <= 0
      || area.height <= 0
    ) {
      return false
    }
    const intersection = visibleIntersection(bounds, area)
    return (
      intersection.width >= MIN_VISIBLE_WIDTH
      && intersection.height >= MIN_VISIBLE_HEIGHT
    )
  })

  return isVisible ? Object.freeze(bounds) : null
}

const RELEASE_CHANNELS = new Set([
  'development',
  'internal-test',
  'production',
])

const ENVIRONMENT_LABELS = Object.freeze({
  development: '开发环境',
  'internal-test': '内部测试',
  production: '',
})

function parseServerOrigin(value) {
  if (typeof value !== 'string' || value.trim() !== value || value.length === 0) {
    throw new Error('invalid desktop server URL')
  }

  let url
  try {
    url = new URL(value)
  } catch {
    throw new Error('invalid desktop server URL')
  }

  if (
    !['http:', 'https:'].includes(url.protocol)
    || !url.hostname
    || url.username
    || url.password
  ) {
    throw new Error('invalid desktop server URL')
  }

  return Object.freeze({
    origin: url.origin,
    protocol: url.protocol,
  })
}

export function loadDesktopConfig(env = {}) {
  const releaseChannel = String(env.DESKTOP_RELEASE_CHANNEL || '').trim()
  if (!RELEASE_CHANNELS.has(releaseChannel)) {
    throw new Error('invalid desktop release channel')
  }

  const parsed = parseServerOrigin(env.DESKTOP_SERVER_URL)
  if (releaseChannel === 'production' && parsed.protocol !== 'https:') {
    throw new Error('production desktop server URL requires HTTPS')
  }

  return Object.freeze({
    releaseChannel,
    origin: parsed.origin,
    environmentLabel: ENVIRONMENT_LABELS[releaseChannel],
    healthUrl: `${parsed.origin}/api/health`,
    bootstrapUrl: `${parsed.origin}/api/desktop/bootstrap`,
    healthTimeoutMs: 8000,
  })
}

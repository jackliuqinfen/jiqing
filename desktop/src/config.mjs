import { readFileSync } from 'node:fs'

const RELEASE_CHANNELS = new Set([
  'development',
  'internal-test',
  'production',
])
const EMBEDDED_PROFILE_SCHEMA_VERSION = 1

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

function configFromEnvironment(env) {
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

export function validateEmbeddedReleaseProfile(value) {
  if (
    !value
    || typeof value !== 'object'
    || Array.isArray(value)
    || value.schemaVersion !== EMBEDDED_PROFILE_SCHEMA_VERSION
    || !RELEASE_CHANNELS.has(value.releaseChannel)
  ) {
    throw new Error('invalid embedded release profile')
  }

  const parsed = parseServerOrigin(value.serverOrigin)
  if (value.releaseChannel === 'production' && parsed.protocol !== 'https:') {
    throw new Error('production desktop server URL requires HTTPS')
  }

  return Object.freeze({
    schemaVersion: EMBEDDED_PROFILE_SCHEMA_VERSION,
    releaseChannel: value.releaseChannel,
    serverOrigin: parsed.origin,
  })
}

export function readEmbeddedReleaseProfile(profileUrl) {
  try {
    const parsed = JSON.parse(readFileSync(profileUrl, 'utf8'))
    return validateEmbeddedReleaseProfile(parsed)
  } catch (error) {
    if (
      error instanceof Error
      && (
        error.message.includes('embedded release profile')
        || error.message.includes('requires HTTPS')
      )
    ) {
      throw error
    }
    throw new Error('invalid embedded release profile')
  }
}

export function createEmbeddedReleaseProfile(env = {}) {
  const config = configFromEnvironment(env)
  return Object.freeze({
    schemaVersion: EMBEDDED_PROFILE_SCHEMA_VERSION,
    releaseChannel: config.releaseChannel,
    serverOrigin: config.origin,
  })
}

export function loadDesktopConfig(input = {}) {
  const usesOptionsShape = (
    Object.hasOwn(input, 'isPackaged')
    || Object.hasOwn(input, 'embeddedProfile')
    || Object.hasOwn(input, 'env')
  )
  if (!usesOptionsShape) return configFromEnvironment(input)

  const {
    embeddedProfile,
    env = {},
    isPackaged = false,
  } = input
  if (!isPackaged) return configFromEnvironment(env)

  const profile = validateEmbeddedReleaseProfile(embeddedProfile)
  return configFromEnvironment({
    DESKTOP_RELEASE_CHANNEL: profile.releaseChannel,
    DESKTOP_SERVER_URL: profile.serverOrigin,
  })
}

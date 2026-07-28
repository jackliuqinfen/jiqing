import { pathToFileURL } from 'node:url'

function parseOrigin(value) {
  if (
    typeof value !== 'string'
    || value.length === 0
    || value.trim() !== value
  ) {
    throw new Error('desktop release origin is required')
  }

  let url
  try {
    url = new URL(value)
  } catch {
    throw new Error('desktop release origin is invalid')
  }
  if (
    !['http:', 'https:'].includes(url.protocol)
    || !url.hostname
    || url.username
    || url.password
  ) {
    throw new Error('desktop release origin is invalid')
  }
  return url
}

function requireSecret(value, name) {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new Error(`${name} is required for production release`)
  }
}

function normalizeSignerSha256(value) {
  if (
    typeof value !== 'string'
    || !/^[0-9a-f]{64}$/i.test(value.trim())
  ) {
    throw new Error(
      'WINDOWS_EXPECTED_SIGNER_SHA256 must be a 64-character hex fingerprint',
    )
  }
  return value.trim().toUpperCase()
}

export function validateReleaseConfiguration({
  certificateBase64 = '',
  certificatePassword = '',
  expectedSignerSha256 = '',
  channel,
  origin,
}) {
  if (!['internal-test', 'production'].includes(channel)) {
    throw new Error('desktop release channel must be internal-test or production')
  }
  const parsedOrigin = parseOrigin(origin)
  if (channel === 'production') {
    if (parsedOrigin.protocol !== 'https:') {
      throw new Error('production release origin requires HTTPS')
    }
    requireSecret(certificateBase64, 'WINDOWS_CERTIFICATE_BASE64')
    requireSecret(certificatePassword, 'WINDOWS_CERTIFICATE_PASSWORD')
    const normalizedSigner = normalizeSignerSha256(expectedSignerSha256)
    return Object.freeze({
      channel,
      expectedSignerSha256: normalizedSigner,
      origin: parsedOrigin.origin,
      requiresSigning: true,
    })
  }

  return Object.freeze({
    channel,
    origin: parsedOrigin.origin,
    requiresSigning: false,
  })
}

export function validateWindowsBuildConfiguration({
  certificateBase64 = '',
  certificatePassword = '',
  expectedSignerSha256 = '',
  channel,
  mode,
  origin,
}) {
  if (!['dir', 'nsis', 'production'].includes(mode)) {
    throw new Error('build mode must be dir, nsis, or production')
  }
  if (mode === 'production') {
    if (channel !== 'production') {
      throw new Error('production build mode requires production release')
    }
    return validateReleaseConfiguration({
      certificateBase64,
      certificatePassword,
      expectedSignerSha256,
      channel,
      origin,
    })
  }
  if (channel === 'production') {
    throw new Error('production release must use the production build mode')
  }
  if (channel === 'internal-test') {
    return validateReleaseConfiguration({
      channel,
      origin,
    })
  }
  if (channel !== 'development') {
    throw new Error('desktop build channel is invalid')
  }
  return Object.freeze({
    channel,
    origin: parseOrigin(origin).origin,
    requiresSigning: false,
  })
}

if (
  process.argv[1]
  && import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const result = validateReleaseConfiguration({
    certificateBase64: process.env.WINDOWS_CERTIFICATE_BASE64,
    certificatePassword: process.env.WINDOWS_CERTIFICATE_PASSWORD,
    expectedSignerSha256: process.env.WINDOWS_EXPECTED_SIGNER_SHA256,
    channel: process.env.DESKTOP_RELEASE_CHANNEL,
    origin: process.env.DESKTOP_SERVER_URL,
  })
  process.stdout.write(
    `Release gate accepted ${result.channel} origin ${result.origin}\n`,
  )
}

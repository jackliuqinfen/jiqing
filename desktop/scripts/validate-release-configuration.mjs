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

export function validateReleaseConfiguration({
  certificateBase64 = '',
  certificatePassword = '',
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
  }

  return Object.freeze({
    channel,
    origin: parsedOrigin.origin,
    requiresSigning: channel === 'production',
  })
}

if (
  process.argv[1]
  && import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const result = validateReleaseConfiguration({
    certificateBase64: process.env.WINDOWS_CERTIFICATE_BASE64,
    certificatePassword: process.env.WINDOWS_CERTIFICATE_PASSWORD,
    channel: process.env.DESKTOP_RELEASE_CHANNEL,
    origin: process.env.DESKTOP_SERVER_URL,
  })
  process.stdout.write(
    `Release gate accepted ${result.channel} origin ${result.origin}\n`,
  )
}

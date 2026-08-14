import {
  mkdirSync,
  writeFileSync,
} from 'node:fs'
import { dirname } from 'node:path'
import {
  fileURLToPath,
  pathToFileURL,
} from 'node:url'

import { createEmbeddedReleaseProfile } from '../src/config.mjs'

const DEFAULT_OUTPUT_URL = new URL(
  '../src/release-profile.generated.json',
  import.meta.url,
)

export function serializeReleaseProfile(profile) {
  return `${JSON.stringify({
    schemaVersion: profile.schemaVersion,
    releaseChannel: profile.releaseChannel,
    serverOrigin: profile.serverOrigin,
  }, null, 2)}\n`
}

export function writeReleaseProfile({
  env = process.env,
  outputUrl = DEFAULT_OUTPUT_URL,
} = {}) {
  const profile = createEmbeddedReleaseProfile(env)
  const outputPath = fileURLToPath(outputUrl)
  mkdirSync(dirname(outputPath), { recursive: true })
  writeFileSync(outputPath, serializeReleaseProfile(profile), {
    encoding: 'utf8',
    mode: 0o600,
  })
  return { outputPath, profile }
}

if (
  process.argv[1]
  && import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const { outputPath, profile } = writeReleaseProfile()
  process.stdout.write(
    `Embedded ${profile.releaseChannel} release profile: ${outputPath}\n`,
  )
}

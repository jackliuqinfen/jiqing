import { extractFile } from '@electron/asar'
import {
  FuseState,
  FuseV1Options,
  FuseVersion,
  getCurrentFuseWire,
} from '@electron/fuses'
import {
  existsSync,
  readFileSync,
  statSync,
} from 'node:fs'
import { resolve } from 'node:path'
import {
  fileURLToPath,
  pathToFileURL,
} from 'node:url'
import yaml from 'js-yaml'

import { validateEmbeddedReleaseProfile } from '../src/config.mjs'

const EXPECTED_FUSE_STATES = Object.freeze({
  [FuseV1Options.RunAsNode]: FuseState.DISABLE,
  [FuseV1Options.EnableCookieEncryption]: FuseState.ENABLE,
  [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: FuseState.DISABLE,
  [FuseV1Options.EnableNodeCliInspectArguments]: FuseState.DISABLE,
  [FuseV1Options.EnableEmbeddedAsarIntegrityValidation]: FuseState.ENABLE,
  [FuseV1Options.OnlyLoadAppFromAsar]: FuseState.ENABLE,
  [FuseV1Options.LoadBrowserProcessSpecificV8Snapshot]: FuseState.DISABLE,
  [FuseV1Options.GrantFileProtocolExtraPrivileges]: FuseState.DISABLE,
  [FuseV1Options.WasmTrapHandlers]: FuseState.ENABLE,
})

export function assertHardenedFuseWire(wire) {
  if (!wire || wire.version !== FuseVersion.V1) {
    throw new Error('packaged executable has an unsupported fuse version')
  }

  for (const [key, expected] of Object.entries(EXPECTED_FUSE_STATES)) {
    if (wire[key] !== expected) {
      throw new Error(
        `packaged executable fuse ${FuseV1Options[key]} is not hardened`,
      )
    }
  }
}

export function validatePackagedReleaseProfile(
  value,
  { expectedChannel, expectedOrigin },
) {
  const profile = validateEmbeddedReleaseProfile(value)
  if (profile.releaseChannel !== expectedChannel) {
    throw new Error('packaged release channel does not match the build')
  }
  if (profile.serverOrigin !== new URL(expectedOrigin).origin) {
    throw new Error('packaged server origin does not match the build')
  }
  return profile
}

export function readPackagedReleaseProfile(asarPath) {
  try {
    const contents = extractFile(
      asarPath,
      'src/release-profile.generated.json',
    )
    return JSON.parse(contents.toString('utf8'))
  } catch {
    throw new Error('packaged release profile is missing or unreadable')
  }
}

export function validatePackagedUpdateConfiguration(
  value,
  { expectedChannel, expectedOrigin },
) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('packaged update configuration is invalid')
  }
  const expectedUrl = new URL(
    `/desktop-updates/${expectedChannel}`,
    expectedOrigin,
  ).href.replace(/\/$/, '')
  if (value.provider !== 'generic' || value.url !== expectedUrl) {
    throw new Error('packaged update feed does not match the trusted server')
  }
  return Object.freeze({
    provider: value.provider,
    url: value.url,
  })
}

export async function inspectPackagedApp({
  appDirectory,
  expectedChannel,
  expectedOrigin,
}) {
  const applicationPath = resolve(appDirectory)
  const executablePath = resolve(applicationPath, 'JiqingERP.exe')
  const asarPath = resolve(applicationPath, 'resources', 'app.asar')
  const updateConfigurationPath = resolve(
    applicationPath,
    'resources',
    'app-update.yml',
  )
  for (const path of [executablePath, asarPath, updateConfigurationPath]) {
    if (!existsSync(path) || !statSync(path).isFile()) {
      throw new Error(`packaged artifact is missing: ${path}`)
    }
  }

  const fuseWire = await getCurrentFuseWire(executablePath)
  assertHardenedFuseWire(fuseWire)
  const profile = validatePackagedReleaseProfile(
    readPackagedReleaseProfile(asarPath),
    { expectedChannel, expectedOrigin },
  )
  const updateConfiguration = validatePackagedUpdateConfiguration(
    yaml.load(readFileSync(updateConfigurationPath, 'utf8')),
    { expectedChannel, expectedOrigin },
  )

  return Object.freeze({
    applicationPath,
    asarPath,
    asarBytes: statSync(asarPath).size,
    executablePath,
    executableBytes: statSync(executablePath).size,
    profile,
    updateConfiguration,
  })
}

if (
  process.argv[1]
  && import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const appDirectory = process.argv[2] || fileURLToPath(
    new URL('../dist/win-unpacked', import.meta.url),
  )
  const result = await inspectPackagedApp({
    appDirectory,
    expectedChannel: process.env.DESKTOP_RELEASE_CHANNEL,
    expectedOrigin: process.env.DESKTOP_SERVER_URL,
  })
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`)
}

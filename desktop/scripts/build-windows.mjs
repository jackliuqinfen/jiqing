import { spawnSync } from 'node:child_process'
import {
  cpSync,
  existsSync,
  mkdtempSync,
  mkdirSync,
  realpathSync,
  rmSync,
} from 'node:fs'
import {
  isAbsolute,
  join,
  relative,
  resolve,
} from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  validateWindowsBuildConfiguration,
} from './validate-release-configuration.mjs'
import { verifyWindowsSignatures } from './verify-windows-signatures.mjs'
import { writePackagedUpdateConfig } from './write-update-config.mjs'

const MAX_BUILD_ATTEMPTS = 3
const BUILD_RETRY_DELAY_MS = 1500

function assertDescendant(target, parent, label) {
  const resolvedParent = realpathSync(parent)
  const resolvedTarget = existsSync(target)
    ? realpathSync(target)
    : resolve(target)
  const pathFromParent = relative(resolvedParent, resolvedTarget)
  if (
    pathFromParent.length === 0
    || pathFromParent.startsWith('..')
    || isAbsolute(pathFromParent)
  ) {
    throw new Error(`${label} escapes its trusted parent directory`)
  }
}

const mode = process.argv[2]
const desktopRoot = fileURLToPath(new URL('..', import.meta.url))
const builderCli = fileURLToPath(
  new URL('../node_modules/electron-builder/out/cli/cli.js', import.meta.url),
)
const distRoot = join(desktopRoot, 'dist')
const temporaryRootPath = join(desktopRoot, '.tmp')
mkdirSync(temporaryRootPath, { recursive: true })
const temporaryRoot = realpathSync(temporaryRootPath)
assertDescendant(temporaryRoot, desktopRoot, 'temporary directory')
const installedElectronDist = realpathSync(
  join(desktopRoot, 'node_modules', 'electron', 'dist'),
)
assertDescendant(
  installedElectronDist,
  desktopRoot,
  'installed Electron distribution',
)
assertDescendant(distRoot, desktopRoot, 'desktop distribution directory')

validateWindowsBuildConfiguration({
  certificateBase64: process.env.CSC_LINK,
  certificatePassword: process.env.CSC_KEY_PASSWORD,
  expectedSignerSha256: process.env.WINDOWS_EXPECTED_SIGNER_SHA256,
  channel: process.env.DESKTOP_RELEASE_CHANNEL,
  mode,
  origin: process.env.DESKTOP_SERVER_URL,
})
const updateFeedUrl = new URL(
  `/desktop-updates/${process.env.DESKTOP_RELEASE_CHANNEL}`,
  process.env.DESKTOP_SERVER_URL,
).href.replace(/\/$/, '')
const buildEnvironment = {
  ...process.env,
  DESKTOP_UPDATE_URL: updateFeedUrl,
}

const shortBuildRoot = mkdtempSync(join(temporaryRoot, 'b-'))
const shortOutput = join(shortBuildRoot, 'o')

assertDescendant(shortBuildRoot, temporaryRoot, 'temporary build root')

function builderArguments(output) {
  const commonConfiguration = [
    '--config',
    'electron-builder.yml',
    `--config.electronDist=${installedElectronDist}`,
    `--config.directories.output=${output}`,
  ]
  if (mode === 'dir') {
    return ['--dir', '--win', ...commonConfiguration]
  }
  if (mode === 'nsis') {
    const unpackedPath = join(distRoot, 'win-unpacked')
    if (!existsSync(unpackedPath)) {
      throw new Error('verified unpacked application is missing')
    }
    return [
      '--win',
      'nsis',
      '--prepackaged',
      unpackedPath,
      '--config',
      'electron-builder.yml',
      `--config.directories.output=${output}`,
    ]
  }
  return [
    '--win',
    'nsis',
    ...commonConfiguration,
    '--config.forceCodeSigning=true',
  ]
}

function copyBuildOutput(output) {
  assertDescendant(output, shortBuildRoot, 'temporary build output')
  assertDescendant(distRoot, desktopRoot, 'desktop distribution directory')
  if (!existsSync(output)) {
    throw new Error('electron-builder produced no output')
  }
  if (mode === 'dir' || mode === 'production') {
    rmSync(distRoot, { force: true, recursive: true })
  }
  mkdirSync(distRoot, { recursive: true })
  cpSync(output, distRoot, {
    force: true,
    recursive: true,
  })
}

try {
  let completedOutput = ''
  let lastExitCode = null
  for (let attempt = 1; attempt <= MAX_BUILD_ATTEMPTS; attempt += 1) {
    const attemptOutput = `${shortOutput}-${attempt}`
    const result = spawnSync(
      process.execPath,
      [builderCli, ...builderArguments(attemptOutput)],
      {
        cwd: desktopRoot,
        env: buildEnvironment,
        stdio: 'inherit',
      },
    )
    if (result.error) throw result.error
    lastExitCode = result.status
    if (result.status === 0) {
      completedOutput = attemptOutput
      break
    }
    if (attempt < MAX_BUILD_ATTEMPTS) {
      process.stderr.write(
        `electron-builder attempt ${attempt} failed; retrying in `
          + `${BUILD_RETRY_DELAY_MS} ms\n`,
      )
      await new Promise((resolve) => {
        setTimeout(resolve, BUILD_RETRY_DELAY_MS)
      })
    }
  }
  if (!completedOutput) {
    throw new Error(
      `electron-builder failed after ${MAX_BUILD_ATTEMPTS} attempts `
        + `(last exit code ${lastExitCode})`,
    )
  }
  copyBuildOutput(completedOutput)
  if (mode === 'dir') {
    writePackagedUpdateConfig({
      appDirectory: join(distRoot, 'win-unpacked'),
      updateFeedUrl,
    })
  }
  if (mode === 'production') {
    verifyWindowsSignatures({
      distRoot,
      expectedSignerSha256: process.env.WINDOWS_EXPECTED_SIGNER_SHA256,
    })
  }
} finally {
  assertDescendant(shortBuildRoot, temporaryRoot, 'temporary build root')
  rmSync(shortBuildRoot, { force: true, recursive: true })
}

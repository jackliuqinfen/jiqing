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
const trustedBuildParentPath = join(temporaryRoot, 'windows-build')
mkdirSync(trustedBuildParentPath, { recursive: true })
const trustedBuildParent = realpathSync(trustedBuildParentPath)
assertDescendant(
  trustedBuildParent,
  desktopRoot,
  'temporary build parent',
)
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
  channel: process.env.DESKTOP_RELEASE_CHANNEL,
  mode,
  origin: process.env.DESKTOP_SERVER_URL,
})

const shortBuildRoot = mkdtempSync(
  join(trustedBuildParent, 'run-'),
)
const shortOutput = join(shortBuildRoot, 'out')

assertDescendant(shortBuildRoot, trustedBuildParent, 'temporary build root')

function builderArguments() {
  const commonConfiguration = [
    '--config',
    'electron-builder.yml',
    `--config.electronDist=${installedElectronDist}`,
    `--config.directories.output=${shortOutput}`,
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
      `--config.directories.output=${shortOutput}`,
    ]
  }
  return [
    '--win',
    'nsis',
    ...commonConfiguration,
    '--config.forceCodeSigning=true',
  ]
}

function copyBuildOutput() {
  assertDescendant(shortOutput, shortBuildRoot, 'temporary build output')
  assertDescendant(distRoot, desktopRoot, 'desktop distribution directory')
  if (!existsSync(shortOutput)) {
    throw new Error('electron-builder produced no output')
  }
  if (mode === 'dir' || mode === 'production') {
    rmSync(distRoot, { force: true, recursive: true })
  }
  mkdirSync(distRoot, { recursive: true })
  cpSync(shortOutput, distRoot, {
    force: true,
    recursive: true,
  })
}

rmSync(shortBuildRoot, { force: true, recursive: true })
mkdirSync(shortOutput, { recursive: true })
try {
  const result = spawnSync(
    process.execPath,
    [builderCli, ...builderArguments()],
    {
      cwd: desktopRoot,
      env: process.env,
      stdio: 'inherit',
    },
  )
  if (result.error) throw result.error
  if (result.status !== 0) {
    throw new Error(`electron-builder failed with exit code ${result.status}`)
  }
  copyBuildOutput()
  if (mode === 'production') {
    verifyWindowsSignatures({ distRoot })
  }
} finally {
  assertDescendant(shortBuildRoot, trustedBuildParent, 'temporary build root')
  rmSync(shortBuildRoot, { force: true, recursive: true })
}

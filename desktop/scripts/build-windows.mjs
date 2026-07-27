import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import {
  cpSync,
  existsSync,
  mkdirSync,
  rmSync,
} from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const mode = process.argv[2]
if (!['dir', 'nsis', 'production'].includes(mode)) {
  throw new Error('build mode must be dir, nsis, or production')
}

const desktopRoot = fileURLToPath(new URL('..', import.meta.url))
const builderCli = fileURLToPath(
  new URL('../node_modules/electron-builder/out/cli/cli.js', import.meta.url),
)
const distRoot = join(desktopRoot, 'dist')
const buildId = createHash('sha256')
  .update(desktopRoot)
  .digest('hex')
  .slice(0, 8)
const shortBuildBase = process.env.PUBLIC || 'C:\\Users\\Public'
const shortBuildRoot = join(shortBuildBase, 'JiqingDesktopBuild', buildId)
const shortOutput = join(shortBuildRoot, 'out')

function builderArguments() {
  const common = [
    '--win',
    '--config',
    'electron-builder.yml',
    `--config.directories.output=${shortOutput}`,
  ]
  if (mode === 'dir') return ['--dir', ...common]
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
    '--config',
    'electron-builder.yml',
    '--config.forceCodeSigning=true',
    `--config.directories.output=${shortOutput}`,
  ]
}

function copyBuildOutput() {
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
} finally {
  rmSync(shortBuildRoot, { force: true, recursive: true })
}

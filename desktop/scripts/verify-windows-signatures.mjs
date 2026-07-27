import { spawnSync } from 'node:child_process'
import {
  existsSync,
  readdirSync,
} from 'node:fs'
import { join } from 'node:path'
import {
  fileURLToPath,
  pathToFileURL,
} from 'node:url'

const desktopRoot = fileURLToPath(new URL('..', import.meta.url))
const defaultDistRoot = join(desktopRoot, 'dist')

export function findWindowsSignatureTargets(distRoot = defaultDistRoot) {
  if (!existsSync(distRoot)) {
    throw new Error('desktop distribution directory is missing')
  }
  const installers = readdirSync(distRoot)
    .filter((name) => /^JiqingERP-.+-Setup\.exe$/i.test(name))
    .map((name) => join(distRoot, name))
  if (installers.length !== 1) {
    throw new Error('exactly one production installer is required')
  }
  const application = join(distRoot, 'win-unpacked', 'JiqingERP.exe')
  if (!existsSync(application)) {
    throw new Error('production application executable is missing')
  }
  return Object.freeze([installers[0], application])
}

export function verifyWindowsSignatures({
  distRoot = defaultDistRoot,
  powershell = 'powershell.exe',
} = {}) {
  if (process.platform !== 'win32') {
    throw new Error('Windows signature verification requires Windows')
  }
  const targets = findWindowsSignatureTargets(distRoot)
  const script = [
    "$ErrorActionPreference = 'Stop'",
    'foreach ($target in $args) {',
    '  $signature = Get-AuthenticodeSignature -LiteralPath $target',
    "  if ($signature.Status -ne 'Valid') {",
    '    throw "Invalid Authenticode signature for $target: $($signature.Status)"',
    '  }',
    '}',
  ].join('\n')
  const result = spawnSync(
    powershell,
    ['-NoProfile', '-NonInteractive', '-Command', script, ...targets],
    {
      stdio: 'inherit',
      windowsHide: true,
    },
  )
  if (result.error) throw result.error
  if (result.status !== 0) {
    throw new Error(
      `Windows signature verification failed with exit code ${result.status}`,
    )
  }
  return targets
}

if (
  process.argv[1]
  && import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const targets = verifyWindowsSignatures()
  process.stdout.write(
    `Verified ${targets.length} Windows Authenticode signatures\n`,
  )
}

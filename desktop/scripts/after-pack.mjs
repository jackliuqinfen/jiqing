import { join } from 'node:path'

import {
  flipFuses,
  FuseV1Options,
  FuseVersion,
} from '@electron/fuses'

export const HARDENED_FUSE_CONFIG = Object.freeze({
  version: FuseVersion.V1,
  strictlyRequireAllFuses: true,
  [FuseV1Options.RunAsNode]: false,
  [FuseV1Options.EnableCookieEncryption]: true,
  [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: false,
  [FuseV1Options.EnableNodeCliInspectArguments]: false,
  [FuseV1Options.EnableEmbeddedAsarIntegrityValidation]: true,
  [FuseV1Options.OnlyLoadAppFromAsar]: true,
  // Stock Electron ships the standard snapshot, not a browser-specific one.
  [FuseV1Options.LoadBrowserProcessSpecificV8Snapshot]: false,
  [FuseV1Options.GrantFileProtocolExtraPrivileges]: false,
  [FuseV1Options.WasmTrapHandlers]: true,
})

export function packagedExecutablePath(context) {
  const executableName = (
    context.packager.platformSpecificBuildOptions.executableName
    || context.packager.appInfo.productFilename
  )
  return join(context.appOutDir, `${executableName}.exe`)
}

export default async function afterPack(context) {
  if (context.electronPlatformName !== 'win32') return
  await flipFuses(packagedExecutablePath(context), HARDENED_FUSE_CONFIG)
}

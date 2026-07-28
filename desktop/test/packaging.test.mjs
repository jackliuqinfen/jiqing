import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import yaml from 'js-yaml'
import {
  FuseV1Options,
  FuseVersion,
} from '@electron/fuses'

import { HARDENED_FUSE_CONFIG } from '../scripts/after-pack.mjs'

test('Windows packaging is a branded per-user x64 NSIS installer', () => {
  const config = yaml.load(
    readFileSync(new URL('../electron-builder.yml', import.meta.url), 'utf8'),
  )

  assert.equal(config.appId, 'cn.jiqing.erp.desktop')
  assert.equal(config.productName, '集庆工程管理')
  assert.equal(config.asar, true)
  assert.deepEqual(config.files, ['src/**/*', 'ui/**/*', 'assets/**/*'])
  assert.equal(config.directories.output, 'dist')
  assert.equal(config.win.executableName, 'JiqingERP')
  assert.deepEqual(config.win.target, [{ target: 'nsis', arch: ['x64'] }])
  assert.equal(config.win.icon, 'assets/icon.ico')
  assert.equal(
    config.win.artifactName,
    'JiqingERP-${version}-${arch}-Setup.${ext}',
  )
  assert.equal(config.nsis.oneClick, false)
  assert.equal(config.nsis.perMachine, false)
  assert.equal(config.nsis.allowToChangeInstallationDirectory, true)
  assert.equal(config.nsis.createDesktopShortcut, true)
  assert.equal(config.nsis.createStartMenuShortcut, true)
  assert.equal(config.nsis.runAfterFinish, true)
  assert.equal(config.nsis.deleteAppDataOnUninstall, false)
  assert.equal(config.beforePack, 'scripts/before-pack.mjs')
  assert.equal(config.afterPack, 'scripts/after-pack.mjs')
})

test('NSIS packaging reuses the verified unpacked application', () => {
  const packageJson = JSON.parse(
    readFileSync(new URL('../package.json', import.meta.url), 'utf8'),
  )

  assert.match(packageJson.scripts['dist:win'], /npm run pack:dir/)
  assert.match(
    packageJson.scripts['dist:win'],
    /build-windows\.mjs nsis/,
  )
  assert.match(
    packageJson.scripts['pack:dir'],
    /build-windows\.mjs dir/,
  )
})

test('Windows build reuses the installed unpacked Electron runtime', () => {
  const buildScript = readFileSync(
    new URL('../scripts/build-windows.mjs', import.meta.url),
    'utf8',
  )

  assert.match(
    buildScript,
    /node_modules', 'electron', 'dist'/,
  )
  assert.match(
    buildScript,
    /--config\.electronDist=\$\{installedElectronDist\}/,
  )
  assert.match(
    buildScript,
    /assertDescendant\([\s\S]*installedElectronDist[\s\S]*desktopRoot/,
  )
  assert.match(buildScript, /mkdtempSync\(/)
  assert.match(buildScript, /temporaryRootPath = join\(desktopRoot, '\.tmp'\)/)
  assert.match(
    buildScript,
    /trustedBuildParentPath = join\(temporaryRoot, 'windows-build'\)/,
  )
  assert.match(
    buildScript,
    /assertDescendant\([\s\S]*trustedBuildParent[\s\S]*desktopRoot/,
  )
  assert.ok(
    buildScript.indexOf("'temporary build parent'")
      < buildScript.indexOf('mkdtempSync('),
    'the physical build-parent guard must run before creating a run directory',
  )
  assert.ok(
    buildScript.indexOf("'temporary directory'")
      < buildScript.indexOf('mkdirSync(trustedBuildParentPath'),
    'the physical temporary-root guard must run before creating the build parent',
  )
  assert.doesNotMatch(buildScript, /homedir\(/)
  assert.doesNotMatch(buildScript, /process\.env\.PUBLIC/)
})

test('desktop package exposes reproducible smoke and verification commands', () => {
  const packageJson = JSON.parse(
    readFileSync(new URL('../package.json', import.meta.url), 'utf8'),
  )

  assert.equal(packageJson.scripts.smoke, 'node scripts/smoke-runner.mjs')
  assert.equal(packageJson.scripts.verify, 'node scripts/verify-runner.mjs')
  assert.equal(packageJson.scripts.postinstall, 'install-electron')
  assert.match(
    packageJson.scripts['dist:production'],
    /build-windows\.mjs production/,
  )
})

test('packaging hardens every Electron V1 fuse', () => {
  assert.equal(HARDENED_FUSE_CONFIG.version, FuseVersion.V1)
  assert.equal(HARDENED_FUSE_CONFIG.strictlyRequireAllFuses, true)
  assert.equal(HARDENED_FUSE_CONFIG[FuseV1Options.RunAsNode], false)
  assert.equal(HARDENED_FUSE_CONFIG[FuseV1Options.EnableCookieEncryption], true)
  assert.equal(
    HARDENED_FUSE_CONFIG[
      FuseV1Options.EnableNodeOptionsEnvironmentVariable
    ],
    false,
  )
  assert.equal(
    HARDENED_FUSE_CONFIG[FuseV1Options.EnableNodeCliInspectArguments],
    false,
  )
  assert.equal(
    HARDENED_FUSE_CONFIG[
      FuseV1Options.EnableEmbeddedAsarIntegrityValidation
    ],
    true,
  )
  assert.equal(
    HARDENED_FUSE_CONFIG[FuseV1Options.OnlyLoadAppFromAsar],
    true,
  )
  assert.equal(
    HARDENED_FUSE_CONFIG[
      FuseV1Options.LoadBrowserProcessSpecificV8Snapshot
    ],
    true,
  )
  assert.equal(
    HARDENED_FUSE_CONFIG[
      FuseV1Options.GrantFileProtocolExtraPrivileges
    ],
    false,
  )
  assert.equal(
    HARDENED_FUSE_CONFIG[FuseV1Options.WasmTrapHandlers],
    true,
  )
})

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  FuseState,
  FuseV1Options,
  FuseVersion,
} from '@electron/fuses'

import {
  assertHardenedFuseWire,
  validatePackagedReleaseProfile,
} from '../scripts/verify-packaged-app.mjs'

function hardenedWire() {
  return {
    version: FuseVersion.V1,
    [FuseV1Options.RunAsNode]: FuseState.DISABLE,
    [FuseV1Options.EnableCookieEncryption]: FuseState.ENABLE,
    [FuseV1Options.EnableNodeOptionsEnvironmentVariable]: FuseState.DISABLE,
    [FuseV1Options.EnableNodeCliInspectArguments]: FuseState.DISABLE,
    [FuseV1Options.EnableEmbeddedAsarIntegrityValidation]: FuseState.ENABLE,
    [FuseV1Options.OnlyLoadAppFromAsar]: FuseState.ENABLE,
    [FuseV1Options.LoadBrowserProcessSpecificV8Snapshot]: FuseState.ENABLE,
    [FuseV1Options.GrantFileProtocolExtraPrivileges]: FuseState.DISABLE,
    [FuseV1Options.WasmTrapHandlers]: FuseState.ENABLE,
  }
}

test('packaged app verifier accepts only the complete hardened fuse wire', () => {
  assert.doesNotThrow(() => assertHardenedFuseWire(hardenedWire()))

  const weakened = {
    ...hardenedWire(),
    [FuseV1Options.RunAsNode]: FuseState.ENABLE,
  }
  assert.throws(() => assertHardenedFuseWire(weakened), /RunAsNode/)
})

test('packaged app verifier accepts an exact expected embedded profile', () => {
  const profile = {
    schemaVersion: 1,
    releaseChannel: 'internal-test',
    serverOrigin: 'http://121.4.36.112:8088',
  }
  assert.deepEqual(
    validatePackagedReleaseProfile(profile, {
      expectedChannel: 'internal-test',
      expectedOrigin: 'http://121.4.36.112:8088',
    }),
    profile,
  )

  assert.throws(
    () => validatePackagedReleaseProfile(profile, {
      expectedChannel: 'production',
      expectedOrigin: 'https://erp.example.cn',
    }),
    /release channel/,
  )
})

import test from 'node:test'
import assert from 'node:assert/strict'
import {
  mkdirSync,
  mkdtempSync,
  rmSync,
  writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import {
  validateReleaseConfiguration,
  validateWindowsBuildConfiguration,
} from '../scripts/validate-release-configuration.mjs'
import {
  findWindowsSignatureTargets,
  verifyWindowsSignatures,
} from '../scripts/verify-windows-signatures.mjs'

test('internal-test release accepts an explicit HTTP origin without signing', () => {
  assert.deepEqual(
    validateReleaseConfiguration({
      channel: 'internal-test',
      origin: 'http://121.4.36.112:8088',
    }),
    {
      channel: 'internal-test',
      origin: 'http://121.4.36.112:8088',
      requiresSigning: false,
    },
  )
})

test('production release rejects HTTP before packaging starts', () => {
  assert.throws(
    () => validateReleaseConfiguration({
      certificateBase64: 'certificate',
      certificatePassword: 'password',
      channel: 'production',
      origin: 'http://121.4.36.112:8088',
    }),
    /production release origin requires HTTPS/,
  )
})

test('production release requires both certificate secrets', () => {
  assert.throws(
    () => validateReleaseConfiguration({
      certificateBase64: '',
      certificatePassword: 'password',
      channel: 'production',
      origin: 'https://erp.example.cn',
    }),
    /WINDOWS_CERTIFICATE_BASE64/,
  )
  assert.throws(
    () => validateReleaseConfiguration({
      certificateBase64: 'certificate',
      certificatePassword: '',
      channel: 'production',
      origin: 'https://erp.example.cn',
    }),
    /WINDOWS_CERTIFICATE_PASSWORD/,
  )
})

test('production release accepts HTTPS only when both signing secrets exist', () => {
  assert.deepEqual(
    validateReleaseConfiguration({
      certificateBase64: 'certificate',
      certificatePassword: 'password',
      channel: 'production',
      origin: 'https://erp.example.cn/app',
    }),
    {
      channel: 'production',
      origin: 'https://erp.example.cn',
      requiresSigning: true,
    },
  )
})

test('ordinary Windows build modes reject a production release profile', () => {
  for (const mode of ['dir', 'nsis']) {
    assert.throws(
      () => validateWindowsBuildConfiguration({
        channel: 'production',
        mode,
        origin: 'https://erp.example.cn',
      }),
      /production release must use the production build mode/,
    )
  }
})

test('production Windows build mode requires production HTTPS and signing', () => {
  assert.throws(
    () => validateWindowsBuildConfiguration({
      channel: 'internal-test',
      mode: 'production',
      origin: 'http://erp.example.cn',
    }),
    /requires production release/,
  )
  assert.deepEqual(
    validateWindowsBuildConfiguration({
      certificateBase64: 'certificate',
      certificatePassword: 'password',
      channel: 'production',
      mode: 'production',
      origin: 'https://erp.example.cn',
    }),
    {
      channel: 'production',
      origin: 'https://erp.example.cn',
      requiresSigning: true,
    },
  )
})

test('production signature gate requires one installer and the packaged app', () => {
  const distRoot = mkdtempSync(join(tmpdir(), 'jiqing-signature-targets-'))
  try {
    mkdirSync(join(distRoot, 'win-unpacked'))
    const installer = join(distRoot, 'JiqingERP-1.0.0-x64-Setup.exe')
    const application = join(distRoot, 'win-unpacked', 'JiqingERP.exe')
    writeFileSync(installer, 'installer')
    writeFileSync(application, 'application')

    assert.deepEqual(
      findWindowsSignatureTargets(distRoot),
      [installer, application],
    )

    writeFileSync(
      join(distRoot, 'JiqingERP-1.0.1-x64-Setup.exe'),
      'unexpected installer',
    )
    assert.throws(
      () => findWindowsSignatureTargets(distRoot),
      /exactly one production installer/,
    )
  } finally {
    rmSync(distRoot, { force: true, recursive: true })
  }
})

test(
  'production signature gate executes PowerShell and rejects unsigned targets',
  { skip: process.platform !== 'win32' },
  () => {
    const distRoot = mkdtempSync(join(tmpdir(), 'jiqing-signature-check-'))
    try {
      mkdirSync(join(distRoot, 'win-unpacked'))
      writeFileSync(
        join(distRoot, 'JiqingERP-1.0.0-x64-Setup.exe'),
        'unsigned installer',
      )
      writeFileSync(
        join(distRoot, 'win-unpacked', 'JiqingERP.exe'),
        'unsigned application',
      )

      assert.throws(
        () => verifyWindowsSignatures({ distRoot }),
        /Windows signature verification failed/,
      )
    } finally {
      rmSync(distRoot, { force: true, recursive: true })
    }
  },
)

import test from 'node:test'
import assert from 'node:assert/strict'

import {
  validateReleaseConfiguration,
} from '../scripts/validate-release-configuration.mjs'

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

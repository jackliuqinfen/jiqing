import test from 'node:test'
import assert from 'node:assert/strict'
import { basename } from 'node:path'

import { resolveAppPage } from '../src/app-protocol.mjs'

const UI_ROOT = 'C:\\Program Files\\JiqingERP\\resources\\ui'

test('local protocol resolves only the three fixed fallback pages', () => {
  assert.equal(
    basename(resolveAppPage('app://connecting', UI_ROOT)),
    'connecting.html',
  )
  assert.equal(
    basename(resolveAppPage('app://unavailable', UI_ROOT)),
    'unavailable.html',
  )
  assert.equal(
    basename(resolveAppPage('app://incompatible', UI_ROOT)),
    'incompatible.html',
  )
})

test('local protocol rejects unknown pages and traversal forms', () => {
  for (const url of [
    'app://unknown',
    'app://connecting/../unavailable',
    'app://connecting/extra',
    'app://connecting?resource=../../secret',
    'app://connecting#unavailable',
    'app://user@connecting',
    'https://erp.example.cn',
    'file:///C:/Windows/System32/drivers/etc/hosts',
  ]) {
    assert.equal(resolveAppPage(url, UI_ROOT), null)
  }
})

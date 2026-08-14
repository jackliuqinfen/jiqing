import test from 'node:test'
import assert from 'node:assert/strict'
import {
  basename,
  dirname,
} from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  registerAppProtocol,
  resolveAppPage,
} from '../src/app-protocol.mjs'

const UI_ROOT = 'C:\\Program Files\\JiqingERP\\resources\\ui'
const REAL_UI_ROOT = dirname(
  fileURLToPath(new URL('../ui/connecting.html', import.meta.url)),
)
const REAL_ASSETS_ROOT = dirname(
  fileURLToPath(new URL('../assets/splash-logo.png', import.meta.url)),
)

test('local protocol resolves only the fixed startup and fallback pages', () => {
  assert.equal(
    basename(resolveAppPage('app://splash', UI_ROOT)),
    'splash.html',
  )
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

test('local protocol returns fixed startup HTML and logo without file URLs', async () => {
  let handler
  const protocol = {
    handle(scheme, value) {
      assert.equal(scheme, 'app')
      handler = value
    },
  }
  registerAppProtocol(protocol, null, REAL_UI_ROOT, REAL_ASSETS_ROOT)

  const response = await handler({ url: 'app://splash/' })
  assert.equal(response.status, 200)
  assert.equal(
    response.headers.get('Content-Type'),
    'text/html; charset=utf-8',
  )
  assert.match(await response.text(), /集庆工程管理/)

  const logoResponse = await handler({
    url: 'app://brand/splash-logo.png',
  })
  assert.equal(logoResponse.status, 200)
  assert.equal(logoResponse.headers.get('Content-Type'), 'image/png')
  assert.ok((await logoResponse.arrayBuffer()).byteLength > 1000)
})

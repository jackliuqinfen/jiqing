import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const main = readFileSync(
  new URL('../src/main.mjs', import.meta.url),
  'utf8',
)

test('main process registers the bounded desktop IPC controller', () => {
  assert.match(main, /registerDesktopIpcHandlers/)
  assert.match(main, /createDesktopIpcController/)
  assert.match(main, /new SyncEngine/)
  assert.match(main, /new DesktopApiClient/)
  assert.match(main, /fetchImpl:\s*net\.fetch/)
  assert.match(main, /app\.getPath\(['"]userData['"]\)/)
  assert.match(main, /app\.getVersion\(\)/)
  assert.match(main, /config\.releaseChannel/)
})

test('folder actions are wired through Electron dialog and shell without renderer paths', () => {
  assert.match(main, /dialog\.showOpenDialog/)
  assert.match(main, /shell\.openPath/)
})

test('desktop memory session is cleared when the application exits', () => {
  assert.match(main, /before-quit/)
  assert.match(main, /desktopIpcController\.clearSession\(\)/)
})

test('successful web logout request clears the desktop memory session', () => {
  assert.match(main, /\/api\/auth\/logout/)
  assert.match(main, /webRequest\.onBeforeRequest/)
  assert.match(main, /desktopIpcController\.clearSession\(\)/)
})

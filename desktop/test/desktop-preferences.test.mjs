import assert from 'node:assert/strict'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'

import {
  desktopPreferencesPath,
  readDesktopPreferences,
  writeDesktopPreferences,
} from '../src/desktop-preferences.mjs'

test('desktop preferences persist and restore the selected sync root', () => {
  const directory = mkdtempSync(join(tmpdir(), 'jiqing-desktop-preferences-'))
  try {
    const saved = writeDesktopPreferences(directory, {
      localRoot: 'C:\\Users\\tester\\Documents\\Jiqing',
    })
    assert.equal(saved.localRoot, 'C:\\Users\\tester\\Documents\\Jiqing')
    assert.deepEqual(readDesktopPreferences(directory), saved)
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
})

test('desktop preferences recover safely from invalid JSON', () => {
  const directory = mkdtempSync(join(tmpdir(), 'jiqing-desktop-preferences-'))
  try {
    writeFileSync(desktopPreferencesPath(directory), '{invalid', 'utf8')
    assert.deepEqual(readDesktopPreferences(directory), { localRoot: '' })
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
})

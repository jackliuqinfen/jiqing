import test from 'node:test'
import assert from 'node:assert/strict'
import {
  mkdtempSync,
  readFileSync,
  rmSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import yaml from 'js-yaml'

import {
  writePackagedUpdateConfig,
} from '../scripts/write-update-config.mjs'

test('writes the trusted generic update feed into packaged resources', () => {
  const appDirectory = mkdtempSync(join(tmpdir(), 'jiqing-update-config-'))
  try {
    const updateConfigPath = writePackagedUpdateConfig({
      appDirectory,
      updateFeedUrl:
        'https://erp.example.com/desktop-updates/internal-test/',
    })
    const config = yaml.load(readFileSync(updateConfigPath, 'utf8'))

    assert.deepEqual(config, {
      provider: 'generic',
      url: 'https://erp.example.com/desktop-updates/internal-test',
    })
  } finally {
    rmSync(appDirectory, { force: true, recursive: true })
  }
})

test('rejects non-HTTP update feeds', () => {
  const appDirectory = mkdtempSync(join(tmpdir(), 'jiqing-update-config-'))
  try {
    assert.throws(
      () => writePackagedUpdateConfig({
        appDirectory,
        updateFeedUrl: 'file:///tmp/desktop-updates',
      }),
      /must use HTTP or HTTPS/,
    )
  } finally {
    rmSync(appDirectory, { force: true, recursive: true })
  }
})

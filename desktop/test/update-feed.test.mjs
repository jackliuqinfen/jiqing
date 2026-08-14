import test from 'node:test'
import assert from 'node:assert/strict'
import {
  mkdtempSync,
  mkdirSync,
  readFileSync,
  writeFileSync,
} from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'

import { stageUpdateFeed } from '../scripts/stage-update-feed.mjs'

test('update feed stages only the installer, blockmap and metadata', () => {
  const root = mkdtempSync(join(tmpdir(), 'jiqing-update-feed-'))
  const source = join(root, 'desktop-dist')
  const webDist = join(root, 'web-dist')
  mkdirSync(source)
  mkdirSync(webDist)
  writeFileSync(join(source, 'latest.yml'), 'version: 1.0.3\n')
  writeFileSync(join(source, 'JiqingERP-1.0.3-x64-Setup.exe'), 'installer')
  writeFileSync(
    join(source, 'JiqingERP-1.0.3-x64-Setup.exe.blockmap'),
    'blockmap',
  )
  writeFileSync(join(source, 'builder-debug.yml'), 'private build details')

  const result = stageUpdateFeed({
    source,
    webDist,
    channel: 'internal-test',
  })

  assert.deepEqual(result.files, [
    'JiqingERP-1.0.3-x64-Setup.exe',
    'JiqingERP-1.0.3-x64-Setup.exe.blockmap',
    'latest.yml',
  ])
  assert.equal(
    readFileSync(join(result.target, 'latest.yml'), 'utf8'),
    'version: 1.0.3\n',
  )
})

test('update feed rejects unsupported channels and incomplete artifacts', () => {
  const root = mkdtempSync(join(tmpdir(), 'jiqing-update-feed-'))
  const source = join(root, 'desktop-dist')
  const webDist = join(root, 'web-dist')
  mkdirSync(source)
  mkdirSync(webDist)

  assert.throws(
    () => stageUpdateFeed({ source, webDist, channel: 'preview' }),
    /release channel/,
  )
  assert.throws(
    () => stageUpdateFeed({ source, webDist, channel: 'internal-test' }),
    /latest\.yml/,
  )
})

import test from 'node:test'
import assert from 'node:assert/strict'
import {
  mkdtempSync,
  rmSync,
  writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import {
  formatSmokeFailure,
  readSmokeDiagnostic,
} from '../scripts/smoke-diagnostics.mjs'

test('smoke failure includes a persisted runtime diagnostic before cleanup', () => {
  const root = mkdtempSync(join(tmpdir(), 'jiqing-smoke-diagnostic-'))
  try {
    const resultPath = join(root, 'result.json')
    writeFileSync(resultPath, JSON.stringify({
      runtimeError: 'technical remote load failed',
    }))

    assert.match(
      formatSmokeFailure({
        caseName: 'successful-load',
        completed: {
          stderr: 'electron stderr',
          stdout: 'electron stdout',
        },
        resultPath,
      }),
      /technical remote load failed/,
    )
  } finally {
    rmSync(root, { force: true, recursive: true })
  }
})

test('smoke diagnostic reports malformed result files without throwing', () => {
  const root = mkdtempSync(join(tmpdir(), 'jiqing-smoke-diagnostic-'))
  try {
    const resultPath = join(root, 'result.json')
    writeFileSync(resultPath, '{')
    assert.match(readSmokeDiagnostic(resultPath), /unreadable result/)
  } finally {
    rmSync(root, { force: true, recursive: true })
  }
})

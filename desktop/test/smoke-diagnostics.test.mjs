import test from 'node:test'
import assert from 'node:assert/strict'
import {
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

import {
  createSmokeFailure,
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

test('smoke assertion failures retain the cause and all runtime evidence', () => {
  const root = mkdtempSync(join(tmpdir(), 'jiqing-smoke-diagnostic-'))
  try {
    const resultPath = join(root, 'result.json')
    writeFileSync(resultPath, JSON.stringify({
      runtimeError: 'renderer contract failed',
    }))

    const error = createSmokeFailure({
      caseName: 'successful-load',
      cause: new Error('healthReady was false'),
      completed: {
        stderr: 'electron stderr tail',
        stdout: 'electron stdout tail',
      },
      resultPath,
    })

    assert.equal(error.smokeDiagnostic, true)
    assert.match(error.message, /healthReady was false/)
    assert.match(error.message, /electron stdout tail/)
    assert.match(error.message, /electron stderr tail/)
    assert.match(error.message, /renderer contract failed/)
  } finally {
    rmSync(root, { force: true, recursive: true })
  }
})

test('smoke runner waits for closed output pipes and wraps scenario assertions', () => {
  const runner = readFileSync(
    new URL('../scripts/smoke-runner.mjs', import.meta.url),
    'utf8',
  )
  const completionStart = runner.indexOf('const completed = new Promise')
  const completionEnd = runner.indexOf('\n  return {', completionStart)
  const completionBlock = runner.slice(completionStart, completionEnd)
  assert.match(completionBlock, /child\.once\('close'/)
  assert.doesNotMatch(completionBlock, /child\.once\('exit'/)
  assert.match(runner, /withProcessDiagnostics/)
})

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import yaml from 'js-yaml'

const workflow = yaml.load(
  readFileSync(
    new URL('../../.github/workflows/windows-desktop.yml', import.meta.url),
    'utf8',
  ),
)

function steps(jobName) {
  return workflow.jobs[jobName].steps
}

function step(jobName, name) {
  return steps(jobName).find((candidate) => candidate.name === name)
}

test('Windows verification and release jobs use hosted Windows runners', () => {
  assert.equal(workflow.jobs.verify['runs-on'], 'windows-latest')
  assert.equal(workflow.jobs['internal-test']['runs-on'], 'windows-latest')
  assert.equal(workflow.jobs.production['runs-on'], 'windows-latest')
})

test('internal-test installer embeds only DESKTOP_TEST_URL', () => {
  const build = step('internal-test', 'Build internal-test installer')
  assert.equal(build.env.DESKTOP_RELEASE_CHANNEL, 'internal-test')
  assert.equal(build.env.DESKTOP_SERVER_URL, '${{ vars.DESKTOP_TEST_URL }}')
  assert.match(build.run, /validate-release-configuration/)
  assert.match(build.run, /dist:win/)
})

test('production tag validates HTTPS and signing secrets before packaging', () => {
  const job = workflow.jobs.production
  assert.match(job.if, /refs\/tags\//)
  const gate = step('production', 'Validate production release gate')
  assert.equal(gate.env.DESKTOP_RELEASE_CHANNEL, 'production')
  assert.equal(gate.env.DESKTOP_SERVER_URL, '${{ vars.DESKTOP_PRODUCTION_URL }}')
  assert.equal(
    gate.env.WINDOWS_CERTIFICATE_BASE64,
    '${{ secrets.WINDOWS_CERTIFICATE_BASE64 }}',
  )
  assert.equal(
    gate.env.WINDOWS_CERTIFICATE_PASSWORD,
    '${{ secrets.WINDOWS_CERTIFICATE_PASSWORD }}',
  )
  assert.match(gate.run, /validate-release-configuration/)
})

test('production certificate exists only in runner temp and is always deleted', () => {
  const prepare = step('production', 'Prepare signing certificate')
  assert.match(prepare.run, /\$env:RUNNER_TEMP/)
  assert.doesNotMatch(prepare.run, /Write-(Host|Output)/)

  const cleanup = step('production', 'Delete signing certificate')
  assert.equal(cleanup.if, '${{ always() }}')
  assert.match(cleanup.run, /\$env:RUNNER_TEMP/)
  assert.match(cleanup.run, /Remove-Item/)
})

test('production artifact uploads only after a valid Windows signature', () => {
  const productionSteps = steps('production')
  const buildIndex = productionSteps.findIndex(
    ({ name }) => name === 'Build production installer',
  )
  const signatureIndex = productionSteps.findIndex(
    ({ name }) => name === 'Verify production signature',
  )
  const uploadIndex = productionSteps.findIndex(
    ({ name }) => name === 'Upload signed production installer',
  )
  assert.ok(buildIndex >= 0)
  assert.ok(signatureIndex > buildIndex)
  assert.ok(uploadIndex > signatureIndex)
  assert.match(productionSteps[buildIndex].run, /dist:production/)
  assert.doesNotMatch(productionSteps[buildIndex].run, /dist:win/)
  assert.match(
    productionSteps[signatureIndex].run,
    /verify-windows-signatures\.mjs/,
  )
})

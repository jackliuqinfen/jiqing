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
  assert.deepEqual(job.environment, { name: 'production' })
  const tagGate = step('production', 'Validate production tag')
  assert.match(tagGate.run, /desktop-v\\d\+\\\.\\d\+\\\.\\d\+/)

  const build = step(
    'production',
    'Build and verify signed production installer',
  )
  assert.equal(build.env.DESKTOP_RELEASE_CHANNEL, 'production')
  assert.equal(build.env.DESKTOP_SERVER_URL, '${{ vars.DESKTOP_PRODUCTION_URL }}')
  assert.equal(
    build.env.WINDOWS_CERTIFICATE_BASE64,
    '${{ secrets.WINDOWS_CERTIFICATE_BASE64 }}',
  )
  assert.equal(
    build.env.WINDOWS_CERTIFICATE_PASSWORD,
    '${{ secrets.WINDOWS_CERTIFICATE_PASSWORD }}',
  )
  assert.equal(
    build.env.WINDOWS_EXPECTED_SIGNER_SHA256,
    '${{ vars.WINDOWS_EXPECTED_SIGNER_SHA256 }}',
  )
  assert.match(build.run, /validate-release-configuration/)
})

test('production signing credentials exist only inside the guarded build step', () => {
  const build = step(
    'production',
    'Build and verify signed production installer',
  )
  assert.match(build.run, /\$env:RUNNER_TEMP/)
  assert.match(build.run, /try\s*\{/)
  assert.match(build.run, /finally\s*\{/)
  assert.match(build.run, /Remove-Item/)
  assert.match(build.run, /\$env:CSC_LINK\s*=\s*\$null/)
  assert.match(build.run, /\$env:CSC_KEY_PASSWORD\s*=\s*\$null/)
  assert.doesNotMatch(build.run, /GITHUB_ENV/)
  assert.equal(
    steps('production').filter(
      ({ env = {} }) => env.WINDOWS_CERTIFICATE_PASSWORD,
    ).length,
    1,
  )
})

test('production artifact uploads only after a valid Windows signature', () => {
  const productionSteps = steps('production')
  const buildIndex = productionSteps.findIndex(
    ({ name }) => name === 'Build and verify signed production installer',
  )
  const uploadIndex = productionSteps.findIndex(
    ({ name }) => name === 'Upload signed production installer',
  )
  assert.ok(buildIndex >= 0)
  assert.ok(uploadIndex > buildIndex)
  assert.match(productionSteps[buildIndex].run, /dist:production/)
  assert.doesNotMatch(productionSteps[buildIndex].run, /dist:win/)
  assert.match(
    productionSteps[buildIndex].run,
    /verify-windows-signatures\.mjs/,
  )
  assert.match(productionSteps[buildIndex].run, /verify:package/)
})

test('all third-party GitHub Actions are pinned to immutable commits', () => {
  const actions = Object.values(workflow.jobs)
    .flatMap(({ steps: jobSteps }) => jobSteps)
    .filter(({ uses }) => uses)

  assert.ok(actions.length > 0)
  for (const action of actions) {
    assert.match(
      action.uses,
      /^[^@]+@[0-9a-f]{40}$/i,
      `${action.name} must use a full commit SHA`,
    )
  }
})

test('workflow never exports signing secrets through GITHUB_ENV', () => {
  const serialized = JSON.stringify(workflow)
  assert.doesNotMatch(serialized, /GITHUB_ENV/)
})

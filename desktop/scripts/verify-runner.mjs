import { spawnSync } from 'node:child_process'

const npmCliPath = process.env.npm_execpath
if (!npmCliPath) {
  throw new Error('verify must be launched through npm run verify')
}

function runNpmScript(script, env = process.env) {
  const result = spawnSync(
    process.execPath,
    [npmCliPath, 'run', script],
    {
      env,
      stdio: 'inherit',
    },
  )
  if (result.error) throw result.error
  if (result.status !== 0) {
    throw new Error(`npm run ${script} failed with exit code ${result.status}`)
  }
}

const verificationBuildEnvironment = {
  ...process.env,
  DESKTOP_RELEASE_CHANNEL: 'internal-test',
  DESKTOP_SERVER_URL: 'http://127.0.0.1:9',
}

runNpmScript('test')
runNpmScript('icons')
runNpmScript('pack:dir', verificationBuildEnvironment)
runNpmScript('verify:package', verificationBuildEnvironment)
runNpmScript('smoke')

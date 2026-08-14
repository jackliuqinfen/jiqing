import { app } from 'electron'
import {
  mkdirSync,
  renameSync,
  writeFileSync,
} from 'node:fs'
import { dirname } from 'node:path'

function writeConfigurationFailure(error) {
  const resultPath = String(process.env.DESKTOP_SMOKE_RESULT || '')
  if (!resultPath) return
  mkdirSync(dirname(resultPath), { recursive: true })
  const temporaryPath = `${resultPath}.${process.pid}.tmp`
  writeFileSync(temporaryPath, `${JSON.stringify({
    configurationError: (
      error instanceof Error ? error.message : 'unknown configuration error'
    ),
  }, null, 2)}\n`, {
    encoding: 'utf8',
    mode: 0o600,
  })
  renameSync(temporaryPath, resultPath)
}

if (app.isPackaged) {
  writeConfigurationFailure(
    new Error('desktop smoke entry must remain unpackaged'),
  )
  app.exit(2)
} else {
  app.disableHardwareAcceleration()
  const userDataPath = String(process.env.DESKTOP_SMOKE_USER_DATA || '')
  if (!userDataPath) {
    writeConfigurationFailure(new Error('desktop smoke user-data path missing'))
    app.exit(2)
  } else {
    app.setPath('userData', userDataPath)
    process.env.DESKTOP_UNPACKAGED_SMOKE = '1'
    try {
      await import('../src/main.mjs')
    } catch (error) {
      writeConfigurationFailure(error)
      app.exit(2)
    }
  }
}

import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'

import yaml from 'js-yaml'

export function writePackagedUpdateConfig({
  appDirectory,
  updateFeedUrl,
}) {
  const parsedUrl = new URL(updateFeedUrl)
  if (!['http:', 'https:'].includes(parsedUrl.protocol)) {
    throw new Error('desktop update feed must use HTTP or HTTPS')
  }

  const updateConfigPath = join(
    appDirectory,
    'resources',
    'app-update.yml',
  )
  mkdirSync(dirname(updateConfigPath), { recursive: true })
  writeFileSync(
    updateConfigPath,
    yaml.dump({
      provider: 'generic',
      url: parsedUrl.href.replace(/\/$/, ''),
    }, {
      lineWidth: -1,
      noRefs: true,
    }),
    'utf8',
  )
  return updateConfigPath
}

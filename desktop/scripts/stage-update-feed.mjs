import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readdirSync,
  realpathSync,
  rmSync,
  statSync,
} from 'node:fs'
import {
  isAbsolute,
  join,
  relative,
  resolve,
} from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const RELEASE_CHANNELS = new Set(['internal-test', 'production'])

function assertDirectory(path, label) {
  if (!existsSync(path) || !statSync(path).isDirectory()) {
    throw new Error(`${label} directory is missing`)
  }
  return realpathSync(path)
}

function assertDescendant(path, parent, label) {
  const relativePath = relative(parent, resolve(path))
  if (
    relativePath.length === 0
    || relativePath.startsWith('..')
    || isAbsolute(relativePath)
  ) {
    throw new Error(`${label} escapes its trusted parent directory`)
  }
}

export function stageUpdateFeed({ source, webDist, channel }) {
  if (!RELEASE_CHANNELS.has(channel)) {
    throw new Error('unsupported release channel')
  }
  const sourceRoot = assertDirectory(source, 'desktop distribution')
  const webRoot = assertDirectory(webDist, 'web distribution')
  const names = readdirSync(sourceRoot)
  const installers = names.filter((name) => (
    /^JiqingERP-\d+\.\d+\.\d+-x64-Setup\.exe$/.test(name)
  ))
  if (!names.includes('latest.yml')) {
    throw new Error('latest.yml is missing from desktop distribution')
  }
  if (installers.length !== 1) {
    throw new Error('desktop distribution must contain exactly one installer')
  }
  const blockmap = `${installers[0]}.blockmap`
  if (!names.includes(blockmap)) {
    throw new Error('installer blockmap is missing from desktop distribution')
  }

  const target = join(webRoot, 'desktop-updates', channel)
  assertDescendant(target, webRoot, 'update feed')
  rmSync(target, { force: true, recursive: true })
  mkdirSync(target, { recursive: true })
  const files = [installers[0], blockmap, 'latest.yml'].sort()
  for (const name of files) {
    copyFileSync(join(sourceRoot, name), join(target, name))
  }
  return Object.freeze({ target, files: Object.freeze(files) })
}

if (
  process.argv[1]
  && import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const desktopRoot = fileURLToPath(new URL('..', import.meta.url))
  const channel = process.argv[2] || process.env.DESKTOP_RELEASE_CHANNEL
  const result = stageUpdateFeed({
    source: join(desktopRoot, 'dist'),
    webDist: join(desktopRoot, '..', 'dist'),
    channel,
  })
  process.stdout.write(`${JSON.stringify(result, null, 2)}\n`)
}

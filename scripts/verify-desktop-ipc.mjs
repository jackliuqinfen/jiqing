import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'

const main = readFileSync('desktop/src/main.mjs', 'utf8')
const preloadMatch = main.match(/preload:\s*join\(moduleRoot,\s*'([^']+)'\)/)
if (!preloadMatch) throw new Error('Main process preload configuration is missing')
const preloadName = preloadMatch[1]
if (!preloadName.endsWith('.cjs')) {
  throw new Error(`Sandbox preload must be CommonJS, received ${preloadName}`)
}
const preload = readFileSync(`desktop/src/${preloadName}`, 'utf8')
if (/(?:^|\n)\s*(?:import|export)\s/m.test(preload)) {
  throw new Error('Sandbox preload cannot contain ESM imports or exports')
}

const requestChannels = [
  'desktop:get-capabilities',
  'desktop:select-sync-folder',
  'desktop:get-sync-state',
  'desktop:start-sync',
  'desktop:pause-sync',
  'desktop:open-sync-folder',
]
const stateChannel = 'desktop:sync-state'

for (const channel of requestChannels) {
  if (!preload.includes(channel)) {
    throw new Error(`Missing IPC channel ${channel}`)
  }
}
if (!preload.includes(stateChannel)) {
  throw new Error(`Missing IPC state channel ${stateChannel}`)
}

const declaration = readFileSync('src/types/desktop.d.ts', 'utf8')
if (!declaration.includes('jiqingDesktop?: JiqingDesktopBridge')) {
  throw new Error('Optional Window bridge declaration is missing')
}
if (!declaration.includes('protocolVersion: 1')) {
  throw new Error('Desktop bridge protocol version is missing')
}

const forbiddenPreloadSymbols = [
  'exposeInMainWorld(\'ipcRenderer\'',
  'exposeInMainWorld("ipcRenderer"',
  'exposeInMainWorld(\'fs\'',
  'exposeInMainWorld("fs"',
  'exposeInMainWorld(\'shell\'',
  'exposeInMainWorld("shell"',
  'genericSend',
]
for (const symbol of forbiddenPreloadSymbols) {
  if (preload.includes(symbol)) {
    throw new Error(`Forbidden preload exposure ${symbol}`)
  }
}

const discoveredChannels = new Set(
  preload.match(/desktop:[a-z-]+/g) || [],
)
const allowedChannels = new Set([...requestChannels, stateChannel])
for (const channel of discoveredChannels) {
  if (!allowedChannels.has(channel)) {
    throw new Error(`Unexpected IPC channel ${channel}`)
  }
}

let exposedName
let exposedBridge
const electron = {
  contextBridge: {
    exposeInMainWorld(name, bridge) {
      exposedName = name
      exposedBridge = bridge
    },
  },
  ipcRenderer: {
    invoke() {
      return Promise.resolve()
    },
    on() {},
    removeListener() {},
  },
}
runInNewContext(preload, {
  navigator: {
    userActivation: {
      isActive: true,
    },
  },
  require(specifier) {
    if (specifier !== 'electron') {
      throw new Error(`Sandbox preload requires forbidden module ${specifier}`)
    }
    return electron
  },
}, { filename: preloadName })

if (exposedName !== 'jiqingDesktop') {
  throw new Error('Sandbox preload did not expose jiqingDesktop')
}
const exposedKeys = Object.keys(exposedBridge || {}).sort()
const expectedKeys = [
  'getCapabilities',
  'getSyncState',
  'onSyncState',
  'openSyncFolder',
  'pauseSync',
  'selectSyncFolder',
  'startSync',
]
if (
  exposedKeys.length !== expectedKeys.length
  || !exposedKeys.every((key, index) => key === expectedKeys[index])
) {
  throw new Error(`Unexpected desktop bridge surface: ${exposedKeys.join(', ')}`)
}

console.log('Desktop IPC contract verified')

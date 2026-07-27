import { readFileSync } from 'node:fs'

const preload = readFileSync('desktop/src/preload.mjs', 'utf8')

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

console.log('Desktop IPC contract verified')

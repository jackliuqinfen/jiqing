import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const css = await readFile(new URL('../src/styles/arco-premium-workbench.css', import.meta.url), 'utf8')
const layout = await readFile(new URL('../src/views/AppLayout.vue', import.meta.url), 'utf8')

const requiredTokens = [
  '--workspace-bg-top',
  '--workspace-bg-mid',
  '--workspace-bg-bottom',
  '--workspace-grid',
  '--premium-shadow-ambient',
  '--premium-shadow-card',
  '--premium-shadow-float',
]

for (const token of requiredTokens) {
  assert.match(css, new RegExp(token), `missing visual token: ${token}`)
}

assert.match(css, /\.system-shell::before/)
assert.match(css, /\.platform-topbar[\s\S]*backdrop-filter/)
assert.match(css, /\.arco-table[\s\S]*background:\s*#fff/)
assert.match(css, /\.arco-modal[\s\S]*background:\s*#fff/)
assert.match(layout, /aria-label="平台级模块"/)
assert.match(layout, /aria-label="当前模块业务功能"/)

console.log('premium theme contract: PASS')

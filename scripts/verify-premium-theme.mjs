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

const premiumTopbarRule = css.match(/\.platform-topbar\s*\{[^}]*\}/)?.[0] || ''
const layoutTopbarRule = layout.match(/\.platform-topbar\s*\{[^}]*\}/)?.[0] || ''

assert.match(premiumTopbarRule, /(?<!-)backdrop-filter:\s*blur\(14px\) saturate\(128%\) !important;/)
assert.match(premiumTopbarRule, /-webkit-backdrop-filter:\s*blur\(14px\) saturate\(128%\) !important;/)
assert.match(layoutTopbarRule, /(?<!-)backdrop-filter:\s*blur\(14px\) saturate\(128%\);/)
assert.match(layoutTopbarRule, /-webkit-backdrop-filter:\s*blur\(14px\) saturate\(128%\);/)

assert.match(layout, /:aria-current="isTopNavActive\(item\.path\) \? 'page' : undefined"/)
assert.match(layout, /:aria-current="isSideNavActive\(item\) \? 'page' : undefined"/)

const compactMediaStart = layout.indexOf('@media (max-width: 900px)')
const mobileMediaStart = layout.indexOf('@media (max-width: 640px)', compactMediaStart)
assert.notEqual(compactMediaStart, -1, 'missing 900px compact layout media query')
assert.notEqual(mobileMediaStart, -1, 'missing 640px mobile layout media query')
const compactLayout = layout.slice(compactMediaStart, mobileMediaStart)

assert.doesNotMatch(compactLayout, /\.topbar-user\s+span\s*\{[^}]*display\s*:\s*none;?[^}]*\}/)
assert.match(compactLayout, /\.topbar-user__copy\s*\{[^}]*display\s*:\s*none;?[^}]*\}/)

console.log('premium theme contract: PASS')

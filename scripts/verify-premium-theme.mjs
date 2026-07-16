import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const css = await readFile(new URL('../src/styles/arco-premium-workbench.css', import.meta.url), 'utf8')
const layout = await readFile(new URL('../src/views/AppLayout.vue', import.meta.url), 'utf8')
const cssWithoutComments = css.replace(/\/\*[\s\S]*?\*\//g, '')
const cssRules = [...cssWithoutComments.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((match) => ({
  selectors: match[1].split(',').map((selector) => selector.replace(/\s+/g, ' ').trim()),
  body: match[2],
}))

const ruleBodiesFor = (selector) => cssRules
  .filter((rule) => rule.selectors.includes(selector))
  .map((rule) => rule.body)

const assertRule = (selector, declaration, message) => {
  assert.ok(ruleBodiesFor(selector).some((body) => declaration.test(body)), message)
}

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
assert.match(layout, /class="sidebar-module-heading"/)
assert.match(layout, /class="sidebar-collapse-toggle"/)
assert.doesNotMatch(layout, /class="system-brand"/)
assert.doesNotMatch(layout, /class="sidebar-collapse-actions"/)
assert.doesNotMatch(layout, /class="sidebar-action"/)
assert.doesNotMatch(layout, /class="system-status"/)

assertRule(
  '.system-sidebar',
  /background:\s*linear-gradient\(180deg,\s*rgba\(235,\s*244,\s*255,\s*0\.94\)\s*0%,\s*rgba\(248,\s*251,\s*255,\s*0\.98\)\s*52%,\s*#fff\s*100%\)\s*!important;/,
  'sidebar must use the approved quiet blue-to-white background',
)
assertRule('.system-sidebar', /border-right:\s*0\s*!important;/, 'sidebar must not render a boxed divider')
assertRule('.module-link--active', /background:\s*#fff\s*!important;/, 'active secondary navigation must use a white surface')
assertRule('.module-link--active', /border-color:\s*transparent\s*!important;/, 'active secondary navigation must remain borderless')
assertRule('.module-link--active', /box-shadow:\s*none\s*!important;/, 'active secondary navigation must remain flat')
assertRule('.sidebar-collapse-toggle', /background:\s*rgba\(255,\s*255,\s*255,\s*0\.9\)\s*!important;/, 'collapse control must use the quiet floating treatment')

assertRule(
  '.audit-main .toolbar',
  /background:\s*rgba\(255,\s*255,\s*255,\s*0\.68\)\s*!important;/,
  'audit toolbar must use the L2 translucent material',
)
assert.equal(ruleBodiesFor('.audit-main .filter-panel').length, 0, 'obsolete audit filter selector must not return')

assertRule(
  '.summary-card.summary-card--active',
  /background:\s*var\(--summary-bg,\s*color-mix\(in srgb,\s*var\(--premium-blue\)\s*8%,\s*#fff\)\)\s*!important;/,
  'active summary background must preserve component tones with a brand fallback',
)
assertRule(
  '.summary-card.summary-card--active',
  /border-color:\s*color-mix\(in srgb,\s*var\(--summary-color,\s*var\(--premium-blue\)\)\s*46%,\s*var\(--premium-line\)\)\s*!important;/,
  'active summary border must preserve component tones with a brand fallback',
)
assertRule(
  '.summary-card.summary-card--active',
  /box-shadow:\s*var\(--premium-shadow-card\)\s*!important;/,
  'active summary shadow must stay stable',
)
assertRule(
  '.summary-card.summary-card--active',
  /transform:\s*none\s*!important;/,
  'active summary cards must not move',
)
assert.ok(
  css.lastIndexOf('.summary-card.summary-card--active') > css.lastIndexOf('.summary-card:hover'),
  'active summary override must follow the shared hover rule',
)

assertRule('.arco-table', /border:\s*1px solid var\(--premium-line\)\s*!important;/, 'table must own its outer border')
assertRule('.arco-table', /box-shadow:\s*var\(--premium-shadow-ambient\)\s*!important;/, 'table must own its outer shadow')
assertRule('.arco-table', /background:\s*#fff\s*!important;/, 'table must remain opaque')
assertRule('.arco-table', /backdrop-filter:\s*none\s*!important;/, 'table must not use backdrop blur')
assertRule('.arco-modal', /background:\s*#fff\s*!important;/, 'modal must remain opaque')
assertRule('.arco-modal', /backdrop-filter:\s*none\s*!important;/, 'modal must not use backdrop blur')
assertRule('.arco-table-container', /border:\s*0\s*!important;/, 'table container must not add an outer border')
assertRule('.arco-table-container', /border-radius:\s*inherit\s*!important;/, 'table container must inherit table radius')
assertRule('.arco-table-container', /box-shadow:\s*none\s*!important;/, 'table container must not add an outer shadow')
assert.ok(
  ruleBodiesFor('.arco-table-container').every((body) => !/border:\s*1px/.test(body)),
  'table container must never receive the L3 outer border',
)

assertRule(
  '.project-management .project-table-group',
  /border:\s*1px solid var\(--premium-line\)\s*!important;/,
  'project table group must own the grouped-table border',
)
for (const selector of [
  '.project-management .project-table-group .arco-table',
  '.project-management .project-table-group .arco-table-container',
]) {
  assertRule(selector, /border:\s*0\s*!important;/, `${selector} must not add a nested border`)
  assertRule(selector, /box-shadow:\s*none\s*!important;/, `${selector} must not add a nested shadow`)
}

const premiumTopbarRule = css.match(/\.platform-topbar\s*\{[^}]*\}/)?.[0] || ''
const layoutTopbarRule = layout.match(/\.platform-topbar\s*\{[^}]*\}/)?.[0] || ''

assert.match(premiumTopbarRule, /(?<!-)backdrop-filter:\s*blur\(14px\) saturate\(128%\) !important;/)
assert.match(premiumTopbarRule, /-webkit-backdrop-filter:\s*blur\(14px\) saturate\(128%\) !important;/)
assert.match(layoutTopbarRule, /(?<!-)backdrop-filter:\s*blur\(14px\) saturate\(128%\);/)
assert.match(layoutTopbarRule, /-webkit-backdrop-filter:\s*blur\(14px\) saturate\(128%\);/)

assert.match(layout, /:aria-current="isTopNavActive\(item\.path\) \? 'page' : undefined"/)
assert.match(layout, /:aria-current="isSideNavActive\(item\) \? 'page' : undefined"/)

for (const selector of [
  '.summary-card:focus-visible',
  '.kpi-card:focus-visible',
  '.metric-card:focus-visible',
  '.project-card:focus-visible',
]) {
  assertRule(selector, /box-shadow:\s*0 0 0 3px rgba\(22,\s*93,\s*255,\s*0\.16\),\s*var\(--premium-shadow-card\)\s*!important;/, `${selector} must retain a visible keyboard focus ring`)
  assertRule(selector, /transform:\s*none\s*!important;/, `${selector} must stay stationary while focused`)
}
assert.ok(
  css.lastIndexOf('.summary-card:focus-visible') > css.lastIndexOf('.summary-card.summary-card--active'),
  'summary focus override must follow the active-state rule so active cards retain the focus ring',
)

assertRule('.sidebar-resizer::after', /background:\s*transparent\s*!important;/, 'sidebar resizer must be transparent at rest')
assertRule('.sidebar-resizer::after', /opacity:\s*0\s*!important;/, 'sidebar resizer must be invisible at rest')

const compactMediaStart = layout.indexOf('@media (max-width: 900px)')
const mobileMediaStart = layout.indexOf('@media (max-width: 640px)', compactMediaStart)
assert.notEqual(compactMediaStart, -1, 'missing 900px compact layout media query')
assert.notEqual(mobileMediaStart, -1, 'missing 640px mobile layout media query')
const compactLayout = layout.slice(compactMediaStart, mobileMediaStart)

assert.doesNotMatch(compactLayout, /\.topbar-user\s+span\s*\{[^}]*display\s*:\s*none;?[^}]*\}/)
assert.match(compactLayout, /\.topbar-user__copy\s*\{[^}]*display\s*:\s*none;?[^}]*\}/)

console.log('premium theme contract: PASS')

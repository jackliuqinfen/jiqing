import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import sharp from 'sharp'

test('icon build emits a valid Windows ICO from the enterprise artwork', () => {
  const iconUrl = new URL('../assets/icon.ico', import.meta.url)
  assert.equal(existsSync(iconUrl), true)

  const icon = readFileSync(iconUrl)
  assert.deepEqual([...icon.subarray(0, 4)], [0, 0, 1, 0])
  assert.ok(icon.length > 1024)
})

test('icon build emits the required square PNG sizes and splash artwork', async () => {
  for (const size of [16, 24, 32, 48, 64, 128, 256]) {
    const pngUrl = new URL(
      `../assets/generated/icon-${size}.png`,
      import.meta.url,
    )
    assert.equal(existsSync(pngUrl), true, `missing ${size}px PNG`)
    assert.deepEqual(
      [...readFileSync(pngUrl).subarray(0, 8)],
      [137, 80, 78, 71, 13, 10, 26, 10],
    )
    const metadata = await sharp(fileURLToPath(pngUrl)).metadata()
    assert.equal(metadata.width, size)
    assert.equal(metadata.height, size)
  }

  const splashUrl = new URL('../assets/splash-logo.png', import.meta.url)
  assert.equal(existsSync(splashUrl), true)
  const splash = await sharp(fileURLToPath(splashUrl)).metadata()
  assert.equal(splash.width, 512)
  assert.equal(splash.height, 512)
})

test('icon output is non-empty and records the exact enterprise SVG source', async () => {
  const sourceUrl = new URL(
    '../../public/aoqiang-construction-logo.svg',
    import.meta.url,
  )
  const manifestUrl = new URL('../assets/icon-manifest.json', import.meta.url)
  assert.equal(existsSync(manifestUrl), true)

  const sourceSha256 = createHash('sha256')
    .update(readFileSync(sourceUrl))
    .digest('hex')
  const manifest = JSON.parse(readFileSync(manifestUrl, 'utf8'))
  assert.equal(manifest.schemaVersion, 1)
  assert.equal(manifest.source, 'public/aoqiang-construction-logo.svg')
  assert.equal(manifest.sourceSha256, sourceSha256)

  const { data, info } = await sharp(
    fileURLToPath(new URL('../assets/generated/icon-256.png', import.meta.url)),
  )
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true })
  let visiblePixels = 0
  for (let offset = 3; offset < data.length; offset += info.channels) {
    if (data[offset] > 0) visiblePixels += 1
  }
  assert.ok(visiblePixels > 1000, 'generated icon must contain visible artwork')
})

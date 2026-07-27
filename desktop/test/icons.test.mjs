import test from 'node:test'
import assert from 'node:assert/strict'
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

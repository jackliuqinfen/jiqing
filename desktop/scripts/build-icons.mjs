import { createHash } from 'node:crypto'
import {
  mkdirSync,
  readFileSync,
  writeFileSync,
} from 'node:fs'
import { join } from 'node:path'
import {
  fileURLToPath,
  pathToFileURL,
} from 'node:url'

import pngToIco from 'png-to-ico'
import sharp from 'sharp'

const desktopRoot = fileURLToPath(new URL('..', import.meta.url))
const sourcePath = fileURLToPath(
  new URL('../assets/app-icon-source.png', import.meta.url),
)
const assetsPath = join(desktopRoot, 'assets')
const generatedPath = join(assetsPath, 'generated')
const iconSizes = Object.freeze([16, 24, 32, 48, 64, 128, 256])

async function squareLogo(source, size) {
  const inset = Math.max(1, Math.round(size * 0.08))
  const artworkSize = size - (inset * 2)
  const artwork = await sharp(source)
    .resize({
      width: artworkSize,
      height: artworkSize,
      fit: 'inside',
      withoutEnlargement: false,
    })
    .png()
    .toBuffer()

  return sharp({
    create: {
      width: size,
      height: size,
      channels: 4,
      background: { r: 0, g: 0, b: 0, alpha: 0 },
    },
  })
    .composite([{ input: artwork, gravity: 'center' }])
    .png()
    .toBuffer()
}

export async function buildIcons() {
  mkdirSync(generatedPath, { recursive: true })
  const sourceArtwork = readFileSync(sourcePath)
  const trimmedLogo = await sharp(sourceArtwork)
    .trim()
    .png()
    .toBuffer()

  const pngPaths = []
  for (const size of iconSizes) {
    const outputPath = join(generatedPath, `icon-${size}.png`)
    writeFileSync(outputPath, await squareLogo(trimmedLogo, size))
    pngPaths.push(outputPath)
  }

  writeFileSync(
    join(assetsPath, 'splash-logo.png'),
    await squareLogo(trimmedLogo, 512),
  )
  writeFileSync(join(assetsPath, 'icon.ico'), await pngToIco(pngPaths))
  const manifestPath = join(assetsPath, 'icon-manifest.json')
  writeFileSync(
    manifestPath,
    `${JSON.stringify({
      schemaVersion: 1,
      source: 'desktop/assets/app-icon-source.png',
      sourceSha256: createHash('sha256').update(sourceArtwork).digest('hex'),
    }, null, 2)}\n`,
    'utf8',
  )

  return Object.freeze({
    iconPath: join(assetsPath, 'icon.ico'),
    manifestPath,
    pngPaths: Object.freeze(pngPaths),
    splashPath: join(assetsPath, 'splash-logo.png'),
  })
}

if (
  process.argv[1]
  && import.meta.url === pathToFileURL(process.argv[1]).href
) {
  const result = await buildIcons()
  process.stdout.write(`Generated desktop icon: ${result.iconPath}\n`)
}

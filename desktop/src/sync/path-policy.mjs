import { extname, isAbsolute, posix, relative, resolve } from 'node:path'

const UNSAFE_WINDOWS_CHARACTERS = /[<>:"/\\|?*\u0000-\u001f]/g
const WINDOWS_RESERVED_NAME = /^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$/i
const MAX_SEGMENT_CODE_POINTS = 80
const MAX_RELATIVE_PATH_CODE_POINTS = 220

function codePoints(value) {
  return [...value]
}

function truncate(value, maximumLength) {
  return codePoints(value).slice(0, maximumLength).join('')
}

function truncatePreservingExtension(value, maximumLength) {
  if (codePoints(value).length <= maximumLength) return value
  const extension = extname(value)
  const extensionLength = codePoints(extension).length
  if (!extension || extensionLength >= maximumLength) {
    return truncate(value, maximumLength)
  }
  const stem = value.slice(0, -extension.length)
  return `${truncate(stem, maximumLength - extensionLength)}${extension}`
}

export function safeSegment(
  value,
  {
    maximumLength = MAX_SEGMENT_CODE_POINTS,
    preserveExtension = false,
  } = {},
) {
  if (!Number.isInteger(maximumLength) || maximumLength < 1) {
    throw new Error('invalid segment length')
  }

  let normalized = String(value || '')
    .normalize('NFC')
    .replace(UNSAFE_WINDOWS_CHARACTERS, '_')
    .replace(/^[ .]+/, '_')
    .replace(/[ .]+$/g, '')
    .replace(/_+/g, '_')
  if (!normalized) normalized = '_'

  const extension = extname(normalized)
  const stem = extension ? normalized.slice(0, -extension.length) : normalized
  if (WINDOWS_RESERVED_NAME.test(stem.replace(/[ .]+$/g, ''))) {
    normalized = `_${normalized}`
  }

  return preserveExtension
    ? truncatePreservingExtension(normalized, maximumLength)
    : truncate(normalized, maximumLength)
}

function shrinkSegment(segment, reduction, preserveExtension = false) {
  const currentLength = codePoints(segment).length
  const nextLength = Math.max(1, currentLength - reduction)
  return safeSegment(segment, {
    maximumLength: nextLength,
    preserveExtension,
  })
}

export function buildRelativePath({
  projectCode,
  projectName,
  categoryName,
  originalName,
}) {
  const project = safeSegment(`${projectCode || ''}_${projectName || ''}`)
  const category = safeSegment(categoryName)
  const filename = safeSegment(originalName, { preserveExtension: true })
  const segments = [project, category, filename]
  let excess = codePoints(segments.join('/')).length - MAX_RELATIVE_PATH_CODE_POINTS

  for (const index of [0, 1, 2]) {
    if (excess <= 0) break
    const length = codePoints(segments[index]).length
    const reduction = Math.min(excess, length - 1)
    segments[index] = shrinkSegment(segments[index], reduction, index === 2)
    excess -= reduction
  }

  return segments.join('/')
}

export function appendFilenameSuffix(relativePath, suffix) {
  const directory = posix.dirname(relativePath)
  const extension = posix.extname(relativePath)
  const stem = posix.basename(relativePath, extension)
  const safeSuffix = safeSegment(suffix, { maximumLength: 32 })
  const suffixLength = codePoints(safeSuffix).length
  const maximumExtensionLength = Math.max(
    0,
    MAX_SEGMENT_CODE_POINTS - suffixLength - 1,
  )
  const boundedExtension = truncate(extension, maximumExtensionLength)
  const maximumStemLength = Math.max(
    1,
    MAX_SEGMENT_CODE_POINTS
      - suffixLength
      - codePoints(boundedExtension).length,
  )
  const filename = (
    `${truncate(stem, maximumStemLength)}${safeSuffix}${boundedExtension}`
  )
  return directory === '.' ? filename : `${directory}/${filename}`
}

export function resolveWithinRoot(root, relativePath) {
  if (typeof root !== 'string' || root.trim().length === 0) {
    throw new Error('invalid sync root')
  }
  if (typeof relativePath !== 'string' || isAbsolute(relativePath)) {
    throw new Error('path is outside sync root')
  }

  const resolvedRoot = resolve(root)
  const destination = resolve(resolvedRoot, relativePath)
  const fromRoot = relative(resolvedRoot, destination)
  if (
    fromRoot === '..'
    || fromRoot.startsWith(`..\\`)
    || fromRoot.startsWith('../')
    || isAbsolute(fromRoot)
  ) {
    throw new Error('path is outside sync root')
  }
  return destination
}

export const PATH_POLICY_LIMITS = Object.freeze({
  segmentCodePoints: MAX_SEGMENT_CODE_POINTS,
  relativePathCodePoints: MAX_RELATIVE_PATH_CODE_POINTS,
})

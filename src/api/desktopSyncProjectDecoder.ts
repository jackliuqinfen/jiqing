const PROJECT_KEYS = Object.freeze([
  'auditProjectId',
  'canonicalProjectId',
  'fileCount',
  'projectCode',
  'projectName',
  'projectRef',
  'totalFileSizeBytes',
])
const PROJECT_REF_PATTERN = /^(project|audit):[A-Za-z0-9-]+$/
const MAX_PROJECT_COUNT = 500
const MAX_IDENTIFIER_LENGTH = 256
const MAX_PROJECT_NAME_LENGTH = 512

export interface DesktopSyncProject {
  projectRef: string
  canonicalProjectId: string | null
  auditProjectId: string | null
  projectCode: string
  projectName: string
  fileCount: number
  totalFileSizeBytes: number
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const prototype = Object.getPrototypeOf(value)
  return prototype === Object.prototype || prototype === null
}

function hasExactKeys(value: Record<string, unknown>): boolean {
  const keys = Object.keys(value).sort()
  return (
    keys.length === PROJECT_KEYS.length
    && keys.every((key, index) => key === PROJECT_KEYS[index])
  )
}

function isBoundedNonBlankString(value: unknown, maximumLength: number): value is string {
  return (
    typeof value === 'string'
    && value.length <= maximumLength
    && value.trim().length > 0
  )
}

function isBoundedString(value: unknown, maximumLength: number): value is string {
  return typeof value === 'string' && value.length <= maximumLength
}

function isNullableIdentifier(value: unknown): value is string | null {
  return value === null || isBoundedNonBlankString(value, MAX_IDENTIFIER_LENGTH)
}

function isSafeNonnegativeInteger(value: unknown): value is number {
  return Number.isSafeInteger(value) && (value as number) >= 0
}

function decodeProject(value: unknown): DesktopSyncProject {
  if (!isPlainObject(value) || !hasExactKeys(value)) {
    throw new Error('invalid desktop sync project')
  }
  if (
    !isBoundedNonBlankString(value.projectRef, MAX_IDENTIFIER_LENGTH)
    || !PROJECT_REF_PATTERN.test(value.projectRef)
    || !isNullableIdentifier(value.canonicalProjectId)
    || !isNullableIdentifier(value.auditProjectId)
    || !isBoundedString(value.projectCode, MAX_IDENTIFIER_LENGTH)
    || !isBoundedNonBlankString(value.projectName, MAX_PROJECT_NAME_LENGTH)
    || !isSafeNonnegativeInteger(value.fileCount)
    || !isSafeNonnegativeInteger(value.totalFileSizeBytes)
  ) {
    throw new Error('invalid desktop sync project')
  }

  return Object.freeze({
    projectRef: value.projectRef,
    canonicalProjectId: value.canonicalProjectId,
    auditProjectId: value.auditProjectId,
    projectCode: value.projectCode,
    projectName: value.projectName,
    fileCount: value.fileCount,
    totalFileSizeBytes: value.totalFileSizeBytes,
  })
}

export function decodeDesktopSyncProjects(value: unknown): DesktopSyncProject[] {
  if (!Array.isArray(value) || value.length > MAX_PROJECT_COUNT) {
    throw new Error('invalid desktop sync projects payload')
  }

  const seenProjectRefs = new Set<string>()
  const projects = value.map((item) => {
    const project = decodeProject(item)
    if (seenProjectRefs.has(project.projectRef)) {
      throw new Error('duplicate desktop sync project reference')
    }
    seenProjectRefs.add(project.projectRef)
    return project
  })

  return projects
}

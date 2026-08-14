type RandomUuidSource = {
  randomUUID?: () => string
}

export function newIdempotencyKey(
  prefix = 'idempotency',
  source: RandomUuidSource | undefined = globalThis.crypto,
): string {
  if (typeof source?.randomUUID === 'function') {
    return source.randomUUID.call(source)
  }
  return `${prefix}-${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`
}

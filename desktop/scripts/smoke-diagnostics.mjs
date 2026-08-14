import {
  existsSync,
  readFileSync,
} from 'node:fs'

export function readSmokeDiagnostic(resultPath) {
  if (!resultPath || !existsSync(resultPath)) return ''
  try {
    return JSON.stringify(
      JSON.parse(readFileSync(resultPath, 'utf8')),
      null,
      2,
    )
  } catch (error) {
    return `unreadable result: ${
      error instanceof Error ? error.message : String(error)
    }`
  }
}

export function formatSmokeFailure({
  caseName,
  cause,
  completed,
  resultPath,
  timedOut = false,
}) {
  const diagnostic = readSmokeDiagnostic(resultPath)
  const causeMessage = cause instanceof Error
    ? cause.message
    : String(cause || '')
  return [
    timedOut
      ? `Electron smoke process timed out: ${caseName}`
      : `${caseName} failed`,
    causeMessage ? `cause:\n${causeMessage}` : '',
    `stdout:\n${completed?.stdout || ''}`,
    `stderr:\n${completed?.stderr || ''}`,
    diagnostic ? `result:\n${diagnostic}` : '',
  ].filter(Boolean).join('\n')
}

export function createSmokeFailure(context) {
  const error = new Error(
    formatSmokeFailure(context),
    context.cause ? { cause: context.cause } : undefined,
  )
  error.smokeDiagnostic = true
  return error
}

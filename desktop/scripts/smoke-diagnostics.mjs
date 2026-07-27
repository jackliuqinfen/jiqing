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
  completed,
  resultPath,
  timedOut = false,
}) {
  const diagnostic = readSmokeDiagnostic(resultPath)
  return [
    timedOut
      ? `Electron smoke process timed out: ${caseName}`
      : `${caseName} failed`,
    `stdout:\n${completed?.stdout || ''}`,
    `stderr:\n${completed?.stderr || ''}`,
    diagnostic ? `result:\n${diagnostic}` : '',
  ].filter(Boolean).join('\n')
}

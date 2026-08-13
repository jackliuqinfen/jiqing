import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { registerHooks } from 'node:module'
import { dirname, join, normalize } from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === '@/api/system') {
      const source = `export function getAuthToken() {
        return globalThis.localStorage?.getItem('__jiqing_auth_token__') || ''
      }`
      return {
        shortCircuit: true,
        url: `data:text/javascript,${encodeURIComponent(source)}`,
      }
    }
    if (specifier.startsWith('@/')) {
      return {
        shortCircuit: true,
        url: new URL(`../src/${specifier.slice(2)}.ts`, import.meta.url).href,
      }
    }
    return nextResolve(specifier, context)
  },
})

const {
  buildManualContractValues,
  buildManualProjectValues,
  newManualProjectIntakeKey,
} = await import('../src/utils/manualProjectIntake.ts')
const {
  DocumentReviewApiError,
  abandonProjectIntakeDraft,
  confirmManualProjectIntake,
  downloadOriginalPdf,
  fetchDocumentVersion,
  originalPdfRequest,
  saveProjectIntakeDraft,
} = await import('../src/api/documentReview.ts')

const manualForm = {
  projectName: '大洋湾小瀛台翻新改造项目',
  ownerUnit: '盐城大洋湾组团开发有限公司',
  constructionUnit: '盐城太悦装配建筑工程有限公司',
  contractAmount: 265057.29,
  contractDate: '2026-02-03',
  managerName: '徐华',
  plannedStartDate: '2026-01-05',
  plannedEndDate: '2026-02-03',
  paymentTerms: '验收后付80%\n\n结算后付97%',
  contractorName: '徐华',
  contractorContact: '13800000000',
  companyRole: '施工单位',
  settlementStatus: 'not_started',
  submittedAmount: 0,
  paidAmount: 0,
  description: '小瀛台室内翻新',
  projectCode: 'PROTECTED-CODE',
  projectStatus: 'awarded',
  auditStage: 'not_linked',
  auditProjectId: 'protected-audit-id',
}

test('buildManualContractValues converts exact RMB to integer fen and preserves Chinese names', () => {
  assert.deepEqual(buildManualContractValues(manualForm), {
    'project.name': '大洋湾小瀛台翻新改造项目',
    'party.owner': '盐城大洋湾组团开发有限公司',
    'party.contractor': '盐城太悦装配建筑工程有限公司',
    'contract.amount': 26505729,
    'contract.signed_date': '2026-02-03',
    'project.manager': '徐华',
    'contract.start_date': '2026-01-05',
    'contract.end_date': '2026-02-03',
    'contract.payment_terms': ['验收后付80%', '结算后付97%'],
  })
})

test('buildManualContractValues rejects invalid, nonpositive, nonfinite, and sub-cent money', () => {
  for (const contractAmount of [0, -1, Number.NaN, Number.POSITIVE_INFINITY, 0.001, 1.234, '1.001']) {
    assert.throws(
      () => buildManualContractValues({ ...manualForm, contractAmount }),
      undefined,
      `contractAmount=${String(contractAmount)}`,
    )
  }
})

test('buildManualContractValues rejects missing critical contract facts and blank payment terms', () => {
  for (const [key, value] of [
    ['projectName', ''],
    ['ownerUnit', '   '],
    ['constructionUnit', ''],
    ['contractDate', ''],
    ['paymentTerms', '\n  \n'],
  ]) {
    assert.throws(() => buildManualContractValues({ ...manualForm, [key]: value }))
  }
})

test('buildManualProjectValues emits only the backend whitelist and appends existing note format', () => {
  const result = buildManualProjectValues(manualForm, {
    projectType: '装修工程',
    projectLocation: '盐城市亭湖区',
  })

  assert.deepEqual(result, {
    contractorName: '徐华',
    contractorContact: '13800000000',
    companyRole: '施工单位',
    settlementStatus: 'not_started',
    submittedAmount: 0,
    paidAmount: 0,
    paymentTerms: '验收后付80%\n\n结算后付97%',
    plannedStartDate: '2026-01-05',
    plannedEndDate: '2026-02-03',
    description: '小瀛台室内翻新\n项目类型：装修工程\n项目地点：盐城市亭湖区',
  })
  for (const protectedKey of [
    'projectCode',
    'projectName',
    'contractDate',
    'constructionUnit',
    'ownerUnit',
    'managerName',
    'projectStatus',
    'auditStage',
    'auditProjectId',
    'contractAmount',
  ]) {
    assert.equal(Object.hasOwn(result, protectedKey), false, protectedKey)
  }
})

test('newManualProjectIntakeKey returns opaque unique keys for caller-held stable lifecycle', () => {
  const first = newManualProjectIntakeKey()
  const second = newManualProjectIntakeKey()
  assert.match(first, /^[0-9a-f-]{16,}$/i)
  assert.notEqual(first, second)
})

function installAuthToken() {
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem(key) {
        return key === '__jiqing_auth_token__' ? 'manual-test-token' : null
      },
    },
  })
}

test('manual intake API uses authenticated escaped routes and exact CAS/confirmation payloads', async () => {
  installAuthToken()
  const calls = []
  const metadata = {
    id: 'version/1',
    documentId: 'document-1',
    name: '合同.pdf',
    mimeType: 'application/pdf',
    fileSize: 8,
    uploadedAt: '2026-02-03T00:00:00Z',
    documentType: 'construction_contract',
    alreadyConfirmedProjectId: null,
  }
  const draft = {
    id: 'draft/1',
    ownerUserId: 'user-1',
    status: 'document_attached',
    documentId: 'document-1',
    documentVersionId: 'version/1',
    schemaVersion: 'contract.v1',
    values: {},
    projectValues: {},
    uiState: { wizardStep: 0, pdfPage: 1, pdfScale: 1, previewCollapsed: false },
    revision: 4,
    fallbackReason: 'manual_selected',
    fallbackNote: '',
    completedProjectId: '',
    createdAt: '2026-02-03T00:00:00Z',
    updatedAt: '2026-02-03T00:00:00Z',
  }
  const confirmation = {
    status: 'created',
    replayed: false,
    projectId: 'project-1',
    snapshotId: 'snapshot-1',
    fact: { type: 'contract', id: 'contract-1' },
    project: { id: 'project-1', projectName: manualForm.projectName },
  }
  Object.defineProperty(globalThis, 'fetch', {
    configurable: true,
    value: async (input, init = {}) => {
      const url = String(input)
      calls.push({ url, init })
      if (url.endsWith('/original')) {
        return new Response(new Blob(['%PDF-1.7']), {
          status: 200,
          headers: { 'Content-Type': 'application/pdf' },
        })
      }
      let data = metadata
      if (url.endsWith('/manual-project-confirmation')) data = confirmation
      else if (url.includes('/project-intake-drafts/')) data = draft
      return new Response(JSON.stringify({ success: true, data }), {
        status: init.method === 'POST' ? 200 : 200,
        headers: { 'Content-Type': 'application/json' },
      })
    },
  })

  assert.deepEqual(originalPdfRequest('version/1'), {
    url: '/api/document-versions/version%2F1/original',
    httpHeaders: { Authorization: 'Bearer manual-test-token' },
  })
  assert.deepEqual(await fetchDocumentVersion('version/1'), metadata)
  assert.equal(await (await downloadOriginalPdf('version/1')).text(), '%PDF-1.7')

  const confirmationRequest = {
    idempotencyKey: 'manual-project:stable-key',
    formTemplateVersion: 'manual-project-wizard.v1',
    draftId: 'draft/1',
    expectedDraftRevision: 4,
    contractValues: buildManualContractValues(manualForm),
    projectValues: buildManualProjectValues(manualForm, {}),
  }
  assert.deepEqual(
    await confirmManualProjectIntake('version/1', confirmationRequest),
    confirmation,
  )
  await saveProjectIntakeDraft('draft/1', {
    expectedRevision: 4,
    projectValues: { description: '保存' },
    uiState: { wizardStep: 1 },
  })
  await abandonProjectIntakeDraft('draft/1', 4)

  assert.deepEqual(
    calls.map(({ url, init }) => [url, init.method || 'GET']),
    [
      ['/api/document-versions/version%2F1', 'GET'],
      ['/api/document-versions/version%2F1/original', 'GET'],
      ['/api/document-versions/version%2F1/manual-project-confirmation', 'POST'],
      ['/api/project-intake-drafts/draft%2F1', 'POST'],
      ['/api/project-intake-drafts/draft%2F1/abandon', 'POST'],
    ],
  )
  for (const { init } of calls) {
    assert.equal(new Headers(init.headers).get('Authorization'), 'Bearer manual-test-token')
  }
  assert.deepEqual(JSON.parse(calls[2].init.body), confirmationRequest)
  assert.deepEqual(JSON.parse(calls[3].init.body), {
    expectedRevision: 4,
    projectValues: { description: '保存' },
    uiState: { wizardStep: 1 },
  })
  assert.deepEqual(JSON.parse(calls[4].init.body), { expectedRevision: 4 })
})

test('manual confirmation and original download preserve structured and non-JSON HTTP errors', async () => {
  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({
        success: false,
        code: 'draft_version_conflict',
        error: '草稿已在其他窗口更新，请刷新后继续。',
      }),
      { status: 409, headers: { 'Content-Type': 'application/json' } },
    )
  await assert.rejects(
    () =>
      confirmManualProjectIntake('version-1', {
        idempotencyKey: 'manual-project:key',
        formTemplateVersion: 'manual-project-wizard.v1',
        draftId: 'draft-1',
        expectedDraftRevision: 1,
        contractValues: buildManualContractValues(manualForm),
        projectValues: buildManualProjectValues(manualForm, {}),
      }),
    (error) =>
      error instanceof DocumentReviewApiError &&
      error.status === 409 &&
      error.code === 'draft_version_conflict',
  )

  globalThis.fetch = async () => new Response('<html>bad gateway</html>', { status: 502 })
  await assert.rejects(
    () => downloadOriginalPdf('version-1'),
    (error) => error instanceof DocumentReviewApiError && error.status === 502,
  )
})

test('draft mutation API rejects callers that omit the revision at compile time', () => {
  const projectRoot = dirname(fileURLToPath(new URL('../package.json', import.meta.url)))
  const virtualFile = join(projectRoot, 'test', '__manualDraftCasContract.ts')
  const config = ts.readConfigFile(join(projectRoot, 'tsconfig.json'), ts.sys.readFile)
  assert.equal(config.error, undefined)
  const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, projectRoot)
  const source = `
    import {
      abandonProjectIntakeDraft,
      saveProjectIntakeDraft,
    } from '../src/api/documentReview.ts'

    saveProjectIntakeDraft('draft-1', { values: { 'project.name': '陈旧值' } })
    abandonProjectIntakeDraft('draft-1')
  `
  const host = ts.createCompilerHost(parsed.options)
  const normalizedVirtualFile = normalize(virtualFile).toLowerCase()
  const isVirtualFile = (fileName) => normalize(fileName).toLowerCase() === normalizedVirtualFile
  const originalFileExists = host.fileExists.bind(host)
  const originalReadFile = host.readFile.bind(host)
  const originalGetSourceFile = host.getSourceFile.bind(host)
  host.fileExists = (fileName) => isVirtualFile(fileName) || originalFileExists(fileName)
  host.readFile = (fileName) => isVirtualFile(fileName) ? source : originalReadFile(fileName)
  host.getSourceFile = (fileName, languageVersion, onError, shouldCreateNewSourceFile) => {
    if (isVirtualFile(fileName)) {
      return ts.createSourceFile(fileName, source, languageVersion, true, ts.ScriptKind.TS)
    }
    return originalGetSourceFile(fileName, languageVersion, onError, shouldCreateNewSourceFile)
  }
  const program = ts.createProgram({
    rootNames: [virtualFile, join(projectRoot, 'src', 'env.d.ts')],
    options: parsed.options,
    host,
  })
  const messages = ts.getPreEmitDiagnostics(program).map((diagnostic) =>
    ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n'),
  )

  assert.equal(messages.length, 2, messages.join('\n'))
  assert.ok(messages.some((message) => message.includes('expectedRevision')), messages.join('\n'))
  assert.ok(messages.some((message) => message.includes('Expected 2 arguments')), messages.join('\n'))
})

test('draft mutation sends only caller-held revisions and advances from each response', async () => {
  const calls = []
  const draft = {
    id: 'draft-cas',
    ownerUserId: 'user-1',
    status: 'draft',
    documentId: '',
    documentVersionId: '',
    schemaVersion: 'contract.v1',
    values: {},
    projectValues: {},
    uiState: { wizardStep: 0, pdfPage: 1, pdfScale: 1, previewCollapsed: false },
    revision: 8,
    fallbackReason: 'manual_selected',
    fallbackNote: '',
    completedProjectId: '',
    createdAt: '2026-02-03T00:00:00Z',
    updatedAt: '2026-02-03T00:00:00Z',
  }
  globalThis.fetch = async (input, init = {}) => {
    const url = String(input)
    calls.push({ url, init })
    const data = calls.length === 1
      ? draft
      : { ...draft, status: 'abandoned', revision: 9 }
    return new Response(JSON.stringify({ success: true, data }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  let revision = 7
  const saved = await saveProjectIntakeDraft('draft-cas', {
    expectedRevision: revision,
    values: { 'project.name': '当前窗口值' },
  })
  revision = saved.revision
  const abandoned = await abandonProjectIntakeDraft('draft-cas', revision)
  revision = abandoned.revision

  assert.deepEqual(
    calls.map(({ url, init }) => [url, init.method || 'GET']),
    [
      ['/api/project-intake-drafts/draft-cas', 'POST'],
      ['/api/project-intake-drafts/draft-cas/abandon', 'POST'],
    ],
  )
  assert.deepEqual(JSON.parse(calls[0].init.body), {
    values: { 'project.name': '当前窗口值' },
    expectedRevision: 7,
  })
  assert.deepEqual(JSON.parse(calls[1].init.body), { expectedRevision: 8 })
  assert.equal(revision, 9)
})

test('draft types expose persisted project/UI state and required optimistic revision contracts', () => {
  const source = readFileSync(
    new URL('../src/types/documentReview.ts', import.meta.url),
    'utf8',
  )
  const draft = source.match(/export interface ProjectIntakeDraft \{([\s\S]*?)\n\}/)?.[1]
  const save = source.match(
    /export interface SaveProjectIntakeDraftRequest[^\{]*\{([\s\S]*?)\n\}/,
  )?.[1]

  assert.ok(draft)
  assert.match(draft, /\bprojectValues:\s*ManualProjectValues\b/)
  assert.match(draft, /\buiState:\s*ManualProjectIntakeUiState\b/)
  assert.match(draft, /\brevision:\s*number\b/)
  assert.ok(save)
  assert.match(save, /\bexpectedRevision:\s*number\b/)
  assert.doesNotMatch(save, /expectedRevision\?:/)
})

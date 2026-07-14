import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { registerHooks } from 'node:module'
import test from 'node:test'

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
  DocumentReviewApiError,
  confirmDocumentReview,
  fetchDocumentPageBlob,
  fetchDocumentReview,
  fetchRecognitionJob,
  saveReviewDecisions,
  startRecognition,
  uploadDocument,
} = await import('../src/api/documentReview.ts')
const { deriveReviewCommands, mergeSavedReview } = await import(
  '../src/utils/documentReviewState.ts'
)

const uploadResult = {
  replayed: false,
  crossProjectDuplicateCount: 0,
  document: {
    id: 'document-1',
    type: 'construction_contract',
    lifecycleStage: 'contract_handoff',
    projectId: 'project-1',
    candidateProjectId: null,
    status: 'uploaded',
    createdBy: 'user-1',
    createdAt: '2026-07-14T00:00:00Z',
    updatedAt: '2026-07-14T00:00:00Z',
  },
  version: {
    id: 'version-1',
    documentId: 'document-1',
    number: 1,
    name: 'contract.pdf',
    mimeType: 'application/pdf',
    fileSize: 123,
    uploadedBy: 'user-1',
    uploadedAt: '2026-07-14T00:00:00Z',
  },
}

const recognitionJob = {
  id: 'job-1',
  documentVersionId: 'version-1',
  status: 'queued',
  adapterKey: 'manual',
  schemaVersion: 'construction-contract.v1',
  attempts: 0,
  maxAttempts: 3,
  blockCount: 0,
  fieldCount: 0,
  reviewId: 'review-1',
  reviewStatus: '',
  error: null,
  createdAt: '2026-07-14T00:00:00Z',
  updatedAt: '2026-07-14T00:00:00Z',
  finishedAt: '',
}

test('RecognitionJob exposes the backend reviewId contract', () => {
  const source = readFileSync(
    new URL('../src/types/documentReview.ts', import.meta.url),
    'utf8',
  )
  const recognitionJobContract = source.match(
    /export interface RecognitionJob \{([\s\S]*?)\n\}/,
  )?.[1]

  assert.ok(recognitionJobContract)
  assert.match(recognitionJobContract, /\breviewId:\s*string\b/)
})

function makeReview(overrides = {}) {
  return {
    id: 'review-1',
    status: 'open',
    reviewVersion: 2,
    projectId: 'project-1',
    projectCandidates: [{ projectId: 'project-1', recommended: true }],
    reviewer: { id: '', name: '' },
    document: {
      id: 'document-1',
      type: 'construction_contract',
      lifecycleStage: 'contract_handoff',
      name: 'contract.pdf',
      mimeType: 'application/pdf',
      fileSize: 123,
      version: 1,
    },
    pages: [],
    sections: [
      {
        key: 'contract',
        fields: [
          {
            id: 'field-amount',
            semanticKey: 'contract.amount',
            rawValue: '壹万元整',
            aiValue: '1000000',
            confidence: 0.91,
            validationStatus: 'valid',
            anchors: [],
            decision: null,
          },
          {
            id: 'field-note',
            semanticKey: 'contract.note',
            rawValue: '',
            aiValue: null,
            confidence: null,
            validationStatus: 'invalid',
            anchors: [],
            decision: null,
          },
        ],
      },
    ],
    blockers: [],
    warnings: [],
    allowedCommands: ['save_decisions', 'confirm'],
    ...overrides,
  }
}

function pendingDecision(fieldId, confirmedValue, reason) {
  return {
    fieldId,
    decision: reason ? 'modified' : 'accepted',
    confirmedValue,
    ...(reason ? { reason } : {}),
  }
}

function installAuthToken() {
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: {
      getItem(key) {
        return key === '__jiqing_auth_token__' ? 'test-token' : null
      },
    },
  })
}

test('uploadDocument uses authenticated XHR, exact multipart fields, and computable progress', async () => {
  installAuthToken()

  class FakeXMLHttpRequest {
    static latest
    upload = {}
    headers = {}
    method = ''
    url = ''
    body = null
    status = 0
    responseText = ''

    constructor() {
      FakeXMLHttpRequest.latest = this
    }

    open(method, url) {
      this.method = method
      this.url = url
    }

    setRequestHeader(name, value) {
      this.headers[name] = value
    }

    send(body) {
      this.body = body
    }
  }

  Object.defineProperty(globalThis, 'XMLHttpRequest', {
    configurable: true,
    value: FakeXMLHttpRequest,
  })

  const progress = []
  const request = uploadDocument(
    {
      file: new File(['contract'], 'contract.pdf', { type: 'application/pdf' }),
      documentType: 'construction_contract',
      lifecycleStage: 'contract_handoff',
      projectId: 'project-1',
      candidateProjectId: 'candidate-1',
      documentId: 'document-1',
    },
    (percent) => progress.push(percent),
  )
  const xhr = FakeXMLHttpRequest.latest

  assert.equal(xhr.method, 'POST')
  assert.equal(xhr.url, '/api/documents/uploads')
  assert.equal(xhr.headers.Authorization, 'Bearer test-token')
  assert.equal(xhr.body.get('documentType'), 'construction_contract')
  assert.equal(xhr.body.get('lifecycleStage'), 'contract_handoff')
  assert.equal(xhr.body.get('projectId'), 'project-1')
  assert.equal(xhr.body.get('candidateProjectId'), 'candidate-1')
  assert.equal(xhr.body.get('documentId'), 'document-1')
  assert.equal(xhr.body.get('file').name, 'contract.pdf')

  xhr.upload.onprogress({ lengthComputable: false, loaded: 1, total: 2 })
  xhr.upload.onprogress({ lengthComputable: true, loaded: 1, total: 4 })
  xhr.status = 201
  xhr.responseText = JSON.stringify({ success: true, data: uploadResult })
  xhr.onload()

  assert.deepEqual(await request, uploadResult)
  assert.deepEqual(progress, [25, 100])
})

test('JSON and blob API functions use exact authenticated routes and request mappings', async () => {
  installAuthToken()
  const calls = []
  const review = makeReview()
  const confirmation = {
    status: 'created',
    replayed: false,
    projectId: 'project-1',
    snapshotId: 'snapshot-1',
    fact: { type: 'contract', id: 'contract-1' },
  }

  Object.defineProperty(globalThis, 'fetch', {
    configurable: true,
    value: async (input, init = {}) => {
      const url = String(input)
      calls.push({ url, init })
      if (url.endsWith('/image')) {
        return new Response(new Blob(['page']), { status: 200 })
      }
      let data = recognitionJob
      if (url.includes('/document-reviews/') && url.endsWith('/decisions')) data = review
      else if (url.includes('/document-reviews/') && url.endsWith('/confirm')) data = confirmation
      else if (url.includes('/document-reviews/')) data = review
      return new Response(JSON.stringify({ success: true, data }), {
        status: init.method === 'POST' ? 201 : 200,
        headers: { 'Content-Type': 'application/json' },
      })
    },
  })

  const startRequest = {
    documentVersionId: 'version-1',
    adapterKey: 'manual',
    schemaVersion: 'construction-contract.v1',
    idempotencyKey: 'recognize-1',
  }
  const saveRequest = {
    expectedReviewVersion: 2,
    decisions: [pendingDecision('field-amount', '1000000')],
    bulk: false,
  }
  const confirmRequest = {
    expectedReviewVersion: 3,
    idempotencyKey: 'confirm-1',
    formTemplateVersion: 'contract-form.v1',
    projectId: 'project-1',
  }

  assert.deepEqual(await startRecognition(startRequest), recognitionJob)
  assert.deepEqual(await fetchRecognitionJob('job/1'), recognitionJob)
  assert.deepEqual(await fetchDocumentReview('review/1'), review)
  assert.deepEqual(await saveReviewDecisions('review/1', saveRequest), review)
  assert.deepEqual(await confirmDocumentReview('review/1', confirmRequest), confirmation)
  assert.equal(await (await fetchDocumentPageBlob('version/1', 2)).text(), 'page')

  assert.deepEqual(
    calls.map(({ url, init }) => [url, init.method || 'GET']),
    [
      ['/api/document-recognition-jobs', 'POST'],
      ['/api/document-recognition-jobs/job%2F1', 'GET'],
      ['/api/document-reviews/review%2F1', 'GET'],
      ['/api/document-reviews/review%2F1/decisions', 'POST'],
      ['/api/document-reviews/review%2F1/confirm', 'POST'],
      ['/api/document-versions/version%2F1/pages/2/image', 'GET'],
    ],
  )
  assert.deepEqual(JSON.parse(calls[0].init.body), startRequest)
  assert.deepEqual(JSON.parse(calls[3].init.body), saveRequest)
  assert.deepEqual(JSON.parse(calls[4].init.body), confirmRequest)
  for (const { init } of calls) {
    assert.equal(new Headers(init.headers).get('Authorization'), 'Bearer test-token')
  }
})

test('API errors preserve server concurrency details and map network/non-JSON failures', async () => {
  const saveRequest = {
    expectedReviewVersion: 2,
    decisions: [pendingDecision('field-amount', '1000000')],
  }
  const original = structuredClone(saveRequest)

  globalThis.fetch = async () =>
    new Response(
      JSON.stringify({
        success: false,
        code: 'review_version_conflict',
        error: '复核内容已被更新，请刷新后重试。',
        expectedReviewVersion: 2,
        currentReviewVersion: 3,
      }),
      { status: 409, headers: { 'Content-Type': 'application/json' } },
    )
  await assert.rejects(
    () => saveReviewDecisions('review-1', saveRequest),
    (error) =>
      error instanceof DocumentReviewApiError &&
      error.status === 409 &&
      error.code === 'review_version_conflict' &&
      error.currentReviewVersion === 3,
  )
  assert.deepEqual(saveRequest, original)

  globalThis.fetch = async () => {
    throw new Error('offline')
  }
  await assert.rejects(
    () => fetchRecognitionJob('job-1'),
    (error) =>
      error instanceof DocumentReviewApiError &&
      error.status === 0 &&
      error.code === 'network_error',
  )

  globalThis.fetch = async () => new Response('<html>bad gateway</html>', { status: 502 })
  await assert.rejects(
    () => fetchDocumentReview('review-1'),
    (error) => error instanceof DocumentReviewApiError && error.status === 502,
  )
})

test('deriveReviewCommands stops polling at every terminal recognition state', () => {
  for (const status of ['queued', 'running']) {
    const commands = deriveReviewCommands({
      recognitionJob: { ...recognitionJob, status },
      review: null,
      pendingDecisions: {},
    })
    assert.equal(commands.shouldPollRecognition, true, status)
  }

  for (const status of ['review_ready', 'manual_required', 'failed']) {
    const commands = deriveReviewCommands({
      recognitionJob: { ...recognitionJob, status },
      review: null,
      pendingDecisions: {},
    })
    assert.equal(commands.shouldPollRecognition, false, status)
  }
})

test('deriveReviewCommands exposes retry and manual entry only for backend-supported states', () => {
  const failed = deriveReviewCommands({
    recognitionJob: { ...recognitionJob, status: 'failed' },
    review: null,
    pendingDecisions: {},
  })
  assert.equal(failed.canRetryRecognition, true)
  assert.equal(failed.requiresManualEntry, false)

  const manual = deriveReviewCommands({
    recognitionJob: {
      ...recognitionJob,
      status: 'manual_required',
      error: { code: 'ocr_provider_not_configured', message: '' },
      fieldCount: 0,
    },
    review: null,
    pendingDecisions: {},
  })
  assert.equal(manual.canRetryRecognition, true)
  assert.equal(manual.requiresManualEntry, true)
})

test('deriveReviewCommands obeys allowedCommands, blockers, unsaved work, and confirmed immutability', () => {
  const ready = deriveReviewCommands({
    recognitionJob: null,
    review: makeReview(),
    pendingDecisions: {},
  })
  assert.equal(ready.canEditDecisions, true)
  assert.equal(ready.canSaveDecisions, false)
  assert.equal(ready.canConfirm, true)

  const pending = deriveReviewCommands({
    recognitionJob: null,
    review: makeReview(),
    pendingDecisions: {
      'field-amount': pendingDecision('field-amount', '1000000'),
    },
  })
  assert.equal(pending.canSaveDecisions, true)
  assert.equal(pending.canConfirm, false)

  const blocked = deriveReviewCommands({
    recognitionJob: null,
    review: makeReview({
      blockers: [
        {
          code: 'critical_field_unresolved',
          field: 'contract.amount',
          message: '关键字段必须逐项人工确认。',
          severity: 'blocker',
        },
      ],
    }),
    pendingDecisions: {},
  })
  assert.equal(blocked.canConfirm, false)

  const confirmedReview = makeReview({ status: 'confirmed', allowedCommands: [] })
  const confirmed = deriveReviewCommands({
    recognitionJob: null,
    review: confirmedReview,
    pendingDecisions: {
      'field-note': pendingDecision('field-note', 'manual', '人工补录'),
    },
  })
  assert.equal(confirmed.isReviewImmutable, true)
  assert.equal(confirmed.canEditDecisions, false)
  assert.equal(confirmed.canSaveDecisions, false)
  assert.equal(confirmed.canConfirm, false)
})

test('deriveReviewCommands excludes every critical field from bulk acceptance', () => {
  const review = makeReview({
    sections: [
      {
        key: 'contract',
        fields: [
          makeReview().sections[0].fields[0],
          {
            ...makeReview().sections[0].fields[1],
            id: 'field-payment',
            semanticKey: 'contract.payment_terms',
          },
          {
            ...makeReview().sections[0].fields[1],
            id: 'field-note',
            semanticKey: 'contract.note',
            rawValue: '现场条款',
            aiValue: '现场条款',
            validationStatus: 'valid',
          },
          {
            ...makeReview().sections[0].fields[1],
            id: 'field-empty',
            semanticKey: 'contract.empty_note',
          },
        ],
      },
    ],
  })
  const commands = deriveReviewCommands({
    recognitionJob: null,
    review,
    pendingDecisions: {},
  })

  assert.deepEqual(commands.individualReviewFieldIds, ['field-amount', 'field-payment'])
  assert.deepEqual(commands.bulkAcceptableFieldIds, ['field-note'])
})

test('mergeSavedReview rejects stale responses and retains decisions changed while saving', () => {
  const submitted = pendingDecision('field-amount', '1000000')
  const changedWhileSaving = pendingDecision('field-amount', '1200000', '复核原文后修改')
  const untouched = pendingDecision('field-note', '现场补充', '人工补录')
  const state = {
    recognitionJob: null,
    review: makeReview(),
    pendingDecisions: {
      'field-amount': changedWhileSaving,
      'field-note': untouched,
    },
  }

  const stale = mergeSavedReview(state, makeReview({ reviewVersion: 1 }), [submitted])
  assert.equal(stale, state)

  const savedReview = makeReview({
    reviewVersion: 3,
    sections: [
      {
        key: 'contract',
        fields: makeReview().sections[0].fields.map((field) =>
          field.id === 'field-amount'
            ? {
                ...field,
                decision: {
                  decision: 'accepted',
                  aiValue: '1000000',
                  confirmedValue: '1000000',
                  reason: '',
                  reviewer: { id: 'user-1', name: '复核人' },
                },
              }
            : field,
        ),
      },
    ],
  })
  const merged = mergeSavedReview(state, savedReview, [submitted])

  assert.equal(merged.review.reviewVersion, 3)
  assert.equal(merged.review.sections[0].fields[1].aiValue, null)
  assert.deepEqual(merged.pendingDecisions, {
    'field-amount': changedWhileSaving,
    'field-note': untouched,
  })
  assert.notEqual(merged.pendingDecisions, state.pendingDecisions)
})

test('mergeSavedReview clears only submitted decisions and never mutates a confirmed review', () => {
  const submitted = pendingDecision('field-amount', '1000000')
  const state = {
    recognitionJob: null,
    review: makeReview(),
    pendingDecisions: {
      'field-amount': submitted,
      'field-note': pendingDecision('field-note', '保留', '仍未保存'),
    },
  }
  const merged = mergeSavedReview(state, makeReview({ reviewVersion: 3 }), [submitted])
  assert.deepEqual(Object.keys(merged.pendingDecisions), ['field-note'])

  const confirmedState = {
    ...state,
    review: makeReview({ status: 'confirmed', allowedCommands: [] }),
  }
  assert.equal(
    mergeSavedReview(confirmedState, makeReview({ reviewVersion: 99 }), [submitted]),
    confirmedState,
  )
})

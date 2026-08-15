import { getAuthToken } from '@/api/system'
import type {
  ConfirmDocumentReviewRequest,
  ConfirmDocumentReviewResponse,
  CreateProjectIntakeDraftRequest,
  DocumentReview,
  DocumentReviewErrorPayload,
  DocumentUploadRequest,
  DocumentUploadResponse,
  ExternalImportRequest,
  ManualProjectConfirmationRequest,
  ManualProjectConfirmationResponse,
  ManualReviewRequest,
  DocumentVersionMetadata,
  OriginalPdfRequest,
  ProjectIntakeDraft,
  RecognitionJob,
  RetryRecognitionRequest,
  SaveReviewDecisionsRequest,
  SaveProjectIntakeDraftRequest,
  StartRecognitionRequest,
} from '@/types/documentReview'

const API_BASE = import.meta.env?.VITE_AUDIT_API_BASE || '/api'
// Uploads are streamed and may legitimately take longer than the normal JSON
// request path. Keep the UI bounded without rejecting a reasonably slow PDF.
export const DOCUMENT_UPLOAD_TIMEOUT_MS = 5 * 60 * 1000

type ApiSuccess<T> = { success: true; data: T; error?: never }
type ApiFailure = DocumentReviewErrorPayload & { success: false; data?: never }
type ApiResult<T> = ApiSuccess<T> | ApiFailure

export class DocumentReviewApiError extends Error {
  readonly status: number
  readonly payload: DocumentReviewErrorPayload
  readonly code?: string
  readonly blockers
  readonly expectedReviewVersion?: number
  readonly currentReviewVersion?: number

  constructor(status: number, payload: DocumentReviewErrorPayload) {
    super(payload.error || `请求失败: ${status || '网络异常'}`)
    this.name = 'DocumentReviewApiError'
    this.status = status
    this.payload = payload
    this.code = payload.code
    this.blockers = payload.blockers || []
    this.expectedReviewVersion = payload.expectedReviewVersion
    this.currentReviewVersion = payload.currentReviewVersion
  }
}

function fallbackError(status: number): DocumentReviewErrorPayload {
  return { error: `请求失败: ${status || '网络异常'}` }
}

function networkError(): DocumentReviewApiError {
  return new DocumentReviewApiError(0, {
    code: 'network_error',
    error: '网络连接失败，请检查连接后重试。',
  })
}

function uploadTimeoutError(): DocumentReviewApiError {
  return new DocumentReviewApiError(0, {
    code: 'upload_timeout',
    error: '合同 PDF 上传超时，请检查网络后重试；如页面显示已上传，请先刷新确认。',
  })
}

function parsePayload<T>(value: unknown, status: number): ApiResult<T> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return { success: false, ...fallbackError(status) }
  }
  return value as ApiResult<T>
}

function errorPayload<T>(payload: ApiResult<T>, status: number): DocumentReviewErrorPayload {
  return payload.success ? fallbackError(status) : payload
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken()
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(init?.headers || {}),
      },
    })
  } catch {
    throw networkError()
  }

  let payload: ApiResult<T> = { success: false, ...fallbackError(response.status) }
  try {
    payload = parsePayload<T>(await response.json(), response.status)
  } catch {
    // Preserve the HTTP status when an upstream proxy returns a non-JSON body.
  }
  if (!response.ok || !payload.success || payload.data === undefined) {
    throw new DocumentReviewApiError(response.status, errorPayload(payload, response.status))
  }
  return payload.data
}

export function uploadDocument(
  data: DocumentUploadRequest,
  onProgress?: (percent: number) => void,
): Promise<DocumentUploadResponse> {
  const token = getAuthToken()
  const form = new FormData()
  form.append('documentType', data.documentType)
  form.append('lifecycleStage', data.lifecycleStage)
  if (data.projectId) form.append('projectId', data.projectId)
  if (data.candidateProjectId) form.append('candidateProjectId', data.candidateProjectId)
  if (data.documentId) form.append('documentId', data.documentId)
  form.append('file', data.file)

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `${API_BASE}/documents/uploads`)
    xhr.timeout = DOCUMENT_UPLOAD_TIMEOUT_MS
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || event.total <= 0) return
      onProgress?.(Math.min(99, Math.round((event.loaded / event.total) * 100)))
    }
    xhr.onerror = () => reject(networkError())
    xhr.onabort = () =>
      reject(new DocumentReviewApiError(0, { code: 'request_aborted', error: '上传已取消。' }))
    xhr.ontimeout = () => reject(uploadTimeoutError())
    xhr.onload = () => {
      let payload: ApiResult<DocumentUploadResponse> = {
        success: false,
        ...fallbackError(xhr.status),
      }
      try {
        payload = parsePayload<DocumentUploadResponse>(
          JSON.parse(xhr.responseText || 'null'),
          xhr.status,
        )
      } catch {
        // Use the status-based error when the response is not JSON.
      }
      if (xhr.status < 200 || xhr.status >= 300 || !payload.success || payload.data === undefined) {
        reject(new DocumentReviewApiError(xhr.status, errorPayload(payload, xhr.status)))
        return
      }
      onProgress?.(100)
      resolve(payload.data)
    }
    xhr.send(form)
  })
}

export function startRecognition(data: StartRecognitionRequest): Promise<RecognitionJob> {
  return request('/document-recognition-jobs', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function fetchRecognitionJob(jobId: string): Promise<RecognitionJob> {
  return request(`/document-recognition-jobs/${encodeURIComponent(jobId)}`)
}

export function retryRecognition(
  jobId: string,
  data: RetryRecognitionRequest,
): Promise<RecognitionJob> {
  return request(`/document-recognition-jobs/${encodeURIComponent(jobId)}/retry`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function startDirectManualReview(
  versionId: string,
  data: ManualReviewRequest,
): Promise<RecognitionJob> {
  return request(`/document-versions/${encodeURIComponent(versionId)}/manual-review`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function importDirectExternalResult(
  versionId: string,
  data: ExternalImportRequest,
): Promise<RecognitionJob> {
  return request(`/document-versions/${encodeURIComponent(versionId)}/external-import`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function startJobManualReview(
  jobId: string,
  data: ManualReviewRequest,
): Promise<RecognitionJob> {
  return request(`/document-recognition-jobs/${encodeURIComponent(jobId)}/manual-review`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function importJobExternalResult(
  jobId: string,
  data: ExternalImportRequest,
): Promise<RecognitionJob> {
  return request(`/document-recognition-jobs/${encodeURIComponent(jobId)}/external-import`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function createProjectIntakeDraft(
  data: CreateProjectIntakeDraftRequest,
): Promise<ProjectIntakeDraft> {
  return request('/project-intake-drafts', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function listProjectIntakeDrafts(): Promise<ProjectIntakeDraft[]> {
  return request('/project-intake-drafts/mine')
}

export function saveProjectIntakeDraft(
  draftId: string,
  data: SaveProjectIntakeDraftRequest,
): Promise<ProjectIntakeDraft> {
  return request(`/project-intake-drafts/${encodeURIComponent(draftId)}`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function abandonProjectIntakeDraft(
  draftId: string,
  expectedRevision: number,
): Promise<ProjectIntakeDraft> {
  return request(`/project-intake-drafts/${encodeURIComponent(draftId)}/abandon`, {
    method: 'POST',
    body: JSON.stringify({ expectedRevision }),
  })
}

export function fetchDocumentVersion(versionId: string): Promise<DocumentVersionMetadata> {
  return request(`/document-versions/${encodeURIComponent(versionId)}`)
}

export function originalPdfRequest(versionId: string): OriginalPdfRequest {
  const token = getAuthToken()
  return {
    url: `${API_BASE}/document-versions/${encodeURIComponent(versionId)}/original`,
    httpHeaders: token ? { Authorization: `Bearer ${token}` } : {},
  }
}

export async function downloadOriginalPdf(versionId: string): Promise<Blob> {
  const source = originalPdfRequest(versionId)
  let response: Response
  try {
    response = await fetch(source.url, { headers: source.httpHeaders })
  } catch {
    throw networkError()
  }
  if (!response.ok) {
    let payload: DocumentReviewErrorPayload = fallbackError(response.status)
    try {
      payload = errorPayload(parsePayload<never>(await response.json(), response.status), response.status)
    } catch {
      // Preserve the HTTP status when an upstream proxy returns a non-JSON body.
    }
    throw new DocumentReviewApiError(response.status, payload)
  }
  return response.blob()
}

export function confirmManualProjectIntake(
  versionId: string,
  data: ManualProjectConfirmationRequest,
): Promise<ManualProjectConfirmationResponse> {
  return request(`/document-versions/${encodeURIComponent(versionId)}/manual-project-confirmation`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function fetchDocumentReview(reviewId: string): Promise<DocumentReview> {
  return request(`/document-reviews/${encodeURIComponent(reviewId)}`)
}

export function saveReviewDecisions(
  reviewId: string,
  data: SaveReviewDecisionsRequest,
): Promise<DocumentReview> {
  return request(`/document-reviews/${encodeURIComponent(reviewId)}/decisions`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function confirmDocumentReview(
  reviewId: string,
  data: ConfirmDocumentReviewRequest,
): Promise<ConfirmDocumentReviewResponse> {
  return request(`/document-reviews/${encodeURIComponent(reviewId)}/confirm`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function fetchDocumentPageBlob(versionId: string, pageNumber: number): Promise<Blob> {
  const token = getAuthToken()
  let response: Response
  try {
    response = await fetch(
      `${API_BASE}/document-versions/${encodeURIComponent(versionId)}/pages/${pageNumber}/image`,
      { headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) } },
    )
  } catch {
    throw networkError()
  }
  if (!response.ok) {
    let payload: DocumentReviewErrorPayload = fallbackError(response.status)
    try {
      payload = errorPayload(parsePayload<never>(await response.json(), response.status), response.status)
    } catch {
      // Preserve the HTTP status when the image endpoint returns a non-JSON body.
    }
    throw new DocumentReviewApiError(response.status, payload)
  }
  return response.blob()
}

export type DocumentType =
  | 'construction_contract'
  | 'completion_acceptance_certificate'
  | 'final_audit_determination'

export type DocumentLifecycleStage = 'contract_handoff' | 'completed_acceptance' | 'conclusion'

export type DocumentStatus =
  | 'uploaded'
  | 'rendering'
  | 'recognition_queued'
  | 'recognizing'
  | 'review_ready'
  | 'in_review'
  | 'confirmed'
  | 'correction_required'
  | 'manual_required'
  | 'quarantined'
  | 'failed'
  | 'superseded'

export type RecognitionStatus = 'queued' | 'running' | 'review_ready' | 'manual_required' | 'failed'
export type ReviewStatus = 'open' | 'in_review' | 'confirmed' | 'superseded'
export type ReviewDecisionType = 'accepted' | 'modified' | 'rejected' | 'unrecognized'
export type ReviewCommand = 'save_decisions' | 'confirm'
export type ReviewValidationStatus = 'valid' | 'invalid' | 'unvalidated'
export type EvidenceBox = [number, number, number, number]
export type MoneyFen = `${bigint}`

export type JsonPrimitive = string | number | boolean | null
export type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue }
export type ReviewFieldValue = JsonValue

export interface DocumentRecord {
  id: string
  type: DocumentType
  lifecycleStage: DocumentLifecycleStage
  projectId: string | null
  candidateProjectId: string | null
  status: DocumentStatus
  createdBy: string
  createdAt: string
  updatedAt: string
}

export interface DocumentVersion {
  id: string
  documentId: string
  number: number
  name: string
  mimeType: string
  fileSize: number
  uploadedBy: string
  uploadedAt: string
}

export interface DocumentPage {
  id: string
  pageNumber: number
  width: number
  height: number
  dpi: number
  rotationDegrees: number
  qualityScore: number | null
  imageUrl: string
}

export interface DocumentDetail extends DocumentRecord {
  currentVersion: Omit<DocumentVersion, 'documentId'>
  pages: DocumentPage[]
}

export interface DocumentUploadRequest {
  file: File
  documentType: DocumentType
  lifecycleStage: DocumentLifecycleStage
  projectId?: string
  candidateProjectId?: string
  documentId?: string
}

export interface DocumentUploadResponse {
  replayed: boolean
  crossProjectDuplicateCount: number
  document: DocumentRecord
  version: DocumentVersion
}

export interface RecognitionJobError {
  code: string
  message: string
}

export interface RecognitionJob {
  id: string
  documentVersionId: string
  status: RecognitionStatus
  adapterKey: string
  schemaVersion: string
  attempts: number
  maxAttempts: number
  blockCount: number
  fieldCount: number
  reviewId: string
  reviewStatus: ReviewStatus | ''
  error: RecognitionJobError | null
  createdAt: string
  updatedAt: string
  finishedAt: string
}

export interface StartRecognitionRequest {
  documentVersionId: string
  adapterKey?: string
  schemaVersion?: string
  idempotencyKey: string
}

export interface OcrBlock {
  id: string
  pageId: string
  blockType: string
  rawText: string
  confidence: number | null
  bbox: EvidenceBox
  rowIndex: number | null
  columnIndex: number | null
  metadata: Record<string, JsonValue>
}

export interface EvidenceAnchor {
  id: string
  pageId: string
  bbox: EvidenceBox
  sourceText: string
}

export interface ReviewActor {
  id: string
  name: string
}

export interface ReviewDecision {
  decision: ReviewDecisionType
  aiValue: ReviewFieldValue
  confirmedValue: ReviewFieldValue
  reason: string
  reviewer: ReviewActor
}

export interface ExtractedField {
  id: string
  semanticKey: string
  rawValue: string
  aiValue: ReviewFieldValue
  confidence: number | null
  validationStatus: ReviewValidationStatus
  anchors: EvidenceAnchor[]
  decision: ReviewDecision | null
}

export interface DocumentReviewSection {
  key: string
  fields: ExtractedField[]
}

export interface DocumentReviewIssue {
  code: string
  field: string
  message: string
  severity?: string
  [key: string]: unknown
}

export interface ProjectCandidate {
  projectId: string
  recommended: boolean
}

export interface ReviewDocument {
  id: string
  type: DocumentType
  lifecycleStage: DocumentLifecycleStage
  name: string
  mimeType: string
  fileSize: number
  version: number
}

export interface DocumentReview {
  id: string
  status: ReviewStatus
  reviewVersion: number
  projectId: string | null
  projectCandidates: ProjectCandidate[]
  reviewer: ReviewActor
  document: ReviewDocument
  pages: DocumentPage[]
  sections: DocumentReviewSection[]
  blockers: DocumentReviewIssue[]
  warnings: DocumentReviewIssue[]
  allowedCommands: ReviewCommand[]
}

export interface ReviewDecisionInput {
  fieldId: string
  decision: ReviewDecisionType
  confirmedValue?: ReviewFieldValue
  reason?: string
}

export interface SaveReviewDecisionsRequest {
  expectedReviewVersion: number
  decisions: ReviewDecisionInput[]
  bulk?: boolean
}

export interface ConfirmDocumentReviewRequest {
  expectedReviewVersion: number
  idempotencyKey: string
  formTemplateVersion: string
  projectId?: string
}

export type ConfirmationFactType = 'contract' | 'acceptance' | 'determination'

export interface ConfirmationFact {
  type: ConfirmationFactType
  id: string
}

export interface ConfirmDocumentReviewResponse {
  status: 'created'
  replayed: boolean
  projectId: string | null
  snapshotId: string | null
  fact: ConfirmationFact | null
}

export interface DocumentReviewErrorPayload {
  success?: false
  code?: string
  error?: string
  blockers?: DocumentReviewIssue[]
  expectedReviewVersion?: number
  currentReviewVersion?: number
  field?: string
  [key: string]: unknown
}

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
  sourceRecognitionJobId: string
  fallbackReason: string
  fallbackNote: string
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

export interface RetryRecognitionRequest {
  idempotencyKey: string
}

export type ContractDraftValue = string | number | string[] | null
export type ContractDraftValues = Record<string, ContractDraftValue>

export interface ManualProjectIntakeForm {
  projectName: string
  ownerUnit: string
  constructionUnit: string
  contractAmount: number | string
  contractDate: string
  managerName: string
  plannedStartDate: string
  plannedEndDate: string
  paymentTerms: string
  contractorName: string
  contractorContact: string
  companyRole: string
  settlementStatus: string
  submittedAmount: number | string
  paidAmount: number | string
  description: string
  [key: string]: unknown
}

export interface ManualProjectCreationFlow {
  projectType?: string
  projectLocation?: string
}

export interface ManualProjectValues {
  contractorName?: string
  contractorContact?: string
  companyRole?: string
  settlementStatus?: string
  submittedAmount?: number
  paidAmount?: number
  paymentTerms?: string
  plannedStartDate?: string
  plannedEndDate?: string
  description?: string
}

export interface ManualProjectIntakeUiState {
  wizardStep: number
  pdfPage: number
  pdfScale: number
  previewCollapsed: boolean
}

export interface ManualReviewRequest {
  idempotencyKey: string
  fallbackReason: string
  fallbackNote?: string
  values: ContractDraftValues
}

export interface ExternalImportRequest {
  idempotencyKey: string
  fallbackReason: string
  fallbackNote?: string
  markdown: string
}

export interface ProjectIntakeDraft {
  id: string
  ownerUserId: string
  status: 'draft' | 'document_attached' | 'completed' | 'abandoned'
  documentId: string
  documentVersionId: string
  schemaVersion: 'contract.v1'
  values: ContractDraftValues
  projectValues: ManualProjectValues
  uiState: ManualProjectIntakeUiState
  revision: number
  fallbackReason: string
  fallbackNote: string
  completedProjectId: string
  createdAt: string
  updatedAt: string
}

export interface CreateProjectIntakeDraftRequest {
  values: ContractDraftValues
  projectValues?: ManualProjectValues
  uiState?: Partial<ManualProjectIntakeUiState>
  fallbackReason: string
  fallbackNote?: string
  documentId?: string
  documentVersionId?: string
}

export interface SaveProjectIntakeDraftRequest extends Partial<CreateProjectIntakeDraftRequest> {
  expectedRevision: number
  completedProjectId?: string
}

export interface DocumentVersionMetadata {
  id: string
  documentId: string
  name: string
  mimeType: string
  fileSize: number
  uploadedAt: string
  documentType: DocumentType
  alreadyConfirmedProjectId: string | null
}

export interface OriginalPdfRequest {
  url: string
  httpHeaders: Record<string, string>
  direct?: boolean
}

export interface ManualProjectConfirmationRequest {
  idempotencyKey: string
  formTemplateVersion: 'manual-project-wizard.v1'
  draftId: string
  expectedDraftRevision: number
  contractValues: ContractDraftValues
  projectValues: ManualProjectValues
}

export interface ManualProjectConfirmationProject {
  id: string
  projectCode: string
  projectName: string
  contractDate: string
  constructionUnit: string
  contractorName: string
  contractorContact: string
  ownerUnit: string
  companyRole: string
  managerName: string
  projectStatus: string
  settlementStatus: string
  auditStage: string
  contractAmount: number
  submittedAmount: number
  paidAmount: number
  paymentTerms: string
  plannedStartDate: string
  plannedEndDate: string
  description: string
  documentCompletion: number
  missingRequiredCount: number
  settlementBookStatus: string
  firstAuditMaterialStatus: string
  secondAuditMaterialStatus: string
  variationCount: number
  variationAmount: number
  auditProjectId: string
  createdAt: string
  updatedAt: string
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
  sourceKind: 'ocr' | 'external_ai' | 'manual'
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

export interface ManualProjectConfirmationResponse extends ConfirmDocumentReviewResponse {
  project: ManualProjectConfirmationProject
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

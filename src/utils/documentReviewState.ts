import type {
  DocumentReview,
  DocumentType,
  JsonValue,
  RecognitionJob,
  ReviewDecisionInput,
} from '@/types/documentReview'

const POLLING_STATUSES = new Set(['queued', 'running'])
const RETRYABLE_STATUSES = new Set(['failed', 'manual_required'])

const CRITICAL_FIELDS: Readonly<Record<DocumentType, ReadonlySet<string>>> = {
  construction_contract: new Set([
    'project.name',
    'party.owner',
    'party.contractor',
    'contract.amount',
    'contract.signed_date',
    'contract.payment_terms',
  ]),
  completion_acceptance_certificate: new Set([
    'project.name',
    'party.contractor',
    'acceptance.date',
    'acceptance.conclusion',
  ]),
  final_audit_determination: new Set([
    'project.name',
    'party.owner',
    'party.contractor',
    'audit.engineering_determined_amount',
    'audit.final_settlement_amount',
    'audit.determination_date',
  ]),
}

export interface DocumentReviewState {
  recognitionJob: RecognitionJob | null
  review: DocumentReview | null
  pendingDecisions: Readonly<Record<string, ReviewDecisionInput>>
}

export interface DocumentReviewCommands {
  shouldPollRecognition: boolean
  canRetryRecognition: boolean
  requiresManualEntry: boolean
  isReviewImmutable: boolean
  canEditDecisions: boolean
  canSaveDecisions: boolean
  canConfirm: boolean
  individualReviewFieldIds: string[]
  bulkAcceptableFieldIds: string[]
}

export function deriveReviewCommands(state: DocumentReviewState): DocumentReviewCommands {
  const recognitionStatus = state.recognitionJob?.status
  const review = state.review
  const immutable = review?.status === 'confirmed'
  const allowed = new Set(review?.allowedCommands || [])
  const hasPendingDecisions = Object.keys(state.pendingDecisions).length > 0
  const canEditDecisions = Boolean(review && !immutable && allowed.has('save_decisions'))
  const fieldIds = partitionFieldIds(review)

  return {
    shouldPollRecognition: Boolean(recognitionStatus && POLLING_STATUSES.has(recognitionStatus)),
    canRetryRecognition: Boolean(recognitionStatus && RETRYABLE_STATUSES.has(recognitionStatus)),
    requiresManualEntry: recognitionStatus === 'manual_required',
    isReviewImmutable: immutable,
    canEditDecisions,
    canSaveDecisions: canEditDecisions && hasPendingDecisions,
    canConfirm: Boolean(
      review &&
        !immutable &&
        allowed.has('confirm') &&
        review.blockers.length === 0 &&
        !hasPendingDecisions,
    ),
    individualReviewFieldIds: fieldIds.individual,
    bulkAcceptableFieldIds: fieldIds.bulkAcceptable,
  }
}

export function mergeSavedReview(
  state: DocumentReviewState,
  savedReview: DocumentReview,
  submittedDecisions: readonly ReviewDecisionInput[] = [],
): DocumentReviewState {
  if (state.review?.status === 'confirmed') return state
  if (state.review && savedReview.reviewVersion < state.review.reviewVersion) return state

  if (savedReview.status === 'confirmed') {
    return { ...state, review: savedReview, pendingDecisions: {} }
  }

  const pendingDecisions = { ...state.pendingDecisions }
  for (const submitted of submittedDecisions) {
    const pending = pendingDecisions[submitted.fieldId]
    if (pending && sameDecision(pending, submitted)) {
      delete pendingDecisions[submitted.fieldId]
    }
  }
  return { ...state, review: savedReview, pendingDecisions }
}

function partitionFieldIds(review: DocumentReview | null) {
  const individual: string[] = []
  const bulkAcceptable: string[] = []
  if (!review) return { individual, bulkAcceptable }

  const criticalFields = CRITICAL_FIELDS[review.document.type]
  for (const section of review.sections) {
    for (const field of section.fields) {
      if (criticalFields.has(field.semanticKey)) individual.push(field.id)
      else if (field.aiValue !== null) bulkAcceptable.push(field.id)
    }
  }
  return { individual, bulkAcceptable }
}

function sameDecision(left: ReviewDecisionInput, right: ReviewDecisionInput): boolean {
  return (
    left.fieldId === right.fieldId &&
    left.decision === right.decision &&
    (left.reason || '') === (right.reason || '') &&
    sameJson(left.confirmedValue, right.confirmedValue)
  )
}

function sameJson(left: JsonValue | undefined, right: JsonValue | undefined): boolean {
  if (Object.is(left, right)) return true
  if (Array.isArray(left) && Array.isArray(right)) {
    return left.length === right.length && left.every((item, index) => sameJson(item, right[index]))
  }
  if (isJsonObject(left) && isJsonObject(right)) {
    const leftKeys = Object.keys(left)
    const rightKeys = Object.keys(right)
    return (
      leftKeys.length === rightKeys.length &&
      leftKeys.every((key) => key in right && sameJson(left[key], right[key]))
    )
  }
  return false
}

function isJsonObject(value: JsonValue | undefined): value is Record<string, JsonValue> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

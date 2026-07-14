import type {
  ExtractedField,
  ReviewDecisionInput,
  ReviewFieldValue,
} from '@/types/documentReview'

export function buildReviewDecisionInput(
  field: Pick<ExtractedField, 'id' | 'aiValue'>,
  decision: 'accepted' | 'modified',
  modifiedValue: ReviewFieldValue,
): ReviewDecisionInput {
  if (decision === 'accepted') {
    return {
      fieldId: field.id,
      decision,
      confirmedValue: field.aiValue,
    }
  }

  return {
    fieldId: field.id,
    decision,
    confirmedValue: modifiedValue,
    reason: '人工复核修正 OCR 识别值',
  }
}

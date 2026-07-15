import type {
  ExtractedField,
  ReviewDecisionInput,
  ReviewFieldValue,
} from '@/types/documentReview'

export function buildReviewDecisionInput(
  field: Pick<ExtractedField, 'id' | 'aiValue' | 'sourceKind'>,
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
    reason: modificationReason(field.sourceKind),
  }
}

function modificationReason(sourceKind: ExtractedField['sourceKind']) {
  if (sourceKind === 'manual') return '人工核对合同原文后修正手工录入值'
  if (sourceKind === 'external_ai') return '人工核对合同原文后修正外部 AI 建议'
  return '人工复核修正 OCR 识别值'
}

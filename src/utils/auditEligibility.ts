export type AuditStartEligibilityReason = 'already_linked' | 'stage_not_ready' | 'submitted_amount_required'

export type AuditStartCandidate = {
  id: string
  auditProjectId?: string | null
  projectStatus?: string | null
  submittedAmount?: number | string | null
}

export type AuditStartEligibility =
  | { eligible: true; reason: null }
  | { eligible: false; reason: AuditStartEligibilityReason }

const AUDIT_START_STAGES = new Set(['pending_submission', 'first_audit', 'second_audit'])

const AUDIT_START_MESSAGES: Record<AuditStartEligibilityReason, string> = {
  already_linked: '该项目已进入审计流程，请直接查看审计进度。',
  stage_not_ready: '项目未到送审、一审或二审阶段，不能发起审计。',
  submitted_amount_required: '发起审计前必须填写大于 0 的送审金额。',
}

const AUDIT_START_SKIP_LABELS: Record<AuditStartEligibilityReason, string> = {
  already_linked: '已进入审计流程',
  stage_not_ready: '未到送审、一审或二审阶段',
  submitted_amount_required: '送审金额未大于 0',
}

export function getAuditStartEligibility(project: AuditStartCandidate): AuditStartEligibility {
  if (String(project.auditProjectId || '').trim()) return { eligible: false, reason: 'already_linked' }
  if (!AUDIT_START_STAGES.has(String(project.projectStatus || ''))) return { eligible: false, reason: 'stage_not_ready' }
  const submittedAmount = Number(project.submittedAmount || 0)
  if (!Number.isFinite(submittedAmount) || submittedAmount <= 0) return { eligible: false, reason: 'submitted_amount_required' }
  return { eligible: true, reason: null }
}

export function auditStartEligibilityMessage(reason: AuditStartEligibilityReason) {
  return AUDIT_START_MESSAGES[reason]
}

export function partitionAuditStartCandidates<T extends AuditStartCandidate>(projects: T[]) {
  const eligible: T[] = []
  const skipped: Array<{ project: T; reason: AuditStartEligibilityReason }> = []
  for (const project of projects) {
    const eligibility = getAuditStartEligibility(project)
    if (eligibility.eligible) eligible.push(project)
    else skipped.push({ project, reason: eligibility.reason })
  }
  return { eligible, skipped }
}

export function formatAuditStartSkippedSummary(skipped: Array<{ reason: AuditStartEligibilityReason }>) {
  const counts = new Map<AuditStartEligibilityReason, number>()
  for (const { reason } of skipped) counts.set(reason, (counts.get(reason) || 0) + 1)
  return Array.from(counts.entries())
    .map(([reason, count]) => `${AUDIT_START_SKIP_LABELS[reason]} ${count} 个`)
    .join('；')
}

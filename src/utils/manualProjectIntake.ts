import type {
  ContractDraftValues,
  ManualProjectCreationFlow,
  ManualProjectIntakeForm,
  ManualProjectValues,
} from '@/types/documentReview'

const MAX_SAFE_FEN = BigInt(Number.MAX_SAFE_INTEGER)

function requiredText(value: unknown, label: string): string {
  const text = String(value ?? '').trim()
  if (!text) throw new Error(`${label}不能为空。`)
  return text
}

function optionalText(value: unknown): string {
  return String(value ?? '').trim()
}

function exactFen(value: number | string): number {
  if (typeof value === 'number' && !Number.isFinite(value)) {
    throw new Error('合同金额必须是有限数字。')
  }
  if (typeof value !== 'number' && typeof value !== 'string') {
    throw new Error('合同金额格式不正确。')
  }
  const normalized = String(value).trim()
  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(normalized)
  if (!match) throw new Error('合同金额最多保留两位小数。')

  const yuan = BigInt(match[1])
  const fraction = (match[2] || '').padEnd(2, '0')
  const fen = yuan * 100n + BigInt(fraction || '0')
  if (fen <= 0n) throw new Error('合同金额必须大于 0。')
  if (fen > MAX_SAFE_FEN) throw new Error('合同金额超出可安全处理范围。')
  return Number(fen)
}

function nonnegativeAmount(value: unknown, label: string): number {
  const amount = typeof value === 'number' ? value : Number(value ?? 0)
  if (!Number.isFinite(amount) || amount < 0) throw new Error(`${label}必须是非负有限数字。`)
  return amount
}

function appendCreationNotes(
  description: unknown,
  creationFlow: ManualProjectCreationFlow,
): string {
  const projectType = optionalText(creationFlow.projectType)
  const projectLocation = optionalText(creationFlow.projectLocation)
  const notes = [
    projectType ? `项目类型：${projectType}` : '',
    projectLocation ? `项目地点：${projectLocation}` : '',
  ].filter(Boolean)
  return [optionalText(description), notes.join('\n')].filter(Boolean).join('\n')
}

export function buildManualContractValues(form: ManualProjectIntakeForm): ContractDraftValues {
  const paymentTerms = String(form.paymentTerms ?? '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
  if (!paymentTerms.length) throw new Error('付款条款不能为空。')

  return {
    'project.name': requiredText(form.projectName, '项目名称'),
    'party.owner': requiredText(form.ownerUnit, '建设单位'),
    'party.contractor': requiredText(form.constructionUnit, '施工单位'),
    'contract.amount': exactFen(form.contractAmount),
    'contract.signed_date': requiredText(form.contractDate, '合同签订日期'),
    'project.manager': optionalText(form.managerName),
    'contract.start_date': optionalText(form.plannedStartDate),
    'contract.end_date': optionalText(form.plannedEndDate),
    'contract.payment_terms': paymentTerms,
  }
}

export function buildManualProjectValues(
  form: ManualProjectIntakeForm,
  creationFlow: ManualProjectCreationFlow = {},
): ManualProjectValues {
  return {
    contractorName: optionalText(form.contractorName),
    contractorContact: optionalText(form.contractorContact),
    companyRole: optionalText(form.companyRole),
    settlementStatus: optionalText(form.settlementStatus),
    submittedAmount: nonnegativeAmount(form.submittedAmount, '送审金额'),
    paidAmount: nonnegativeAmount(form.paidAmount, '已付款金额'),
    paymentTerms: optionalText(form.paymentTerms),
    plannedStartDate: optionalText(form.plannedStartDate),
    plannedEndDate: optionalText(form.plannedEndDate),
    description: appendCreationNotes(form.description, creationFlow),
  }
}

export function newManualProjectIntakeKey(): string {
  if (typeof globalThis.crypto?.randomUUID === 'function') return globalThis.crypto.randomUUID()
  return `${Date.now().toString(16)}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`
}

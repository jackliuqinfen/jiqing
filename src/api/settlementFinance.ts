import { getAuthToken } from '@/api/system'
import type { ApiResult } from '@/types/audit'

const API_BASE = import.meta.env.VITE_AUDIT_API_BASE || '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken()
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  })
  const payload = (await res.json()) as ApiResult<T>
  if (!res.ok || !payload.success) {
    throw new Error(payload.error || `请求失败: ${res.status}`)
  }
  return payload.data
}

export interface SettlementBossDashboard {
  contractTotalAmount?: number
  auditedTotalAmount?: number
  invoiceTotalAmount?: number
  receivedTotalAmount?: number
  receivableAmount?: number
  overdueReceivableAmount?: number
  retentionAmount?: number
  collectibleAmount?: number
  settlementProjectCount?: number
  riskProjectCount?: number
}

export interface SettlementWorkbenchItem {
  id: string
  projectId?: string
  projectName?: string
  ownerUnit?: string
  currentNode?: string
  amount?: number
  paidAmount?: number
  remainingAmount?: number
  invoiceStatus?: string
  documentStatus?: string
  dueDate?: string
  isOverdue?: boolean
  action?: string
  managerName?: string
}

export interface SettlementProjectLedgerItem {
  id: string
  projectId?: string
  projectCode?: string
  projectName?: string
  ownerUnit?: string
  constructionUnit?: string
  managerName?: string
  contractAmount?: number
  provisionalSum?: number
  estimatedPrice?: number
  variationAmount?: number
  submittedAmount?: number
  firstAuditAmount?: number
  secondAuditAmount?: number
  finalAuditedAmount?: number
  invoiceAmount?: number
  receivedAmount?: number
  receivableAmount?: number
  remainingReceivableAmount?: number
  retentionAmount?: number
  projectStatus?: string
  settlementStatus?: string
  invoiceStatus?: string
  collectionStatus?: string
  nextPaymentNode?: string
  nextAction?: string
  contractName?: string
  contractNo?: string
  provisionalAmount?: number
  estimatedAmount?: number
  ownerSuppliedAmount?: number
  otherDeductionAmount?: number
  paymentBaseAmount?: number
  taxRate?: number
  contractDate?: string
  paymentTerms?: string
  acceptanceStatus?: string
  acceptanceDate?: string
  auditStatus?: string
  firstAuditDate?: string
  secondAuditDate?: string
  finalAuditAmount?: number
  finalAuditDate?: string
  hasInvoice?: boolean
  invoicedAmount?: number
  hasReceived?: boolean
  hasPayment?: boolean
  historicalPaidAmount?: number
  hasRetention?: boolean
  retentionRatio?: number
  warrantyStartDate?: string
  warrantyEndDate?: string
  paymentTemplateId?: string
  documentsMissing?: boolean
  documentNote?: string
  exceptionNote?: string
  isDraft?: boolean
  paymentNodes?: SettlementPaymentNode[]
}

export interface SettlementPaymentNode {
  id?: string
  nodeName: string
  nodeOrder: number
  triggerCondition: string
  baseType: string
  paymentRatio: number
  baseAmount?: number
  calculatedAmount?: number
  isCumulative: boolean
  deductExisting: boolean
  requiredDocuments: string[]
  dueDays: number
  reminderEnabled: boolean
  nodeStatus?: string
}

export type SettlementProjectPayload = Partial<Omit<SettlementProjectLedgerItem, 'id'>> & {
  settlementName?: string
  remark?: string
}

export interface SettlementInvoiceRecord {
  id: string
  invoiceNo?: string
  projectName?: string
  contractName?: string
  paymentNodeName?: string
  issuerName?: string
  receiverName?: string
  invoiceType?: string
  invoiceAmount?: number
  taxRate?: number
  taxAmount?: number
  invoiceDate?: string
  invoiceStatus?: string
  collectionStatus?: string
  remark?: string
}

export interface SettlementPaymentRecord {
  id: string
  projectName?: string
  contractName?: string
  paymentNodeName?: string
  recordType?: '收款' | '付款' | string
  amount?: number
  paymentDate?: string
  counterparty?: string
  operatorName?: string
  remark?: string
}

export interface SettlementRetentionRecord {
  id: string
  projectName?: string
  contractName?: string
  retentionRatio?: number
  retentionAmount?: number
  warrantyStartDate?: string
  warrantyEndDate?: string
  isDue?: boolean
  refundStatus?: string
  refundDate?: string
}

export function fetchSettlementBossDashboard(): Promise<SettlementBossDashboard> {
  return request('/settlement/dashboard/boss')
}

export function fetchSettlementFinanceWorkbench(): Promise<SettlementWorkbenchItem[]> {
  return request('/settlement/workbench/finance')
}

export function fetchSettlementProjects(): Promise<SettlementProjectLedgerItem[]> {
  return request('/settlement/projects')
}

export function createSettlementProject(data: SettlementProjectPayload): Promise<SettlementProjectLedgerItem> {
  return request('/settlement/projects', { method: 'POST', body: JSON.stringify(data) })
}

export function fetchSettlementInvoices(): Promise<SettlementInvoiceRecord[]> {
  return request('/settlement/invoices')
}

export function fetchSettlementPaymentRecords(): Promise<SettlementPaymentRecord[]> {
  return request('/settlement/payment-records')
}

export function fetchSettlementRetentions(): Promise<SettlementRetentionRecord[]> {
  return request('/settlement/retentions')
}

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
  ownerPaidTotalAmount?: number
  bankReceivedTotalAmount?: number
  outstandingAcceptanceAmount?: number
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
  historicalBankReceivedAmount?: number
  historicalAcceptanceAmount?: number
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
  paymentSummary?: SettlementPaymentSummary
}

export interface SettlementPaymentSummary {
  pendingApprovalAmount?: number
  approvedAmount?: number
  ownerPaidAmount?: number
  approvedUnreceivedAmount?: number
  bankReceivedAmount?: number
  outstandingAcceptanceAmount?: number
  dueConfirmationAmount?: number
  refusedAmount?: number
  collectionStatus?: string
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

export type SettlementApprovalStatus = 'DRAFT' | 'SUBMITTED' | 'APPROVED' | 'REJECTED'
export type SettlementReceiptType = 'BANK_TRANSFER' | 'BANK_ACCEPTANCE' | 'COMMERCIAL_ACCEPTANCE'
export type SettlementAcceptanceStatus = 'OUTSTANDING' | 'DUE_PENDING' | 'REDEEMED' | 'DISCOUNTED' | 'ENDORSED' | 'REFUSED_RETURNED'

export interface SettlementPaymentApplication {
  id: string
  settlementId: string
  projectId: string
  projectName?: string
  projectCode?: string
  contractName?: string
  nodeId?: string
  nodeName?: string
  applicationNo?: string
  applicationName?: string
  appliedAmount?: number
  submittedDate?: string
  approvalStatus?: SettlementApprovalStatus
  approvedAmount?: number
  approvalDate?: string
  payerUnit?: string
  attachmentFileId?: string
  attachmentName?: string
  remark?: string
  createdAt?: string
  updatedAt?: string
}

export interface SettlementReceiptAllocation {
  id?: string
  applicationId: string
  applicationName?: string
  allocationAmount: number
}

export interface SettlementReceipt {
  id: string
  settlementId: string
  projectId: string
  projectName?: string
  projectCode?: string
  contractName?: string
  receiptType: SettlementReceiptType
  amount?: number
  receivedDate?: string
  payerName?: string
  receivingEntity?: string
  receivingAccount?: string
  attachmentFileId?: string
  attachmentName?: string
  isDraft?: boolean
  acceptanceStatus?: SettlementAcceptanceStatus
  acceptanceNumber?: string
  acceptorName?: string
  issuerName?: string
  issueDate?: string
  dueDate?: string
  draftMedium?: string
  holderName?: string
  actualBankAmount?: number
  discountFee?: number
  disposedDate?: string
  remark?: string
  allocations?: SettlementReceiptAllocation[]
  createdAt?: string
  updatedAt?: string
}

export type SettlementPaymentApplicationPayload = Partial<SettlementPaymentApplication> & {
  settlementId: string
  applicationName: string
}

export type SettlementReceiptPayload = Partial<SettlementReceipt> & {
  settlementId: string
  receiptType: SettlementReceiptType
  allocations: SettlementReceiptAllocation[]
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

export function fetchSettlementPaymentApplications(): Promise<SettlementPaymentApplication[]> {
  return request('/settlement/payment-applications')
}

export function createSettlementPaymentApplication(
  data: SettlementPaymentApplicationPayload,
): Promise<SettlementPaymentApplication> {
  return request('/settlement/payment-applications', { method: 'POST', body: JSON.stringify(data) })
}

export function updateSettlementPaymentApplicationStatus(
  id: string,
  data: { approvalStatus: Extract<SettlementApprovalStatus, 'APPROVED' | 'REJECTED'>; approvedAmount?: number; approvalDate: string; remark?: string },
): Promise<SettlementPaymentApplication> {
  return request(`/settlement/payment-applications/${id}/status`, { method: 'PUT', body: JSON.stringify(data) })
}

export function fetchSettlementReceipts(): Promise<SettlementReceipt[]> {
  return request('/settlement/receipts')
}

export function createSettlementReceipt(data: SettlementReceiptPayload): Promise<SettlementReceipt> {
  return request('/settlement/receipts', { method: 'POST', body: JSON.stringify(data) })
}

export function updateSettlementAcceptanceStatus(
  id: string,
  data: { acceptanceStatus: SettlementAcceptanceStatus; actualBankAmount?: number; discountFee?: number; disposedDate?: string; remark?: string },
): Promise<{ id: string; acceptanceStatus: SettlementAcceptanceStatus }> {
  return request(`/settlement/receipts/${id}/status`, { method: 'PUT', body: JSON.stringify(data) })
}

export function fetchSettlementRetentions(): Promise<SettlementRetentionRecord[]> {
  return request('/settlement/retentions')
}

<template>
  <section class="payment-flow">
    <header class="payment-flow__head">
      <div>
        <h2>付款申请与款项到账</h2>
        <p>先登记付款申请及甲方审批结果，再登记银行到账或承兑汇票。两类记录分开管理、按申请核销。</p>
      </div>
      <div v-if="canManage" class="payment-flow__actions">
        <button type="button" @click="openApplication">登记付款申请</button>
        <button class="primary" type="button" @click="openReceipt">登记款项到账</button>
      </div>
    </header>

    <div class="summary-grid">
      <article><span>待甲方审批</span><strong>{{ money(summary.pendingApproval) }}</strong></article>
      <article><span>甲方累计审批通过</span><strong>{{ money(summary.approved) }}</strong></article>
      <article><span>甲方累计已付</span><strong>{{ money(summary.ownerPaid) }}</strong></article>
      <article><span>银行实际到账</span><strong>{{ money(summary.bankReceived) }}</strong></article>
      <article class="warning"><span>未兑付承兑汇票</span><strong>{{ money(summary.outstandingAcceptance) }}</strong></article>
      <article :class="{ danger: summary.refused > 0 }"><span>拒付/退票异常</span><strong>{{ money(summary.refused) }}</strong></article>
    </div>

    <div class="flow-section">
      <div class="flow-section__title">
        <div><h3>甲方付款情况</h3><p>待审批只统计已正式提交的申请，草稿不进入金额汇总。</p></div>
        <span>{{ applications.length }} 条</span>
      </div>
      <div class="business-table business-table--application">
        <div class="business-table__head"><span>项目 / 申请</span><span>付款节点</span><span>申请金额</span><span>甲方审批</span><span>已关联到账</span><span>日期</span><span>操作</span></div>
        <div v-for="item in applications" :key="item.id" class="business-table__row">
          <span><strong>{{ item.projectName || '-' }}</strong><small>{{ item.applicationName || item.applicationNo || '-' }}</small></span>
          <span>{{ item.nodeName || '未关联节点' }}</span>
          <span>{{ money(item.appliedAmount) }}</span>
          <span><em class="status" :data-status="item.approvalStatus">{{ approvalLabel(item.approvalStatus) }}</em><small v-if="item.approvalStatus === 'APPROVED'">{{ money(item.approvedAmount) }}</small></span>
          <span>{{ money(receivedForApplication(item.id)) }}</span>
          <span>{{ item.approvalDate || item.submittedDate || '-' }}</span>
          <span class="row-actions"><button v-if="canManage && item.approvalStatus === 'SUBMITTED'" type="button" @click="openApproval(item)">登记审批结果</button><small v-else>-</small></span>
        </div>
        <div v-if="!applications.length" class="business-table__empty">暂无真实付款申请</div>
      </div>
    </div>

    <div class="flow-section">
      <div class="flow-section__title">
        <div><h3>款项到账情况</h3><p>承兑汇票收到后计入甲方已付，兑付前不计入银行实际到账。</p></div>
        <span>{{ receipts.length }} 条</span>
      </div>
      <div class="business-table business-table--receipt">
        <div class="business-table__head"><span>项目</span><span>到账方式</span><span>金额</span><span>资金状态</span><span>凭证</span><span>到账 / 到期日</span><span>操作</span></div>
        <div v-for="item in receipts" :key="item.id" class="business-table__row">
          <span><strong>{{ item.projectName || '-' }}</strong><small>{{ allocationText(item) }}</small></span>
          <span>{{ receiptTypeLabel(item.receiptType) }}<small v-if="item.acceptanceNumber">{{ item.acceptanceNumber }}</small></span>
          <span>{{ money(item.amount) }}</span>
          <span><em class="status" :data-status="item.acceptanceStatus || 'BANK_RECEIVED'">{{ receiptStatusLabel(item) }}</em></span>
          <span>{{ item.attachmentName || '凭证已上传' }}</span>
          <span>{{ item.receivedDate || '-' }}<small v-if="item.dueDate">到期：{{ item.dueDate }}</small></span>
          <span class="row-actions">
            <template v-if="canManage && canProcessAcceptance(item)">
              <button type="button" @click="processAcceptance(item, 'REDEEMED')">确认兑付</button>
              <button class="danger-link" type="button" @click="processAcceptance(item, 'REFUSED_RETURNED')">登记退票</button>
            </template>
            <small v-else>-</small>
          </span>
        </div>
        <div v-if="!receipts.length" class="business-table__empty">暂无真实到账记录</div>
      </div>
    </div>

    <p v-if="message" class="flow-message" :class="messageType">{{ message }}</p>

    <AModal v-model:visible="applicationDialog" title="登记付款申请" width="720px" :footer="false" :mask-closable="false">
      <form class="dialog-form" @submit.prevent="submitApplication">
        <label class="span-2"><span>结算项目 *</span><select v-model="applicationForm.settlementId" required @change="syncApplicationProject"><option value="">请选择已纳入结算管理的项目</option><option v-for="item in formalSettlements" :key="item.id" :value="item.id">{{ item.projectName }} · {{ item.contractName || '施工合同' }}</option></select></label>
        <label><span>付款节点</span><select v-model="applicationForm.nodeId"><option value="">暂不关联节点</option><option v-for="node in selectedSettlement?.paymentNodes || []" :key="node.id" :value="node.id">{{ node.nodeName }}</option></select></label>
        <label><span>申请名称 *</span><input v-model.trim="applicationForm.applicationName" required placeholder="如：竣工验收后第一次付款申请" /></label>
        <label><span>申请编号</span><input v-model.trim="applicationForm.applicationNo" placeholder="可不填" /></label>
        <label><span>申请金额（元） *</span><input v-model.number="applicationForm.appliedAmount" min="0" step="0.01" type="number" required /></label>
        <label><span>提交日期 *</span><input v-model="applicationForm.submittedDate" type="date" required /></label>
        <label><span>甲方审批结果 *</span><select v-model="applicationForm.approvalStatus" required><option value="SUBMITTED">待甲方审批</option><option value="APPROVED">甲方审批通过</option><option value="REJECTED">甲方未通过</option><option value="DRAFT">保存草稿</option></select></label>
        <template v-if="applicationForm.approvalStatus === 'APPROVED'">
          <label><span>审批通过金额（元） *</span><input v-model.number="applicationForm.approvedAmount" min="0" step="0.01" type="number" required /></label>
          <label><span>审批日期 *</span><input v-model="applicationForm.approvalDate" type="date" required /></label>
        </template>
        <label class="span-2"><span>付款单位</span><input v-model.trim="applicationForm.payerUnit" placeholder="默认带出建设单位，可据实修正" /></label>
        <label class="span-2"><span>备注</span><textarea v-model.trim="applicationForm.remark" rows="3" placeholder="可记录审批意见或特殊情况" /></label>
        <footer><button type="button" @click="applicationDialog = false">取消</button><button class="primary" type="submit" :disabled="saving">{{ saving ? '保存中...' : '确认登记' }}</button></footer>
      </form>
    </AModal>

    <AModal v-model:visible="approvalDialog" title="登记甲方审批结果" width="560px" :footer="false" :mask-closable="false">
      <form class="dialog-form" @submit.prevent="submitApproval">
        <label class="span-2"><span>付款申请</span><input :value="approvalTarget?.applicationName || '-'" disabled /></label>
        <label><span>甲方审批结果 *</span><select v-model="approvalForm.approvalStatus" required><option value="APPROVED">甲方审批通过</option><option value="REJECTED">甲方未通过</option></select></label>
        <label><span>审批日期 *</span><input v-model="approvalForm.approvalDate" type="date" required /></label>
        <label v-if="approvalForm.approvalStatus === 'APPROVED'" class="span-2"><span>审批通过金额（元） *</span><input v-model.number="approvalForm.approvedAmount" min="0" :max="approvalTarget?.appliedAmount || undefined" step="0.01" type="number" required /></label>
        <label class="span-2"><span>审批意见/说明</span><textarea v-model.trim="approvalForm.remark" rows="3" /></label>
        <footer><button type="button" @click="approvalDialog = false">取消</button><button class="primary" type="submit" :disabled="saving">{{ saving ? '保存中...' : '确认登记' }}</button></footer>
      </form>
    </AModal>

    <AModal v-model:visible="receiptDialog" title="登记款项到账" width="760px" :footer="false" :mask-closable="false">
      <form class="dialog-form" @submit.prevent="submitReceipt">
        <label class="span-2"><span>结算项目 *</span><select v-model="receiptForm.settlementId" required @change="syncReceiptProject"><option value="">请选择已纳入结算管理的项目</option><option v-for="item in formalSettlements" :key="item.id" :value="item.id">{{ item.projectName }} · {{ item.contractName || '施工合同' }}</option></select></label>
        <label class="span-2"><span>关联已审批付款申请 *</span><select v-model="receiptForm.applicationId" required @change="fillReceiptAmount"><option value="">请选择</option><option v-for="item in approvedApplications" :key="item.id" :value="item.id">{{ item.applicationName }} · 剩余 {{ money(applicationRemaining(item)) }}</option></select></label>
        <label><span>到账方式 *</span><select v-model="receiptForm.receiptType" required><option value="BANK_TRANSFER">银行转账</option><option value="BANK_ACCEPTANCE">银行承兑汇票</option><option value="COMMERCIAL_ACCEPTANCE">商业承兑汇票</option></select></label>
        <label><span>金额（元） *</span><input v-model.number="receiptForm.amount" min="0" step="0.01" type="number" required /></label>
        <label><span>实际收到日期 *</span><input v-model="receiptForm.receivedDate" type="date" required /></label>
        <label><span>付款方 *</span><input v-model.trim="receiptForm.payerName" required /></label>
        <template v-if="receiptForm.receiptType === 'BANK_TRANSFER'">
          <label><span>收款主体 *</span><input v-model.trim="receiptForm.receivingEntity" required /></label>
          <label><span>收款账户 *</span><input v-model.trim="receiptForm.receivingAccount" required /></label>
        </template>
        <template v-else>
          <label><span>汇票号码 *</span><input v-model.trim="receiptForm.acceptanceNumber" required /></label>
          <label><span>承兑人 *</span><input v-model.trim="receiptForm.acceptorName" required /></label>
          <label><span>出票人 *</span><input v-model.trim="receiptForm.issuerName" required /></label>
          <label><span>出票日期 *</span><input v-model="receiptForm.issueDate" type="date" required /></label>
          <label><span>到期日期 *</span><input v-model="receiptForm.dueDate" type="date" required /></label>
          <label><span>汇票介质 *</span><select v-model="receiptForm.draftMedium" required><option value="电子">电子汇票</option><option value="纸质">纸质汇票</option></select></label>
          <label class="span-2"><span>持票主体 *</span><input v-model.trim="receiptForm.holderName" required /></label>
        </template>
        <label class="span-2 file-field"><span>{{ receiptForm.receiptType === 'BANK_TRANSFER' ? '银行回单/到账截图 *' : '电子汇票截图、PDF或纸票扫描件 *' }}</span><input type="file" required accept=".pdf,.png,.jpg,.jpeg,.webp" @change="selectReceiptFile" /><small v-if="uploadProgress">上传进度 {{ uploadProgress }}%</small></label>
        <label class="span-2"><span>备注</span><textarea v-model.trim="receiptForm.remark" rows="3" /></label>
        <footer><button type="button" @click="receiptDialog = false">取消</button><button class="primary" type="submit" :disabled="saving">{{ saving ? '上传并登记中...' : '确认登记' }}</button></footer>
      </form>
    </AModal>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { uploadProjectFile } from '@/api/projects'
import {
  createSettlementPaymentApplication,
  createSettlementReceipt,
  fetchSettlementPaymentApplications,
  fetchSettlementReceipts,
  updateSettlementPaymentApplicationStatus,
  updateSettlementAcceptanceStatus,
  type SettlementAcceptanceStatus,
  type SettlementPaymentApplication,
  type SettlementApprovalStatus,
  type SettlementProjectLedgerItem,
  type SettlementReceipt,
  type SettlementReceiptType,
} from '@/api/settlementFinance'
import { formatWan } from '@/utils/format'

const props = defineProps<{ settlements: SettlementProjectLedgerItem[]; canManage: boolean }>()
const emit = defineEmits<{ saved: [] }>()
const applications = ref<SettlementPaymentApplication[]>([])
const receipts = ref<SettlementReceipt[]>([])
const applicationDialog = ref(false)
const receiptDialog = ref(false)
const approvalDialog = ref(false)
const approvalTarget = ref<SettlementPaymentApplication | null>(null)
const saving = ref(false)
const message = ref('')
const messageType = ref<'success' | 'error'>('success')
const receiptFile = ref<File | null>(null)
const uploadProgress = ref(0)

const applicationForm = reactive({ settlementId: '', nodeId: '', applicationNo: '', applicationName: '', appliedAmount: 0, submittedDate: '', approvalStatus: 'SUBMITTED' as SettlementApprovalStatus, approvedAmount: 0, approvalDate: '', payerUnit: '', remark: '' })
const receiptForm = reactive({ settlementId: '', applicationId: '', receiptType: 'BANK_TRANSFER' as SettlementReceiptType, amount: 0, receivedDate: '', payerName: '', receivingEntity: '', receivingAccount: '', acceptanceNumber: '', acceptorName: '', issuerName: '', issueDate: '', dueDate: '', draftMedium: '电子', holderName: '', remark: '' })
const approvalForm = reactive({ approvalStatus: 'APPROVED' as Extract<SettlementApprovalStatus, 'APPROVED' | 'REJECTED'>, approvedAmount: 0, approvalDate: '', remark: '' })

const formalSettlements = computed(() => props.settlements.filter((item) => !item.isDraft))
const selectedSettlement = computed(() => formalSettlements.value.find((item) => item.id === applicationForm.settlementId))
const selectedReceiptSettlement = computed(() => formalSettlements.value.find((item) => item.id === receiptForm.settlementId))
const approvedApplications = computed(() => applications.value.filter((item) => item.settlementId === receiptForm.settlementId && item.approvalStatus === 'APPROVED' && applicationRemaining(item) > 0))

const summary = computed(() => ({
  pendingApproval: applications.value.filter((item) => item.approvalStatus === 'SUBMITTED').reduce((sum, item) => sum + Number(item.appliedAmount || 0), 0),
  approved: applications.value.filter((item) => item.approvalStatus === 'APPROVED').reduce((sum, item) => sum + Number(item.approvedAmount || 0), 0),
  ownerPaid: props.settlements.reduce((sum, item) => sum + Number(item.paymentSummary?.ownerPaidAmount || 0), 0),
  bankReceived: props.settlements.reduce((sum, item) => sum + Number(item.paymentSummary?.bankReceivedAmount || 0), 0),
  outstandingAcceptance: props.settlements.reduce((sum, item) => sum + Number(item.paymentSummary?.outstandingAcceptanceAmount || 0), 0),
  refused: props.settlements.reduce((sum, item) => sum + Number(item.paymentSummary?.refusedAmount || 0), 0),
}))

function money(value?: number) { return value == null ? '-' : formatWan(Number(value || 0)) }
function approvalLabel(status?: string) { return ({ DRAFT: '草稿', SUBMITTED: '待甲方审批', APPROVED: '甲方审批通过', REJECTED: '甲方未通过' } as Record<string, string>)[status || ''] || status || '-' }
function receiptTypeLabel(type?: string) { return ({ BANK_TRANSFER: '银行转账', BANK_ACCEPTANCE: '银行承兑汇票', COMMERCIAL_ACCEPTANCE: '商业承兑汇票' } as Record<string, string>)[type || ''] || '-' }
function receiptStatusLabel(item: SettlementReceipt) { if (item.receiptType === 'BANK_TRANSFER') return '银行已到账'; return ({ OUTSTANDING: '汇票待兑付', DUE_PENDING: '到期待财务确认', REDEEMED: '已兑付', DISCOUNTED: '已贴现', ENDORSED: '已背书转让', REFUSED_RETURNED: '拒付/退票' } as Record<string, string>)[item.acceptanceStatus || ''] || '-' }
function canProcessAcceptance(item: SettlementReceipt) { return item.receiptType !== 'BANK_TRANSFER' && ['OUTSTANDING', 'DUE_PENDING'].includes(item.acceptanceStatus || '') }
function allocationText(item: SettlementReceipt) { return item.allocations?.map((entry) => entry.applicationName).filter(Boolean).join('、') || '未关联申请' }
function receivedForApplication(id: string) { return receipts.value.filter((item) => !item.isDraft && item.acceptanceStatus !== 'REFUSED_RETURNED').flatMap((item) => item.allocations || []).filter((item) => item.applicationId === id).reduce((sum, item) => sum + Number(item.allocationAmount || 0), 0) }
function applicationRemaining(item: SettlementPaymentApplication) { return Math.max(Number(item.approvedAmount || 0) - receivedForApplication(item.id), 0) }

async function load() {
  try {
    ;[applications.value, receipts.value] = await Promise.all([fetchSettlementPaymentApplications(), fetchSettlementReceipts()])
  } catch (error) {
    messageType.value = 'error'; message.value = error instanceof Error ? error.message : '付款申请与到账记录加载失败'
  }
}
function openApplication() { Object.assign(applicationForm, { settlementId: '', nodeId: '', applicationNo: '', applicationName: '', appliedAmount: 0, submittedDate: new Date().toISOString().slice(0, 10), approvalStatus: 'SUBMITTED', approvedAmount: 0, approvalDate: '', payerUnit: '', remark: '' }); applicationDialog.value = true }
function syncApplicationProject() { applicationForm.nodeId = ''; applicationForm.payerUnit = selectedSettlement.value?.ownerUnit || '' }
async function submitApplication() {
  saving.value = true
  try {
    await createSettlementPaymentApplication({ ...applicationForm })
    applicationDialog.value = false; messageType.value = 'success'; message.value = '付款申请已登记'; await load(); emit('saved')
  } catch (error) { messageType.value = 'error'; message.value = error instanceof Error ? error.message : '付款申请登记失败' } finally { saving.value = false }
}
function openApproval(item: SettlementPaymentApplication) {
  approvalTarget.value = item
  Object.assign(approvalForm, { approvalStatus: 'APPROVED', approvedAmount: Number(item.appliedAmount || 0), approvalDate: new Date().toISOString().slice(0, 10), remark: '' })
  approvalDialog.value = true
}
async function submitApproval() {
  if (!approvalTarget.value) return
  saving.value = true
  try {
    await updateSettlementPaymentApplicationStatus(approvalTarget.value.id, { ...approvalForm, approvedAmount: approvalForm.approvalStatus === 'APPROVED' ? Number(approvalForm.approvedAmount || 0) : 0 })
    approvalDialog.value = false; messageType.value = 'success'; message.value = '甲方审批结果已登记'; await load(); emit('saved')
  } catch (error) { messageType.value = 'error'; message.value = error instanceof Error ? error.message : '甲方审批结果登记失败' } finally { saving.value = false }
}
function openReceipt() { Object.assign(receiptForm, { settlementId: '', applicationId: '', receiptType: 'BANK_TRANSFER', amount: 0, receivedDate: new Date().toISOString().slice(0, 10), payerName: '', receivingEntity: '', receivingAccount: '', acceptanceNumber: '', acceptorName: '', issuerName: '', issueDate: '', dueDate: '', draftMedium: '电子', holderName: '', remark: '' }); receiptFile.value = null; uploadProgress.value = 0; receiptDialog.value = true }
function syncReceiptProject() { receiptForm.applicationId = ''; receiptForm.amount = 0; receiptForm.payerName = selectedReceiptSettlement.value?.ownerUnit || '' }
function fillReceiptAmount() { const item = approvedApplications.value.find((entry) => entry.id === receiptForm.applicationId); receiptForm.amount = item ? applicationRemaining(item) : 0 }
function selectReceiptFile(event: Event) { receiptFile.value = (event.target as HTMLInputElement).files?.[0] || null }
async function submitReceipt() {
  if (!receiptFile.value || !selectedReceiptSettlement.value) { messageType.value = 'error'; message.value = '请先选择项目、付款申请并上传到账凭证'; return }
  saving.value = true
  try {
    const uploaded = await uploadProjectFile(selectedReceiptSettlement.value.projectId || '', { categoryKey: 'payment', displayName: receiptFile.value.name, file: receiptFile.value }, (value) => { uploadProgress.value = value })
    await createSettlementReceipt({ ...receiptForm, attachmentFileId: uploaded.id, allocations: [{ applicationId: receiptForm.applicationId, allocationAmount: Number(receiptForm.amount || 0) }] })
    receiptDialog.value = false; messageType.value = 'success'; message.value = '款项到账已登记并关联付款申请'; await load(); emit('saved')
  } catch (error) { messageType.value = 'error'; message.value = error instanceof Error ? error.message : '款项到账登记失败' } finally { saving.value = false }
}
async function processAcceptance(item: SettlementReceipt, acceptanceStatus: Extract<SettlementAcceptanceStatus, 'REDEEMED' | 'REFUSED_RETURNED'>) {
  const action = acceptanceStatus === 'REDEEMED' ? '确认该承兑汇票已兑付并计入银行实际到账' : '登记该承兑汇票拒付/退票，并冲回甲方累计已付'
  if (!window.confirm(`${action}？该操作会写入项目操作记录。`)) return
  saving.value = true
  try {
    await updateSettlementAcceptanceStatus(item.id, { acceptanceStatus, disposedDate: new Date().toISOString().slice(0, 10) })
    messageType.value = 'success'
    message.value = acceptanceStatus === 'REDEEMED' ? '承兑汇票已确认兑付' : '承兑汇票已登记退票并冲回甲方累计已付'
    await load()
    emit('saved')
  } catch (error) {
    messageType.value = 'error'
    message.value = error instanceof Error ? error.message : '承兑汇票状态更新失败'
  } finally {
    saving.value = false
  }
}

onMounted(load)
defineExpose({ refresh: load })
</script>

<style scoped>
.payment-flow{display:grid;gap:18px}.payment-flow__head,.flow-section__title{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}.payment-flow__head h2,.flow-section h3{margin:0;color:#10264a}.payment-flow__head p,.flow-section__title p{margin:6px 0 0;color:#6f809a;line-height:1.6}.payment-flow__actions{display:flex;gap:8px}.payment-flow button{height:34px;padding:0 14px;border:1px solid #cfd9ea;border-radius:6px;background:#fff;color:#26405f}.payment-flow button.primary{border-color:#165dff;background:#165dff;color:#fff}.summary-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:10px}.summary-grid article{min-height:76px;padding:13px;border:1px solid rgba(111,142,194,.2);border-radius:6px;background:rgba(255,255,255,.78)}.summary-grid span,.summary-grid strong{display:block}.summary-grid span{color:#72829a;font-size:12px}.summary-grid strong{margin-top:10px;color:#10264a;font-size:16px}.summary-grid .warning{border-top:3px solid #f59e0b}.summary-grid .danger{border-top:3px solid #ef4444}.flow-section{overflow:hidden;border:1px solid rgba(111,142,194,.2);border-radius:6px;background:rgba(255,255,255,.82)}.flow-section__title{padding:14px 16px;border-bottom:1px solid #e5ebf4}.flow-section__title p{font-size:12px}.flow-section__title>span{color:#6f809a}.business-table__head,.business-table__row{display:grid;grid-template-columns:1.35fr .9fr .75fr .9fr .85fr .9fr 1.05fr;gap:12px;align-items:center;padding:11px 16px}.business-table__head{background:#f5f8fc;color:#596c88;font-size:12px}.business-table__row{min-height:60px;border-top:1px solid #e8edf5}.business-table__row>span{min-width:0;overflow-wrap:anywhere}.business-table strong,.business-table small{display:block}.business-table small{margin-top:5px;color:#71829b}.business-table__empty{padding:28px;text-align:center;color:#8390a4}.row-actions{display:flex;gap:6px;align-items:center}.row-actions button{height:28px;padding:0 8px;font-size:12px}.row-actions .danger-link{border-color:#f2caca;color:#b42318}.status{display:inline-flex;padding:3px 7px;border-radius:4px;background:#edf3fd;color:#2f5d9d;font-style:normal;font-size:12px}.status[data-status="APPROVED"],.status[data-status="BANK_RECEIVED"],.status[data-status="REDEEMED"]{background:#eaf8f3;color:#087a60}.status[data-status="COMMERCIAL_ACCEPTANCE"],.status[data-status="OUTSTANDING"],.status[data-status="DUE_PENDING"]{background:#fff5df;color:#9c6200}.status[data-status="REJECTED"],.status[data-status="REFUSED_RETURNED"]{background:#fff0f0;color:#b42318}.flow-message{padding:10px 12px;border-radius:6px;background:#eaf8f3;color:#087a60}.flow-message.error{background:#fff0f0;color:#b42318}.dialog-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px 16px}.dialog-form label{display:grid;gap:7px;color:#536680;font-size:12px}.dialog-form .span-2{grid-column:1/-1}.dialog-form input,.dialog-form select,.dialog-form textarea{width:100%;min-height:36px;padding:8px 10px;border:1px solid #d5dfed;border-radius:6px;background:#fff;color:#172b4d;box-sizing:border-box}.dialog-form textarea{resize:vertical}.dialog-form .file-field{padding:12px;border:1px dashed #b9c8df;border-radius:6px;background:#f8faff}.dialog-form footer{grid-column:1/-1;display:flex;justify-content:flex-end;gap:8px;padding-top:8px}.dialog-form button:disabled{opacity:.55}@media(max-width:1050px){.summary-grid{grid-template-columns:repeat(3,1fr)}}@media(max-width:760px){.payment-flow__head,.flow-section__title{display:grid}.summary-grid,.dialog-form{grid-template-columns:1fr}.dialog-form .span-2{grid-column:auto}.business-table{overflow:auto}.business-table__head,.business-table__row{min-width:980px}.payment-flow__actions{flex-wrap:wrap}}
</style>

<template>
  <AModal
    :visible="visible"
    title="纳入结算管理"
    width="1080px"
    :mask-closable="false"
    :footer="false"
    @update:visible="emit('update:visible', $event)"
  >
    <div class="settlement-wizard">
      <nav class="wizard-steps" aria-label="纳入结算管理步骤">
        <button
          v-for="(step, index) in steps"
          :key="step.key"
          type="button"
          :class="{ active: stepIndex === index, done: stepIndex > index }"
          :disabled="index > maxReachedStep"
          @click="goToStep(index)"
        >
          <span>{{ index + 1 }}</span>
          <strong>{{ step.label }}</strong>
        </button>
      </nav>

      <AForm :model="form" layout="vertical" class="wizard-body">
        <section v-if="stepKey === 'project'" class="wizard-pane">
          <header class="pane-head">
            <div><span>第 1 步</span><h3>选择项目</h3></div>
            <p>请选择项目管理中的真实项目。系统自动带出基础信息、合同金额和已有状态，避免重复建档。</p>
          </header>
          <AFormItem field="projectId" label="项目名称" required>
            <ASelect v-model="form.projectId" :options="projectOptions" allow-search placeholder="搜索项目名称或编号" />
          </AFormItem>
          <p v-if="selectedRecord && !selectedRecord.isDraft" class="wizard-alert danger">该项目已纳入结算管理，不能重复生成。</p>
          <p v-else-if="selectedRecord?.isDraft" class="wizard-alert">已读取该项目此前保存的草稿，可以继续完善。</p>
          <p v-else-if="selectedProject && !selectedProject.contractAmount" class="wizard-alert danger">当前项目缺少合同金额，请先在项目管理中补充合同信息。</p>
          <div class="fact-grid">
            <article v-for="item in projectFacts" :key="item.label"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></article>
          </div>
        </section>

        <section v-else-if="stepKey === 'contract'" class="wizard-pane">
          <header class="pane-head">
            <div><span>第 2 步</span><h3>确认合同信息</h3></div>
            <p>合同付款基数由系统实时计算；项目主档案未维护的字段才需要补充。</p>
          </header>
          <div class="form-grid">
            <AFormItem field="contractName" label="合同名称" required><AInput v-model="form.contractName" placeholder="请输入真实合同名称" /></AFormItem>
            <AFormItem field="contractNo" label="合同编号"><AInput v-model="form.contractNo" placeholder="未维护可暂不填写" /></AFormItem>
            <AFormItem field="contractAmount" label="合同金额（元）" required><AInputNumber v-model="form.contractAmount" :min="0" :precision="2" hide-button /></AFormItem>
            <AFormItem field="provisionalAmount" label="暂列金额（元）"><AInputNumber v-model="form.provisionalAmount" :min="0" :precision="2" hide-button /></AFormItem>
            <AFormItem field="estimatedAmount" label="专业工程暂估价（元）"><AInputNumber v-model="form.estimatedAmount" :min="0" :precision="2" hide-button /></AFormItem>
            <AFormItem field="ownerSuppliedAmount" label="甲供材料/设备金额（元）"><AInputNumber v-model="form.ownerSuppliedAmount" :min="0" :precision="2" hide-button /></AFormItem>
            <AFormItem field="otherDeductionAmount" label="其他扣除项（元）"><AInputNumber v-model="form.otherDeductionAmount" :min="0" :precision="2" hide-button /></AFormItem>
            <AFormItem field="taxRate" label="税率"><ASelect v-model="form.taxRate" :options="taxRateOptions" allow-clear placeholder="请选择税率" /></AFormItem>
            <AFormItem field="contractDate" label="合同签订日期"><ADatePicker v-model="form.contractDate" allow-clear placeholder="请选择日期" /></AFormItem>
            <AFormItem class="span-2" field="paymentTerms" label="付款条款原文" required>
              <ATextarea v-model="form.paymentTerms" :auto-size="{ minRows: 3, maxRows: 6 }" placeholder="请录入合同中的真实付款条款" />
            </AFormItem>
          </div>
          <div class="money-result"><span>付款基数</span><strong>{{ moneyTriplet(paymentBaseAmount) }}</strong><small>合同金额 - 暂列金额 - 暂估价 - 甲供金额 - 其他扣除项</small></div>
          <p class="source-note">合同及审计附件复用资料中心中的项目文件，不在结算台账重复上传。</p>
        </section>

        <section v-else-if="stepKey === 'stage'" class="wizard-pane">
          <header class="pane-head">
            <div><span>第 3 步</span><h3>设置结算状态</h3></div>
            <p>通过业务问答判断当前阶段，系统自动生成结算状态。</p>
          </header>
          <h4>项目是否竣工验收？</h4>
          <div class="choice-grid choice-grid--three">
            <button v-for="item in acceptanceOptions" :key="item.value" type="button" :class="{ active: form.acceptanceStatus === item.value }" @click="selectAcceptanceStatus(item.value)">
              <strong>{{ item.label }}</strong><span>{{ item.hint }}</span>
            </button>
          </div>
          <div v-if="form.acceptanceStatus === 'accepted'" class="form-grid compact">
            <AFormItem field="acceptanceDate" label="竣工验收日期" required><ADatePicker v-model="form.acceptanceDate" allow-clear placeholder="请选择日期" /></AFormItem>
          </div>
          <template v-if="canEnterAudit">
            <h4>项目是否已经送审？</h4>
            <div class="choice-grid choice-grid--four">
              <button v-for="item in auditOptions" :key="item.value" type="button" :class="{ active: form.auditStatus === item.value }" @click="form.auditStatus = item.value"><strong>{{ item.label }}</strong></button>
            </div>
            <div class="form-grid">
              <AFormItem v-if="auditRank >= 1" field="submittedAmount" label="送审金额（元）"><AInputNumber v-model="form.submittedAmount" :min="0" :precision="2" hide-button /></AFormItem>
              <AFormItem v-if="auditRank >= 3" field="firstAuditAmount" label="一审审定金额（元）"><AInputNumber v-model="form.firstAuditAmount" :min="0" :precision="2" hide-button /></AFormItem>
              <AFormItem v-if="auditRank >= 3" field="firstAuditDate" label="一审完成日期"><ADatePicker v-model="form.firstAuditDate" allow-clear placeholder="请选择日期" /></AFormItem>
              <AFormItem v-if="auditRank >= 5" field="secondAuditAmount" label="二审审定金额（元）"><AInputNumber v-model="form.secondAuditAmount" :min="0" :precision="2" hide-button /></AFormItem>
              <AFormItem v-if="auditRank >= 5" field="secondAuditDate" label="二审完成日期"><ADatePicker v-model="form.secondAuditDate" allow-clear placeholder="请选择日期" /></AFormItem>
              <AFormItem v-if="auditRank >= 7" field="finalAuditAmount" label="最终审定金额（元）"><AInputNumber v-model="form.finalAuditAmount" :min="0" :precision="2" hide-button /></AFormItem>
              <AFormItem v-if="auditRank >= 7" field="finalAuditDate" label="定案日期"><ADatePicker v-model="form.finalAuditDate" allow-clear placeholder="请选择日期" /></AFormItem>
              <AFormItem v-if="auditRank >= 7" field="retentionRatio" label="质保金比例（%）"><AInputNumber v-model="form.retentionRatio" :min="0" :max="100" :precision="2" hide-button /></AFormItem>
              <AFormItem v-if="auditRank >= 7" field="warrantyStartDate" label="质保期开始日期"><ADatePicker v-model="form.warrantyStartDate" allow-clear placeholder="请选择日期" /></AFormItem>
              <AFormItem v-if="auditRank >= 7" field="warrantyEndDate" label="质保期结束日期"><ADatePicker v-model="form.warrantyEndDate" allow-clear placeholder="请选择日期" /></AFormItem>
            </div>
          </template>
          <div v-else-if="form.acceptanceStatus" class="stage-gate" role="status">
            <strong>{{ auditGateText }}</strong>
            <span>竣工验收合格后，系统才会开放送审及审计阶段信息。</span>
          </div>
          <div class="status-result"><span>系统结算状态</span><strong>{{ generatedStatus }}</strong></div>
        </section>

        <section v-else-if="stepKey === 'history'" class="wizard-pane">
          <header class="pane-head">
            <div><span>第 4 步</span><h3>录入历史财务数据</h3></div>
            <p>系统不会猜测历史财务数据。老项目请据实录入，新项目可全部选择“否”。</p>
          </header>
          <div class="history-grid">
            <HistoryQuestion label="是否已有开票" hint="发票累计金额" :active="form.hasInvoice" amount-label="已开票金额（元）" :amount="form.invoicedAmount" @toggle="form.hasInvoice = $event" @amount="form.invoicedAmount = $event" />
            <HistoryQuestion label="是否已有收款" hint="银行到账累计金额" :active="form.hasReceived" amount-label="已收款金额（元）" :amount="form.receivedAmount" @toggle="form.hasReceived = $event" @amount="form.receivedAmount = $event" />
            <HistoryQuestion label="是否已有付款" hint="项目主档案显示的已付款需再次确认" :active="form.hasPayment" amount-label="已付款金额（元）" :amount="form.historicalPaidAmount" @toggle="form.hasPayment = $event" @amount="form.historicalPaidAmount = $event" />
            <HistoryQuestion label="是否已有质保金扣留" hint="已实际扣留的质保金" :active="form.hasRetention" amount-label="已扣质保金（元）" :amount="form.retentionAmount" @toggle="form.hasRetention = $event" @amount="form.retentionAmount = $event" />
          </div>
          <AFormItem v-if="needsExceptionNote" field="exceptionNote" label="特殊情况说明" required><ATextarea v-model="form.exceptionNote" :auto-size="{ minRows: 2, maxRows: 4 }" placeholder="已收款大于已开票时必须说明真实原因" /></AFormItem>
        </section>

        <section v-else-if="stepKey === 'nodes'" class="wizard-pane">
          <header class="pane-head">
            <div><span>第 5 步</span><h3>生成付款节点</h3></div>
            <p>模板只提供计算规则，所有节点都可复核；自定义模板可逐项增删。</p>
          </header>
          <div class="template-grid">
            <button v-for="item in paymentTemplates" :key="item.id" type="button" :class="{ active: form.paymentTemplateId === item.id }" @click="applyTemplate(item.id)"><strong>{{ item.label }}</strong><span>{{ item.description }}</span></button>
          </div>
          <div class="node-editor">
            <article v-for="(node, index) in form.paymentNodes" :key="`${node.nodeOrder}-${index}`">
              <header><strong>{{ index + 1 }}. {{ node.nodeName || '未命名节点' }}</strong><button v-if="form.paymentTemplateId === 'CUSTOM'" type="button" @click="removeNode(index)">删除</button></header>
              <div class="form-grid">
                <AFormItem label="节点名称"><AInput v-model="node.nodeName" /></AFormItem>
                <AFormItem label="触发条件"><ASelect v-model="node.triggerCondition" :options="triggerOptions" /></AFormItem>
                <AFormItem label="付款基数"><ASelect v-model="node.baseType" :options="baseTypeOptions" /></AFormItem>
                <AFormItem label="付款比例（%）"><AInputNumber :model-value="node.paymentRatio * 100" :min="0" :max="100" :precision="2" hide-button @change="value => updateRatio(node, value)" /></AFormItem>
              </div>
              <div class="calculation-strip"><span>基数 {{ money(calculatedNodes[index]?.baseAmount) }}</span><span>节点金额 {{ money(calculatedNodes[index]?.calculatedAmount) }}</span><strong>当前可收 {{ money(calculatedNodes[index]?.currentReceivable) }}</strong></div>
            </article>
          </div>
          <button v-if="form.paymentTemplateId === 'CUSTOM'" class="add-node" type="button" @click="addNode">+ 添加付款节点</button>
          <div class="document-row"><ACheckbox v-model="form.documentsMissing">当前资料存在缺失，生成“待补资料”待办</ACheckbox><AInput v-if="form.documentsMissing" v-model="form.documentNote" placeholder="请说明缺少哪些真实资料" /></div>
        </section>

        <section v-else class="wizard-pane">
          <header class="pane-head"><div><span>第 6 步</span><h3>确认生成</h3></div><p>确认后将写入真实结算台账、付款节点、资料缺口待办和操作日志。</p></header>
          <div class="review-grid"><article v-for="item in reviewItems" :key="item.label"><span>{{ item.label }}</span><strong>{{ item.value }}</strong></article></div>
          <div class="review-table"><div><strong>付款节点</strong><strong>比例</strong><strong>系统计算金额</strong><strong>预计状态</strong></div><div v-for="node in calculatedNodes" :key="node.nodeName"><span>{{ node.nodeName }}</span><span>{{ percent(node.paymentRatio) }}</span><span>{{ money(node.calculatedAmount) }}</span><span>{{ node.previewStatus }}</span></div></div>
          <AFormItem field="remark" label="备注"><ATextarea v-model="form.remark" :auto-size="{ minRows: 2, maxRows: 4 }" placeholder="可填写真实补充说明" /></AFormItem>
        </section>
      </AForm>

      <p v-if="message" class="wizard-message" :class="messageType">{{ message }}</p>
      <footer class="wizard-footer">
        <button type="button" @click="close">取消</button>
        <button type="button" :disabled="!form.projectId || saving" @click="saveDraft">保存草稿</button>
        <span />
        <button type="button" :disabled="stepIndex === 0" @click="stepIndex -= 1">上一步</button>
        <button v-if="stepKey !== 'review'" class="primary" type="button" @click="next">下一步</button>
        <button v-else class="primary" type="button" :disabled="saving" @click="confirm">确认生成</button>
      </footer>
    </div>
  </AModal>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, reactive, ref, watch } from 'vue'
import { createSettlementProject, type SettlementPaymentNode, type SettlementProjectLedgerItem, type SettlementProjectPayload } from '@/api/settlementFinance'
import type { ProjectRecord } from '@/types'
import { amountToChineseUpper, formatWan } from '@/utils/format'

const props = defineProps<{ visible: boolean; projects: ProjectRecord[]; settlements: SettlementProjectLedgerItem[] }>()
const emit = defineEmits<{ (event: 'update:visible', value: boolean): void; (event: 'saved'): void }>()

type StepKey = 'project' | 'contract' | 'stage' | 'history' | 'nodes' | 'review'
type WizardForm = Omit<SettlementProjectPayload, 'projectId'> & {
  projectId: string
  acceptanceStatus: string
  auditStatus: string
  hasInvoice: boolean
  hasReceived: boolean
  hasPayment: boolean
  hasRetention: boolean
  paymentNodes: SettlementPaymentNode[]
}

const steps: { key: StepKey; label: string }[] = [
  { key: 'project', label: '选择项目' }, { key: 'contract', label: '合同信息' }, { key: 'stage', label: '结算状态' },
  { key: 'history', label: '历史财务' }, { key: 'nodes', label: '付款节点' }, { key: 'review', label: '确认生成' },
]
const acceptanceOptions = [
  { label: '未竣工', value: 'not_completed', hint: '项目仍在施工或尚未完成' },
  { label: '已竣工，未验收', value: 'completed_not_accepted', hint: '等待竣工验收' },
  { label: '已竣工并验收合格', value: 'accepted', hint: '可进入资料准备或送审' },
]
const auditOptions = [
  { label: '未送审', value: 'not_submitted', rank: 0 }, { label: '已送审', value: 'submitted', rank: 1 },
  { label: '一审中', value: 'first_in_progress', rank: 2 }, { label: '一审完成', value: 'first_completed', rank: 3 },
  { label: '二审中', value: 'second_in_progress', rank: 4 }, { label: '二审完成', value: 'second_completed', rank: 5 },
  { label: '政府审计中', value: 'government_audit', rank: 6 }, { label: '最终定案', value: 'final', rank: 7 },
]
const taxRateOptions = [3, 6, 9, 13].map((value) => ({ label: `${value}%`, value }))
const triggerOptions = [
  { label: '竣工验收完成', value: 'ACCEPTANCE_COMPLETED' }, { label: '一审完成', value: 'FIRST_AUDIT_COMPLETED' },
  { label: '二审完成', value: 'SECOND_AUDIT_COMPLETED' }, { label: '最终定案', value: 'FINAL_AUDIT_COMPLETED' },
  { label: '质保期满', value: 'WARRANTY_EXPIRED' },
]
const baseTypeOptions = [
  { label: '合同付款基数', value: 'CONTRACT_PAYMENT_BASE' }, { label: '一审审定金额', value: 'FIRST_AUDIT_AMOUNT' },
  { label: '二审审定金额', value: 'SECOND_AUDIT_AMOUNT' }, { label: '最终审定金额', value: 'FINAL_AUDIT_AMOUNT' },
]

function node(nodeName: string, triggerCondition: string, baseType: string, paymentRatio: number, isCumulative = true, requiredDocuments: string[] = []): SettlementPaymentNode {
  return { nodeName, nodeOrder: 0, triggerCondition, baseType, paymentRatio, isCumulative, deductExisting: true, requiredDocuments, dueDays: 30, reminderEnabled: true }
}
const paymentTemplates = [
  { id: 'TEMPLATE_60_70_97', label: '模板 A', description: '验收 60% + 一审 70% + 二审/定案 97% + 质保金', nodes: () => [
    node('竣工验收后付款', 'ACCEPTANCE_COMPLETED', 'CONTRACT_PAYMENT_BASE', 0.6, true, ['合同', '竣工验收证明', '付款申请单', '发票']),
    node('一审完成后付款', 'FIRST_AUDIT_COMPLETED', 'FIRST_AUDIT_AMOUNT', 0.7, true, ['一审报告', '付款申请单', '发票']),
    node('二审或定案后付款', 'SECOND_AUDIT_COMPLETED', 'FINAL_AUDIT_AMOUNT', 0.97, true, ['二审报告或定案单', '付款申请单', '发票']),
    node('质保金退还', 'WARRANTY_EXPIRED', 'FINAL_AUDIT_AMOUNT', 0.03, false, ['质保期满证明', '付款申请单']),
  ] },
  { id: 'TEMPLATE_30_40_60_85', label: '模板 B', description: '30% + 40% + 60% + 85% + 余款', nodes: () => [
    node('验收后支付至 30%', 'ACCEPTANCE_COMPLETED', 'CONTRACT_PAYMENT_BASE', 0.3), node('一审后支付至 40%', 'FIRST_AUDIT_COMPLETED', 'FIRST_AUDIT_AMOUNT', 0.4),
    node('二审后支付至 60%', 'SECOND_AUDIT_COMPLETED', 'SECOND_AUDIT_AMOUNT', 0.6), node('定案后支付至 85%', 'FINAL_AUDIT_COMPLETED', 'FINAL_AUDIT_AMOUNT', 0.85),
    node('质保期满支付余款', 'WARRANTY_EXPIRED', 'FINAL_AUDIT_AMOUNT', 0.15, false),
  ] },
  { id: 'TEMPLATE_50_60_70', label: '模板 C', description: '50% + 60% + 70% + 质保金', nodes: () => [
    node('验收后支付至 50%', 'ACCEPTANCE_COMPLETED', 'CONTRACT_PAYMENT_BASE', 0.5), node('一审后支付至 60%', 'FIRST_AUDIT_COMPLETED', 'FIRST_AUDIT_AMOUNT', 0.6),
    node('定案后支付至 70%', 'FINAL_AUDIT_COMPLETED', 'FINAL_AUDIT_AMOUNT', 0.7), node('质保期满支付余款', 'WARRANTY_EXPIRED', 'FINAL_AUDIT_AMOUNT', 0.3, false),
  ] },
  { id: 'CUSTOM', label: '模板 D', description: '自定义付款节点', nodes: () => [node('', 'ACCEPTANCE_COMPLETED', 'CONTRACT_PAYMENT_BASE', 0)] },
]

const form = reactive<WizardForm>(emptyForm())
const stepIndex = ref(0)
const maxReachedStep = ref(0)
const saving = ref(false)
const message = ref('')
const messageType = ref<'info' | 'error' | 'success'>('info')
const stepKey = computed(() => steps[stepIndex.value]?.key || 'project')
const selectedProject = computed(() => props.projects.find((item) => item.id === form.projectId) || null)
const selectedRecord = computed(() => props.settlements.find((item) => item.projectId === form.projectId) || null)
const projectOptions = computed(() => props.projects.map((item) => ({ label: `${item.projectName}${item.projectCode ? ` · ${item.projectCode}` : ''}`, value: item.id })))
const projectFacts = computed(() => {
  const item = selectedProject.value
  return [
    { label: '项目编号', value: item?.projectCode || '-' }, { label: '建设单位', value: item?.ownerUnit || '-' },
    { label: '施工单位', value: item?.constructionUnit || '-' }, { label: '项目负责人', value: item?.managerName || '-' },
    { label: '项目状态', value: item?.projectStatusText || item?.projectStatus || '-' }, { label: '合同状态', value: item?.contractAmount ? '已维护合同金额' : '缺少合同信息' },
  ]
})
const paymentBaseAmount = computed(() => Number(form.contractAmount || 0) - Number(form.provisionalAmount || 0) - Number(form.estimatedAmount || 0) - Number(form.ownerSuppliedAmount || 0) - Number(form.otherDeductionAmount || 0))
const canEnterAudit = computed(() => form.acceptanceStatus === 'accepted')
const auditRank = computed(() => canEnterAudit.value ? (auditOptions.find((item) => item.value === form.auditStatus)?.rank || 0) : 0)
const auditGateText = computed(() => form.acceptanceStatus === 'completed_not_accepted' ? '项目尚未通过竣工验收，当前不能报审。' : '项目尚未竣工，当前不能报审。')
const generatedStatus = computed(() => {
  if (form.acceptanceStatus === 'not_completed') return '未进入结算'
  if (form.acceptanceStatus === 'completed_not_accepted') return '待验收'
  const map: Record<string, string> = { not_submitted: '资料准备中', submitted: '已送审', first_in_progress: '一审中', first_completed: '一审完成', second_in_progress: '二审中', second_completed: '二审完成', government_audit: '政府审计中', final: '最终定案' }
  return map[form.auditStatus] || '资料准备中'
})
const needsExceptionNote = computed(() => Boolean(form.hasReceived && Number(form.receivedAmount || 0) > Number(form.invoicedAmount || 0)))
const calculatedNodes = computed(() => {
  let cumulative = 0
  let receivedRemaining = Number(form.receivedAmount || 0)
  return form.paymentNodes.map((item, index) => {
    const bases: Record<string, number> = { CONTRACT_PAYMENT_BASE: paymentBaseAmount.value, FIRST_AUDIT_AMOUNT: Number(form.firstAuditAmount || 0), SECOND_AUDIT_AMOUNT: Number(form.secondAuditAmount || 0), FINAL_AUDIT_AMOUNT: Number(form.finalAuditAmount || 0) }
    const baseAmount = bases[item.baseType] ?? paymentBaseAmount.value
    const target = Math.max(baseAmount * Number(item.paymentRatio || 0), 0)
    const calculatedAmount = item.isCumulative ? Math.max(target - cumulative, 0) : target
    if (item.isCumulative) cumulative += calculatedAmount
    const deducted = item.deductExisting ? Math.min(receivedRemaining, calculatedAmount) : 0
    receivedRemaining -= deducted
    return { ...item, nodeOrder: index + 1, baseAmount, calculatedAmount, currentReceivable: Math.max(calculatedAmount - deducted, 0), previewStatus: previewNodeStatus(item.triggerCondition, calculatedAmount) }
  })
})
const reviewItems = computed(() => [
  { label: '项目名称', value: selectedProject.value?.projectName || '-' }, { label: '项目编号', value: selectedProject.value?.projectCode || '-' },
  { label: '建设单位', value: selectedProject.value?.ownerUnit || '-' }, { label: '施工单位', value: selectedProject.value?.constructionUnit || '-' },
  { label: '合同金额', value: moneyTriplet(Number(form.contractAmount || 0)) }, { label: '付款基数', value: moneyTriplet(paymentBaseAmount.value) },
  { label: '结算状态', value: generatedStatus.value }, { label: '已开票金额', value: money(Number(form.invoicedAmount || 0)) },
  { label: '已收款金额', value: money(Number(form.receivedAmount || 0)) }, { label: '资料状态', value: form.documentsMissing ? `缺失：${form.documentNote || '待补充说明'}` : '未标记缺失' },
])

function emptyForm(): WizardForm {
  return { projectId: '', contractName: '', contractNo: '', contractAmount: undefined, provisionalAmount: 0, estimatedAmount: 0, ownerSuppliedAmount: 0, otherDeductionAmount: 0, taxRate: undefined, contractDate: '', paymentTerms: '', acceptanceStatus: '', acceptanceDate: '', auditStatus: 'not_submitted', submittedAmount: undefined, firstAuditAmount: undefined, firstAuditDate: '', secondAuditAmount: undefined, secondAuditDate: '', finalAuditAmount: undefined, finalAuditDate: '', hasInvoice: false, invoicedAmount: 0, hasReceived: false, receivedAmount: 0, hasPayment: false, historicalPaidAmount: 0, hasRetention: false, retentionRatio: 0, retentionAmount: 0, warrantyStartDate: '', warrantyEndDate: '', paymentTemplateId: '', paymentNodes: [], documentsMissing: false, documentNote: '', exceptionNote: '', settlementStatus: '', settlementName: '', remark: '', isDraft: false }
}

watch(() => props.visible, (visible) => { if (visible) reset() })
watch(() => form.projectId, (projectId) => { if (projectId) hydrateProject() })
watch(() => form.acceptanceStatus, (status) => { if (status !== 'accepted') clearAuditProgress() })
watch(() => form.auditStatus, () => clearAuditFieldsAboveRank(auditRank.value))

function reset() { Object.assign(form, emptyForm()); form.paymentNodes = []; stepIndex.value = 0; maxReachedStep.value = 0; message.value = '' }
function selectAcceptanceStatus(status: string) { form.acceptanceStatus = status; message.value = '' }
function clearAuditProgress() {
  form.acceptanceDate = ''
  form.auditStatus = 'not_submitted'
  form.submittedAmount = undefined
  form.firstAuditAmount = undefined
  form.firstAuditDate = ''
  form.secondAuditAmount = undefined
  form.secondAuditDate = ''
  form.finalAuditAmount = undefined
  form.finalAuditDate = ''
  form.retentionRatio = 0
  form.warrantyStartDate = ''
  form.warrantyEndDate = ''
}
function clearAuditFieldsAboveRank(rank: number) {
  if (rank < 1) form.submittedAmount = undefined
  if (rank < 3) { form.firstAuditAmount = undefined; form.firstAuditDate = '' }
  if (rank < 5) { form.secondAuditAmount = undefined; form.secondAuditDate = '' }
  if (rank < 7) { form.finalAuditAmount = undefined; form.finalAuditDate = ''; form.retentionRatio = 0; form.warrantyStartDate = ''; form.warrantyEndDate = '' }
}
function hydrateProject() {
  const project = selectedProject.value
  const draft = selectedRecord.value?.isDraft ? selectedRecord.value : null
  if (draft) {
    Object.assign(form, draft, { projectId: project?.id || draft.projectId || '', paymentNodes: (draft.paymentNodes || []).map((item) => ({ ...item })) })
    return
  }
  if (!project) return
  form.contractAmount = project.contractAmount || undefined
  form.contractDate = project.contractDate || ''
  form.paymentTerms = project.paymentTerms || ''
  form.submittedAmount = project.submittedAmount || undefined
  form.hasPayment = Number(project.paidAmount || 0) > 0
  form.historicalPaidAmount = Number(project.paidAmount || 0)
  const stage = project.auditStage || project.projectStatus
  const auditMap: Record<string, string> = { submitted: 'submitted', pending_submission: 'not_submitted', first_audit: 'first_in_progress', second_audit: 'second_in_progress', conclusion: 'final', archived: 'final' }
  form.auditStatus = auditMap[stage] || 'not_submitted'
  form.acceptanceStatus = ['completed_acceptance', 'pending_submission', 'first_audit', 'second_audit', 'conclusion', 'archived'].includes(project.projectStatus) ? 'accepted' : 'not_completed'
}
function goToStep(index: number) { if (index <= maxReachedStep.value) stepIndex.value = index }
function showError(text: string) { messageType.value = 'error'; message.value = text }
function validateCurrentStep() {
  if (stepKey.value === 'project') {
    if (!form.projectId) return showError('请先选择项目管理中的项目。'), false
    if (selectedRecord.value && !selectedRecord.value.isDraft) return showError('该项目已纳入结算管理，不能重复生成。'), false
    if (!selectedProject.value?.contractAmount) return showError('当前项目缺少合同金额，请先补充合同。'), false
  }
  if (stepKey.value === 'contract') {
    if (!String(form.contractName || '').trim()) return showError('请填写真实合同名称。'), false
    if (Number(form.contractAmount || 0) <= 0) return showError('合同金额必须大于 0。'), false
    if (paymentBaseAmount.value < 0) return showError('付款基数不能小于 0，请核对扣除项。'), false
    if (!String(form.paymentTerms || '').trim()) return showError('请录入合同付款条款原文。'), false
  }
  if (stepKey.value === 'stage') {
    if (!form.acceptanceStatus) return showError('请确认竣工验收状态。'), false
    if (form.acceptanceStatus === 'accepted' && !form.acceptanceDate) return showError('请选择竣工验收日期。'), false
    if (!canEnterAudit.value && form.auditStatus !== 'not_submitted') return showError('项目竣工验收合格后才能进入送审流程。'), false
    if (auditRank.value >= 1 && Number(form.submittedAmount || 0) <= 0) return showError('项目进入送审后必须填写送审金额。'), false
    if (auditRank.value >= 3 && Number(form.firstAuditAmount || 0) <= 0) return showError('一审完成时必须填写一审审定金额。'), false
    if (auditRank.value >= 3 && !form.firstAuditDate) return showError('一审完成时必须填写一审完成日期。'), false
    if (auditRank.value >= 5 && Number(form.secondAuditAmount || 0) <= 0) return showError('二审完成时必须填写二审审定金额。'), false
    if (auditRank.value >= 5 && !form.secondAuditDate) return showError('二审完成时必须填写二审完成日期。'), false
    if (auditRank.value >= 7 && Number(form.finalAuditAmount || 0) <= 0) return showError('最终定案时必须填写最终审定金额。'), false
    if (auditRank.value >= 7 && !form.finalAuditDate) return showError('最终定案时必须填写定案日期。'), false
  }
  if (stepKey.value === 'history') {
    if (Number(form.invoicedAmount || 0) > Number(form.finalAuditAmount || form.contractAmount || 0)) return showError('已开票金额不能超过最终审定金额或合同金额。'), false
    if (Number(form.historicalPaidAmount || 0) > Number(form.contractAmount || 0)) return showError('已付款金额不能超过合同金额。'), false
    if (needsExceptionNote.value && !String(form.exceptionNote || '').trim()) return showError('已收款大于已开票金额时必须填写特殊情况说明。'), false
  }
  if (stepKey.value === 'nodes' && (!form.paymentTemplateId || !form.paymentNodes.length || form.paymentNodes.some((item) => !item.nodeName || item.paymentRatio <= 0))) return showError('请选择模板并完善付款节点名称和比例。'), false
  message.value = ''
  return true
}
function next() { if (!validateCurrentStep()) return; stepIndex.value += 1; maxReachedStep.value = Math.max(maxReachedStep.value, stepIndex.value) }
function applyTemplate(templateId: string) { const template = paymentTemplates.find((item) => item.id === templateId); if (!template) return; form.paymentTemplateId = templateId; form.paymentNodes = template.nodes().map((item, index) => ({ ...item, nodeOrder: index + 1 })) }
function addNode() { form.paymentNodes.push(node('', 'ACCEPTANCE_COMPLETED', 'CONTRACT_PAYMENT_BASE', 0)); form.paymentNodes.forEach((item, index) => { item.nodeOrder = index + 1 }) }
function removeNode(index: number) { form.paymentNodes.splice(index, 1); form.paymentNodes.forEach((item, itemIndex) => { item.nodeOrder = itemIndex + 1 }) }
function updateRatio(item: SettlementPaymentNode, value: number | undefined) { item.paymentRatio = Number(value || 0) / 100 }
function triggerSatisfied(trigger: string) { if (trigger === 'ACCEPTANCE_COMPLETED') return form.acceptanceStatus === 'accepted'; if (trigger === 'WARRANTY_EXPIRED') return Boolean(form.warrantyEndDate && form.warrantyEndDate <= new Date().toISOString().slice(0, 10)); const required: Record<string, number> = { FIRST_AUDIT_COMPLETED: 3, SECOND_AUDIT_COMPLETED: 5, FINAL_AUDIT_COMPLETED: 7 }; return auditRank.value >= (required[trigger] ?? 99) }
function previewNodeStatus(trigger: string, amount: number) { if (!triggerSatisfied(trigger)) return '未满足'; if (form.documentsMissing) return '待补资料'; if (Number(form.invoicedAmount || 0) < amount) return '待开票'; if (Number(form.receivedAmount || 0) <= 0) return '待收款'; if (Number(form.receivedAmount || 0) < amount) return '部分收款'; return '已完成' }
function buildPayload(isDraft: boolean): SettlementProjectPayload {
  const auditFields = canEnterAudit.value ? {} : { auditStatus: 'not_submitted', submittedAmount: 0, firstAuditAmount: 0, firstAuditDate: '', secondAuditAmount: 0, secondAuditDate: '', finalAuditAmount: 0, finalAuditDate: '', warrantyStartDate: '', warrantyEndDate: '' }
  return { ...form, ...auditFields, isDraft, settlementStatus: isDraft ? '草稿' : generatedStatus.value, settlementName: `${selectedProject.value?.projectName || ''}结算管理`, paymentBaseAmount: paymentBaseAmount.value, paymentNodes: calculatedNodes.value.map((item) => ({ ...item })) }
}
async function saveDraft() { if (!form.projectId) return showError('请先选择项目。'); await submit(true) }
async function confirm() { stepIndex.value = steps.length - 1; if (!validateAll()) return; await submit(false) }
function validateAll() { const original = stepIndex.value; for (let index = 0; index < steps.length - 1; index += 1) { stepIndex.value = index; if (!validateCurrentStep()) { maxReachedStep.value = Math.max(maxReachedStep.value, index); return false } } stepIndex.value = original; return true }
async function submit(isDraft: boolean) { saving.value = true; try { await createSettlementProject(buildPayload(isDraft)); messageType.value = 'success'; message.value = isDraft ? '草稿已保存。' : '项目已纳入结算管理。'; emit('saved'); if (!isDraft) emit('update:visible', false) } catch (error) { showError(error instanceof Error ? error.message : '保存结算信息失败') } finally { saving.value = false } }
function close() { emit('update:visible', false) }
function money(value?: number) { return value === undefined || value === null ? '-' : formatWan(value) }
function moneyTriplet(value: number) { const amount = Number(value || 0); return `${amount.toLocaleString('zh-CN', { minimumFractionDigits: 4, maximumFractionDigits: 4 })} 元 / ${(amount / 10000).toFixed(4)} 万元 / ${amountToChineseUpper(amount)}` }
function percent(value: number) { return `${(Number(value || 0) * 100).toFixed(2)}%` }

const HistoryQuestion = defineComponent({
  name: 'HistoryQuestion', props: { label: { type: String, required: true }, hint: { type: String, required: true }, active: { type: Boolean, required: true }, amountLabel: { type: String, required: true }, amount: { type: Number, default: 0 } }, emits: ['toggle', 'amount'],
  setup(props, { emit: childEmit }) { return () => h('article', { class: 'history-question' }, [h('div', [h('strong', props.label), h('span', props.hint)]), h('div', { class: 'binary-control' }, [h('button', { type: 'button', class: { active: !props.active }, onClick: () => childEmit('toggle', false) }, '否'), h('button', { type: 'button', class: { active: props.active }, onClick: () => childEmit('toggle', true) }, '是')]), props.active ? h('label', [h('span', props.amountLabel), h('input', { type: 'number', min: '0', step: '0.01', value: props.amount, onInput: (event: Event) => childEmit('amount', Number((event.target as HTMLInputElement).value || 0)) })]) : null]) }
})
</script>

<style scoped>
.settlement-wizard{display:grid;grid-template-rows:auto minmax(0,1fr) auto;max-height:min(78vh,820px);margin:-8px -16px -16px;color:#10264a}.wizard-steps{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;padding:16px 18px;border-bottom:1px solid rgba(116,145,195,.18);background:rgba(246,249,255,.76)}.wizard-steps button{min-width:0;height:54px;display:flex;align-items:center;gap:8px;padding:0 10px;border:1px solid transparent;border-radius:6px;background:transparent;color:#6b7d99}.wizard-steps button span{width:24px;height:24px;display:grid;place-items:center;border-radius:50%;background:#e9eff9;font-size:12px}.wizard-steps button strong{font-size:13px;white-space:nowrap}.wizard-steps button.active{color:#0f4ce8;background:#fff;border-color:rgba(22,93,255,.24);box-shadow:0 8px 22px rgba(41,73,129,.08)}.wizard-steps button.active span,.wizard-steps button.done span{color:#fff;background:#165dff}.wizard-body{overflow:auto;padding:22px 24px}.wizard-pane{display:grid;gap:18px}.pane-head{display:flex;align-items:flex-start;justify-content:space-between;gap:24px}.pane-head div{display:flex;align-items:center;gap:10px}.pane-head div>span{color:#165dff;font-size:12px;font-weight:700}.pane-head h3{margin:0;font-size:20px}.pane-head p{max-width:540px;margin:0;color:#6e7f99;line-height:1.7}.fact-grid,.review-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.fact-grid article,.review-grid article{min-height:72px;padding:13px;border:1px solid rgba(115,144,194,.18);border-radius:6px;background:rgba(248,250,254,.72)}.fact-grid span,.review-grid span{display:block;margin-bottom:8px;color:#7687a0;font-size:12px}.fact-grid strong,.review-grid strong{line-height:1.5;overflow-wrap:anywhere}.wizard-alert{margin:0;padding:10px 12px;border-radius:6px;background:#edf5ff;color:#2356a8}.wizard-alert.danger{background:#fff2f2;color:#b42318}.form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 16px}.form-grid.compact{max-width:50%}.span-2{grid-column:1/-1}.money-result{display:grid;gap:6px;padding:16px;border-left:3px solid #165dff;border-radius:4px;background:#f5f8ff}.money-result span,.money-result small{color:#6e7f99}.money-result strong{font-size:16px;line-height:1.6;overflow-wrap:anywhere}.source-note{margin:0;color:#75849a;font-size:12px}.wizard-pane h4{margin:0;font-size:14px}.choice-grid{display:grid;gap:10px}.choice-grid--three{grid-template-columns:repeat(3,1fr)}.choice-grid--four{grid-template-columns:repeat(4,1fr)}.choice-grid button,.template-grid button{min-height:68px;padding:12px;text-align:left;border:1px solid rgba(112,142,194,.22);border-radius:6px;background:#fff;color:#1b3155}.choice-grid button strong,.choice-grid button span,.template-grid button strong,.template-grid button span{display:block}.choice-grid button span,.template-grid button span{margin-top:6px;color:#71829d;font-size:12px;line-height:1.5}.choice-grid button.active,.template-grid button.active{border-color:#165dff;background:#f3f7ff;box-shadow:0 0 0 2px rgba(22,93,255,.08)}.status-result{display:flex;align-items:center;justify-content:space-between;padding:13px 16px;border-radius:6px;background:#edf8f5}.status-result span{color:#607c76}.status-result strong{color:#008a70}.history-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.history-question{display:grid;grid-template-columns:1fr auto;gap:12px;padding:14px;border:1px solid rgba(112,142,194,.2);border-radius:6px;background:#fff}.history-question>div:first-child strong,.history-question>div:first-child span{display:block}.history-question>div:first-child span{margin-top:5px;color:#75849b;font-size:12px}.history-question label{grid-column:1/-1;display:grid;gap:6px;color:#5e6f89;font-size:12px}.history-question input{height:34px;padding:0 10px;border:1px solid #d7e0ef;border-radius:4px}.binary-control{display:flex}.binary-control button{height:30px;padding:0 13px;border:1px solid #d8e1f0;background:#fff;color:#64738a}.binary-control button:first-child{border-radius:4px 0 0 4px}.binary-control button:last-child{border-radius:0 4px 4px 0}.binary-control button.active{color:#fff;background:#165dff;border-color:#165dff}.template-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}.node-editor{display:grid;gap:10px}.node-editor article{padding:14px;border:1px solid rgba(112,142,194,.2);border-radius:6px;background:rgba(255,255,255,.8)}.node-editor article>header{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}.node-editor article>header button{border:0;background:transparent;color:#d92d20}.calculation-strip{display:flex;flex-wrap:wrap;gap:18px;padding-top:10px;border-top:1px solid #e7edf6;color:#64758f;font-size:12px}.calculation-strip strong{margin-left:auto;color:#165dff}.add-node{justify-self:start;height:34px;padding:0 14px;border:1px solid #165dff;border-radius:4px;background:#fff;color:#165dff}.document-row{display:grid;gap:10px;padding:14px;border-radius:6px;background:#f7f9fc}.review-table{overflow:hidden;border:1px solid #dfe6f2;border-radius:6px}.review-table>div{display:grid;grid-template-columns:2fr .7fr 1.2fr 1fr;gap:12px;padding:11px 14px;border-bottom:1px solid #e7edf6}.review-table>div:first-child{background:#f5f8fc}.review-table>div:last-child{border-bottom:0}.wizard-message{margin:0 24px 10px;padding:9px 12px;border-radius:4px;background:#edf5ff;color:#2456a5}.wizard-message.error{background:#fff1f1;color:#b42318}.wizard-message.success{background:#ecf8f4;color:#08795f}.wizard-footer{display:grid;grid-template-columns:auto auto 1fr auto auto;gap:10px;padding:14px 18px;border-top:1px solid rgba(116,145,195,.18);background:#fff}.wizard-footer button{height:36px;padding:0 16px;border:1px solid #d5deed;border-radius:4px;background:#fff;color:#29405f}.wizard-footer button.primary{color:#fff;background:#165dff;border-color:#165dff}.wizard-footer button:disabled{opacity:.45;cursor:not-allowed}
.stage-gate{display:grid;gap:5px;padding:14px 16px;border:1px solid rgba(245,166,35,.24);border-radius:6px;background:#fff9ed;color:#6f4b08}.stage-gate span{color:#8a6a2f;font-size:12px;line-height:1.6}
@media(max-width:900px){.wizard-steps{grid-template-columns:repeat(3,1fr)}.fact-grid,.review-grid,.history-grid,.form-grid,.choice-grid--three,.choice-grid--four,.template-grid{grid-template-columns:1fr}.form-grid.compact{max-width:none}.span-2{grid-column:auto}.pane-head{display:grid}.wizard-footer{grid-template-columns:repeat(2,auto);justify-content:end}.wizard-footer span{display:none}}
</style>

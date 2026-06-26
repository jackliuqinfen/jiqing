<template>
  <t-dialog
    v-model:visible="visible"
    :header="dialogHeader"
    width="760px"
    :confirm-btn="readonly ? null : confirmBtnProps"
    :cancel-btn="{ content: readonly ? '关闭' : '取消' }"
    destroy-on-close
    class="audit-edit-dialog"
    @confirm="handleSubmit"
  >
    <t-form
      ref="formRef"
      :data="formData"
      :rules="readonly ? {} : formRules"
      label-align="top"
      class="edit-form"
      :class="{ 'is-readonly': readonly }"
    >
      <!-- 工程基础信息 -->
      <fieldset class="form-fieldset">
        <legend class="fieldset-legend">
          <span class="legend-dot" style="background:var(--color-brand-500)" />工程基础信息
        </legend>
        <div class="form-row">
          <t-form-item label="项目全称" name="projectName" class="flex-2">
            <t-input v-model="formData.projectName" placeholder="请输入项目全称" :disabled="readonly" />
          </t-form-item>
        </div>
        <div class="form-row">
          <t-form-item label="分部/楼栋" name="sectionBuilding">
            <t-input v-model="formData.sectionBuilding" placeholder="如：1#楼主体结构" :disabled="readonly" />
          </t-form-item>
          <t-form-item label="结算编号" name="settlementNo">
            <t-input v-model="formData.settlementNo" placeholder="如：JS-2025-001" :disabled="readonly" />
          </t-form-item>
        </div>
        <div class="form-row">
          <t-form-item label="工程分类" name="category">
            <t-select v-model="formData.category" :options="categoryOpts" placeholder="选择" :disabled="readonly" />
          </t-form-item>
          <t-form-item label="优先级" name="priority">
            <t-select v-model="formData.priority" :options="priorityOpts" placeholder="选择" :disabled="readonly" />
          </t-form-item>
          <t-form-item label="流程阶段" name="stage">
            <t-select v-model="formData.stage" :options="stageOpts" placeholder="选择" :disabled="readonly" />
          </t-form-item>
        </div>
      </fieldset>

      <!-- 经办人 -->
      <fieldset class="form-fieldset">
        <legend class="fieldset-legend">
          <span class="legend-dot" style="background:var(--color-brand-500)" />施工方经办人
        </legend>
        <div class="form-row">
          <t-form-item label="经办人姓名" name="contractorName">
            <t-input v-model="formData.contractorName" placeholder="经办人姓名" :disabled="readonly" />
          </t-form-item>
          <t-form-item label="联系电话" name="contractorPhone">
            <t-input v-model="formData.contractorPhone" placeholder="手机号" :disabled="readonly" />
          </t-form-item>
        </div>
      </fieldset>

      <!-- 造价金额 -->
      <fieldset class="form-fieldset">
        <legend class="fieldset-legend">
          <span class="legend-dot" style="background:var(--color-warning)" />造价金额（元）
        </legend>
        <div class="form-row">
          <t-form-item label="合同金额" name="contractAmount">
            <t-input-number v-model="formData.contractAmount" :min="0" :decimal-places="2" placeholder="0.00" class="w-full" :disabled="readonly" />
          </t-form-item>
          <t-form-item label="送审结算金额" name="submittedAmount">
            <t-input-number v-model="formData.submittedAmount" :min="0" :decimal-places="2" placeholder="0.00" class="w-full" :disabled="readonly" />
          </t-form-item>
        </div>
        <div class="form-row">
          <t-form-item label="一审审定金额" name="firstAuditAmount">
            <t-input-number v-model="formData.firstAuditAmount" :min="0" :decimal-places="2" placeholder="0.00" class="w-full" :disabled="readonly" />
          </t-form-item>
          <t-form-item label="二审审定金额" name="secondAuditAmount">
            <t-input-number v-model="formData.secondAuditAmount" :min="0" :decimal-places="2" placeholder="0.00" class="w-full" :disabled="readonly" />
          </t-form-item>
        </div>
        <div class="form-row">
          <t-form-item label="定案应付工程款" name="finalPayable">
            <t-input-number v-model="formData.finalPayable" :min="0" :decimal-places="2" placeholder="0.00" class="w-full" :disabled="readonly" />
          </t-form-item>
          <t-form-item label="已回款金额" name="paidAmount">
            <t-input-number v-model="formData.paidAmount" :min="0" :decimal-places="2" placeholder="0.00" class="w-full" />
          </t-form-item>
        </div>
      </fieldset>

      <!-- 一审信息 -->
      <fieldset class="form-fieldset">
        <legend class="fieldset-legend">
          <span class="legend-dot" style="background:var(--color-stage-first-audit)" />一审信息（第三方造价事务所）
        </legend>
        <div class="form-row">
          <t-form-item label="咨询单位名称" name="firstCompany" class="flex-2">
            <t-input v-model="formData.firstCompany" placeholder="第三方咨询单位名称" />
          </t-form-item>
        </div>
        <div class="form-row">
          <t-form-item label="初审造价师" name="firstAuditorName">
            <t-input v-model="formData.firstAuditorName" placeholder="造价师姓名" />
          </t-form-item>
          <t-form-item label="联系手机号" name="firstAuditorPhone">
            <t-input v-model="formData.firstAuditorPhone" placeholder="手机号" />
          </t-form-item>
        </div>
      </fieldset>

      <!-- 二审信息 -->
      <fieldset class="form-fieldset">
        <legend class="fieldset-legend">
          <span class="legend-dot" style="background:var(--color-stage-second-audit)" />二审信息（建设单位内审）
        </legend>
        <div class="form-row">
          <t-form-item label="内审部门" name="secondDept" class="flex-2">
            <t-input v-model="formData.secondDept" placeholder="建设单位内审部门" />
          </t-form-item>
        </div>
        <div class="form-row">
          <t-form-item label="复审工程师" name="secondAuditorName">
            <t-input v-model="formData.secondAuditorName" placeholder="工程师姓名" />
          </t-form-item>
          <t-form-item label="联系手机号" name="secondAuditorPhone">
            <t-input v-model="formData.secondAuditorPhone" placeholder="手机号" />
          </t-form-item>
        </div>
      </fieldset>

      <!-- 时限与状态 -->
      <fieldset class="form-fieldset">
        <legend class="fieldset-legend">
          <span class="legend-dot" style="background:var(--color-info)" />时限管控与状态
        </legend>
        <div class="form-row">
          <t-form-item label="报审提交日期" name="submitDate">
            <t-date-picker v-model="formData.submitDate" placeholder="选择日期" clearable />
          </t-form-item>
          <t-form-item label="审计办结截止日" name="auditDeadline">
            <t-date-picker v-model="formData.auditDeadline" placeholder="选择日期" clearable />
          </t-form-item>
          <t-form-item label="资料状态" name="docStatus">
            <t-select v-model="formData.docStatus" :options="docStatusOpts" placeholder="选择" />
          </t-form-item>
        </div>
      </fieldset>

      <!-- 业务备注 -->
      <fieldset class="form-fieldset">
        <legend class="fieldset-legend">
          <span class="legend-dot" style="background:var(--color-gray-400)" />业务备注
        </legend>
        <t-form-item label="结算争议" name="dispute">
          <t-textarea v-model="formData.dispute" placeholder="记录结算争议内容（选填）" :maxlength="500" :rows="2" />
        </t-form-item>
        <t-form-item label="协调记录" name="coordination">
          <t-textarea v-model="formData.coordination" placeholder="记录协调沟通内容（选填）" :maxlength="500" :rows="2" />
        </t-form-item>
      </fieldset>
    </t-form>
  </t-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { useKanbanStore } from '@/store/kanban'
import { MessagePlugin } from '@/ui/message'
import type { FormInstanceFunctions, FormRule } from '@/ui/tdesignCompat'
import type { CostAuditItem, KanbanStage, ProjectCategory, PriorityLevel, DocStatus } from '@/types'
import { createRequestLock } from '@/utils/debounce'
import { todayISO } from '@/utils/date'

const store = useKanbanStore()

const props = defineProps<{
  visible: boolean
  mode: 'create' | 'edit'
  item: CostAuditItem | null
  readonly?: boolean
}>()

const emit = defineEmits<{ 'update:visible': [value: boolean] }>()

const visible = computed({
  get: () => props.visible,
  set: (val) => emit('update:visible', val),
})

const isEdit = computed(() => props.mode === 'edit')
const dialogHeader = computed(() =>
  props.readonly ? '查看造价结算项目' : isEdit.value ? '编辑造价结算项目' : '新增造价结算项目'
)

const formRef = ref<FormInstanceFunctions>()

interface FormData {
  projectName: string; sectionBuilding: string; settlementNo: string
  category: ProjectCategory; priority: PriorityLevel; stage: KanbanStage
  contractorName: string; contractorPhone: string
  contractAmount: number; submittedAmount: number; firstAuditAmount: number
  secondAuditAmount: number; finalPayable: number; paidAmount: number
  firstCompany: string; firstAuditorName: string; firstAuditorPhone: string
  secondDept: string; secondAuditorName: string; secondAuditorPhone: string
  submitDate: string; auditDeadline: string; docStatus: DocStatus
  dispute: string; coordination: string
}

const formData = reactive<FormData>({
  projectName: '', sectionBuilding: '', settlementNo: '',
  category: '竣工总结算', priority: 'S2', stage: 'submitted',
  contractorName: '', contractorPhone: '',
  contractAmount: 0, submittedAmount: 0, firstAuditAmount: 0,
  secondAuditAmount: 0, finalPayable: 0, paidAmount: 0,
  firstCompany: '', firstAuditorName: '', firstAuditorPhone: '',
  secondDept: '', secondAuditorName: '', secondAuditorPhone: '',
  submitDate: todayISO(), auditDeadline: todayISO(), docStatus: '资料齐全',
  dispute: '', coordination: '',
})

const formRules: Record<string, FormRule[]> = {
  projectName: [{ required: true, message: '请输入项目全称', trigger: 'blur' }],
  submittedAmount: [{ required: true, message: '请输入送审金额', trigger: 'blur' }],
  auditDeadline: [{ required: true, message: '请选择截止日期', trigger: 'change' }],
  firstCompany: [{ required: true, message: '请输入审计单位', trigger: 'blur' }],
  firstAuditorPhone: [
    { required: true, message: '请输入对接人电话', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入有效手机号', trigger: 'blur' },
  ],
}

const requestLock = createRequestLock()

const confirmBtnProps = computed(() => ({
  content: isEdit.value ? '保存修改' : '确认创建',
  loading: requestLock.isLocked(),
}))

watch(() => [props.visible, props.item], () => {
  if (!props.visible) return
  if (props.mode === 'edit' && props.item) {
    const item = props.item
    Object.assign(formData, {
      projectName: item.projectName, sectionBuilding: item.sectionBuilding, settlementNo: item.settlementNo,
      category: item.category, priority: item.priority, stage: item.stage,
      contractorName: item.contractor.name, contractorPhone: item.contractor.phone,
      contractAmount: item.amount.contractAmount, submittedAmount: item.amount.submittedAmount,
      firstAuditAmount: item.amount.firstAuditAmount, secondAuditAmount: item.amount.secondAuditAmount,
      finalPayable: item.amount.finalPayable, paidAmount: item.amount.paidAmount,
      firstCompany: item.firstAudit.companyName, firstAuditorName: item.firstAudit.auditor.name,
      firstAuditorPhone: item.firstAudit.auditor.phone,
      secondDept: item.secondAudit.department, secondAuditorName: item.secondAudit.auditor.name,
      secondAuditorPhone: item.secondAudit.auditor.phone,
      submitDate: item.deadline.submitDate, auditDeadline: item.deadline.auditDeadline,
      docStatus: item.docStatus, dispute: item.remark.dispute, coordination: item.remark.coordination,
    })
  } else {
    Object.assign(formData, {
      projectName: '', sectionBuilding: '', settlementNo: '',
      category: '竣工总结算', priority: 'S2', stage: 'submitted',
      contractorName: '', contractorPhone: '',
      contractAmount: 0, submittedAmount: 0, firstAuditAmount: 0,
      secondAuditAmount: 0, finalPayable: 0, paidAmount: 0,
      firstCompany: '', firstAuditorName: '', firstAuditorPhone: '',
      secondDept: '', secondAuditorName: '', secondAuditorPhone: '',
      submitDate: todayISO(), auditDeadline: todayISO(), docStatus: '资料齐全',
      dispute: '', coordination: '',
    })
  }
})

async function handleSubmit() {
  if (props.readonly) {
    visible.value = false
    return
  }
  const valid = await formRef.value?.validate()
  if (valid !== true) return
  if (requestLock.isLocked()) return
  requestLock.lock()
  try {
    const payload = {
      projectName: formData.projectName, sectionBuilding: formData.sectionBuilding,
      settlementNo: formData.settlementNo, category: formData.category, priority: formData.priority,
      stage: formData.stage,
      contractor: { name: formData.contractorName, phone: formData.contractorPhone },
      amount: {
        contractAmount: formData.contractAmount, submittedAmount: formData.submittedAmount,
        firstAuditAmount: formData.firstAuditAmount, secondAuditAmount: formData.secondAuditAmount,
        auditDifference: formData.submittedAmount - formData.secondAuditAmount,
        finalPayable: formData.finalPayable, paidAmount: formData.paidAmount,
      },
      firstAudit: { companyName: formData.firstCompany, auditor: { name: formData.firstAuditorName, phone: formData.firstAuditorPhone } },
      secondAudit: { department: formData.secondDept, auditor: { name: formData.secondAuditorName, phone: formData.secondAuditorPhone } },
      deadline: { submitDate: formData.submitDate, auditDeadline: formData.auditDeadline },
      docStatus: formData.docStatus,
      remark: { dispute: formData.dispute, coordination: formData.coordination },
      operator: '当前用户',
    }
    if (isEdit.value && props.item) {
      await store.handleUpdate({ id: props.item.id, ...payload })
    } else {
      await store.handleCreate(payload)
    }
    visible.value = false
  } catch (e) {
    MessagePlugin.error(`操作失败: ${e instanceof Error ? e.message : '未知错误'}`)
  } finally {
    requestLock.unlock()
  }
}

const priorityOpts = [
  { label: 'S0 特急', value: 'S0' }, { label: 'S1 高', value: 'S1' },
  { label: 'S2 中', value: 'S2' },    { label: 'S3 低', value: 'S3' },
]
const categoryOpts = [
  { label: '竣工总结算', value: '竣工总结算' }, { label: '分部结算', value: '分部结算' },
  { label: '现场签证', value: '现场签证' },     { label: '工程变更', value: '工程变更' },
  { label: '土建造价', value: '土建造价' },     { label: '安装造价', value: '安装造价' },
  { label: '市政结算', value: '市政结算' },     { label: '分包审核', value: '分包审核' },
]
const stageOpts = [
  { label: '报审待受理', value: 'submitted' },   { label: '一级初审', value: 'first_audit' },
  { label: '二级复审', value: 'second_audit' },    { label: '待定案', value: 'conclusion' },
  { label: '办结归档', value: 'archived' },
]
const docStatusOpts = [
  { label: '资料齐全', value: '资料齐全' },     { label: '缺图纸', value: '缺图纸' },
  { label: '缺变更签证', value: '缺变更签证' }, { label: '资料退回补件', value: '资料退回补件' },
]
</script>

<style scoped>
.edit-form {
  max-height: 60vh;
  overflow-y: auto;
  padding-right: var(--space-2);
}

.form-fieldset {
  border: none;
  padding: 0;
  margin: 0 0 var(--space-5);
}

.form-fieldset + .form-fieldset {
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-color);
}

.fieldset-legend {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--space-3);
  padding: 0;
  width: 100%;
}

.legend-dot {
  width: 8px; height: 8px;
  border-radius: 2px;
  flex-shrink: 0;
}

.form-row {
  display: flex;
  gap: var(--space-4);
}

.form-row .t-form__item {
  flex: 1;
  margin-bottom: var(--space-3);
}

.flex-2 { flex: 2 !important; }

.w-full :deep(.t-input-number) { width: 100%; }

:deep(.t-form__label) {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  font-weight: 500;
  padding-bottom: var(--space-1);
}

:deep(.t-dialog__body) {
  padding-top: var(--space-4);
  padding-bottom: var(--space-4);
}

:deep(.t-textarea__inner) {
  resize: vertical;
  min-height: 56px;
}
</style>

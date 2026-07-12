<template>
  <main class="mobile-project">
    <section class="mobile-hero">
      <header class="mobile-top">
        <div>
          <span>工程管理系统</span>
          <h1>项目</h1>
        </div>
        <AButton class="icon-action" shape="circle" variant="outline" :loading="loading" aria-label="刷新项目" @click="loadAll">
          <template #icon><AIcon name="refresh" /></template>
        </AButton>
      </header>

      <section class="mobile-search">
        <AInput v-model="filters.keyword" allow-clear placeholder="搜索项目、编号、单位、负责人" @keyup.enter="applyFilters">
          <template #prefix-icon><AIcon name="search" /></template>
        </AInput>
        <AButton class="icon-action" shape="circle" variant="outline" aria-label="打开筛选" @click="filterVisible = true">
          <template #icon><AIcon name="filter" /></template>
        </AButton>
      </section>
    </section>

    <section class="metric-strip" aria-label="项目概览">
      <button v-for="item in summaryCards" :key="item.key" type="button" :class="{ active: activeQuickFilter === item.key }" @click="applyQuickFilter(item.key)">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </button>
    </section>

    <section v-if="activeFilterLabels.length" class="filter-chips" aria-label="当前筛选">
      <button v-for="chip in activeFilterLabels" :key="chip.key" type="button" @click="clearFilter(chip.key)">
        {{ chip.label }}：{{ chip.value }}
        <b aria-hidden="true">×</b>
      </button>
      <button type="button" @click="resetFilters">清除</button>
    </section>

    <AAlert v-if="error" theme="error" :close="false" class="mobile-alert">
      <template #message>
        <div class="mobile-alert-message">
          <strong>数据加载失败</strong>
          <span>{{ error }}</span>
        </div>
      </template>
    </AAlert>

    <StatePanel
      v-if="loading && records.length === 0"
      state="loading"
      title="正在加载项目"
      description="正在同步项目状态、资料和结算信息。"
    />

    <StatePanel
      v-else-if="!loading && records.length === 0"
      state="empty"
      title="暂无项目"
      description="当前筛选下没有可显示的项目。"
    >
      <template #actions>
        <AButton variant="outline" @click="resetFilters">清除筛选</AButton>
      </template>
    </StatePanel>

    <section v-else class="project-list" aria-label="项目列表">
      <div class="list-head">
        <div>
          <strong>项目列表</strong>
          <span>{{ total }} 个项目 · {{ sortLabel(filters.sort) }}</span>
        </div>
        <AButton size="mini" variant="text" @click="filterVisible = true">筛选</AButton>
      </div>
      <article v-for="record in records" :key="record.id" class="project-card" @click="openDetail(record)">
        <div class="card-head">
          <div>
            <h2>{{ record.projectName }}</h2>
            <p>{{ record.projectCode }} · {{ record.constructionUnit || record.contractorName || '未填写施工单位' }}</p>
          </div>
          <AIcon name="right" />
        </div>
        <div class="tag-row">
          <ATag size="small" variant="light" :theme="projectTheme(record.projectStatus)">{{ projectStatusLabel(record.projectStatus) }}</ATag>
          <ATag size="small" variant="light" :theme="settlementTheme(record.settlementStatus)">{{ settlementStatusLabel(record.settlementStatus) }}</ATag>
        </div>
        <div class="card-progress">
          <div>
            <span>资料完整度</span>
            <strong>{{ record.documentCompletion || 0 }}%</strong>
          </div>
          <i><em :style="{ width: `${Math.min(100, Math.max(0, record.documentCompletion || 0))}%` }" /></i>
        </div>
        <div class="card-meta">
          <span><AIcon name="user" />{{ record.managerName || record.contractorName || '未分配' }}</span>
          <span><AIcon name="safe" /><MoneyDisplay :value="record.contractAmount || record.submittedAmount || 0" mode="inline" /></span>
        </div>
        <div class="next-tip" :data-level="nextAction(record).level">{{ nextAction(record).text }}</div>
      </article>
    </section>

    <div v-if="records.length > 0" class="load-more">
      <span>当前 {{ records.length }} / {{ total }} 项</span>
      <AButton v-if="records.length < total" variant="outline" :loading="loadingMore" @click="loadMore">加载更多</AButton>
    </div>

    <nav class="bottom-nav" aria-label="移动端导航">
      <router-link to="/"><i><AIcon name="dashboard" /></i><span>首页</span></router-link>
      <router-link to="/m/project-management" class="active"><i><AIcon name="task" /></i><span>项目</span></router-link>
      <router-link to="/materials"><i><AIcon name="folder" /></i><span>资料</span></router-link>
      <button type="button" @click="loadAll"><i><AIcon name="refresh" /></i><span>刷新</span></button>
    </nav>

    <AModal
      v-model:visible="filterVisible"
      header="筛选项目"
      :confirm-btn="{ content: '查看结果' }"
      :cancel-btn="{ content: '重置' }"
      modal-class="mobile-sheet-modal"
      @confirm="applyFiltersFromModal"
      @cancel="resetFilters"
    >
      <AForm :model="filters" layout="vertical" class="mobile-form">
        <AFormItem field="projectStatus" label="项目状态">
          <ASelect v-model="filters.projectStatus" allow-clear :options="projectStatusOptions" placeholder="全部项目状态" />
        </AFormItem>
        <AFormItem field="settlementStatus" label="结算状态">
          <ASelect v-model="filters.settlementStatus" allow-clear :options="settlementStatusOptions" placeholder="全部结算状态" />
        </AFormItem>
        <AFormItem field="managerName" label="负责人">
          <AInput v-model="filters.managerName" allow-clear placeholder="输入负责人姓名" />
        </AFormItem>
        <AFormItem field="sort" label="排序">
          <ASelect v-model="filters.sort" :options="sortOptions" />
        </AFormItem>
        <ACheckbox v-model="filters.onlyMissingDocuments">仅看资料不齐</ACheckbox>
        <ACheckbox v-model="filters.onlyAuditLinked">仅看已进入审计</ACheckbox>
      </AForm>
    </AModal>

    <AModal
      v-model:visible="detailVisible"
      header="项目详情"
      :confirm-btn="null"
      width="100%"
      modal-class="mobile-detail-modal"
      destroy-on-close
    >
      <StatePanel v-if="detailLoading" state="loading" title="正在加载项目详情" description="请稍候。" />
      <section v-else-if="currentProject" class="detail-mobile">
        <div class="detail-title">
          <ATag variant="light" :theme="projectTheme(currentProject.projectStatus)">{{ projectStatusLabel(currentProject.projectStatus) }}</ATag>
          <h2>{{ currentProject.projectName }}</h2>
          <p>{{ currentProject.projectCode }} · {{ currentProject.constructionUnit || '未填写施工单位' }}</p>
          <ProjectLifecycleStatus
            ref="lifecycleStatusRef"
            :project-id="currentProject.id"
            @advance="openLifecycleTransition"
          />
        </div>

        <div class="quick-actions">
          <AButton size="small" theme="primary" @click="openFileDialog()">上传资料</AButton>
          <AButton size="small" variant="outline" @click="openSettlementDialog()">新增结算</AButton>
          <AButton size="small" variant="outline" @click="openVariationDialog()">新增签证</AButton>
          <AButton size="small" variant="outline" :loading="auditStarting" @click="currentProject.auditProjectId ? goAudit(currentProject.auditProjectId) : startAudit(currentProject)">
            {{ currentProject.auditProjectId ? '看审计' : '发起审计' }}
          </AButton>
        </div>

        <div class="status-edit">
          <AForm :model="statusForm" layout="vertical" class="status-form">
            <AFormItem field="settlementStatus" label="结算状态">
              <ASelect v-model="statusForm.settlementStatus" :options="settlementStatusOptions" />
            </AFormItem>
          </AForm>
          <AButton theme="primary" :loading="statusSaving" @click="saveStatus">保存结算状态</AButton>
        </div>

        <div class="mobile-tabs" role="tablist">
          <button v-for="tab in tabs" :key="tab.value" type="button" :class="{ active: activeTab === tab.value }" @click="activeTab = tab.value">
            {{ tab.label }}
          </button>
        </div>

        <div v-if="activeTab === 'overview'" class="detail-block">
          <article><span>负责人</span><strong>{{ currentProject.managerName || '未分配' }}</strong></article>
          <article><span>联系电话</span><strong>{{ currentProject.contractorContact || '暂无' }}</strong></article>
          <article><span>合同金额</span><MoneyDisplay :value="currentProject.contractAmount || 0" mode="full" /></article>
          <article><span>已付款</span><MoneyDisplay :value="currentProject.paidAmount || 0" mode="full" /></article>
          <article><span>计划周期</span><strong>{{ shortDate(currentProject.plannedStartDate) }} - {{ shortDate(currentProject.plannedEndDate) }}</strong></article>
          <article><span>资料完整度</span><strong>{{ currentProject.documentCompletion || 0 }}%</strong></article>
        </div>

        <div v-else-if="activeTab === 'files'" class="mobile-list-block">
          <button v-for="category in meta.categories" :key="category.categoryKey" type="button" @click="openFileDialog(category.categoryKey)">
            <div>
              <strong>{{ category.categoryName }}</strong>
              <span>{{ filesByCategory(category.categoryKey).length ? `已上传 ${filesByCategory(category.categoryKey).length} 份` : '待上传' }}</span>
            </div>
            <ATag v-if="category.required" size="small" variant="light" theme="warning">必填</ATag>
          </button>
        </div>

        <div v-else-if="activeTab === 'settlements'" class="mobile-list-block">
          <button v-for="item in currentProject.settlements || []" :key="item.id" type="button" @click="openSettlementDialog(item)">
            <div>
              <strong>{{ item.settlementName }}</strong>
              <span>{{ settlementTypeLabel(item.settlementType) }}</span>
              <MoneyDisplay :value="item.approvedAmount || item.applyAmount || 0" mode="compact" />
            </div>
            <ATag size="small" variant="light" :theme="settlementTheme(item.settlementStatus)">{{ settlementStatusLabel(item.settlementStatus) }}</ATag>
          </button>
          <AButton v-if="!(currentProject.settlements || []).length" theme="primary" @click="openSettlementDialog()">新增结算</AButton>
        </div>

        <div v-else-if="activeTab === 'variations'" class="mobile-list-block">
          <button v-for="item in currentProject.variations || []" :key="item.id" type="button" @click="openVariationDialog(item)">
            <div>
              <strong>{{ item.variationName }}</strong>
              <span>{{ variationTypeLabel(item.variationType) }}</span>
              <MoneyDisplay :value="item.amount || 0" mode="compact" />
            </div>
            <ATag size="small" variant="light" :theme="projectTheme(item.variationStatus)">{{ variationStatusLabel(item.variationStatus) }}</ATag>
          </button>
          <AButton v-if="!(currentProject.variations || []).length" theme="primary" @click="openVariationDialog()">新增签证</AButton>
        </div>

        <div v-else class="mobile-list-block">
          <article v-for="item in currentProject.logs || []" :key="item.id" class="log-row">
            <strong>{{ item.action }}</strong>
            <span>{{ item.content }}</span>
            <em>{{ formatDate(item.createdAt) }}</em>
          </article>
          <StatePanel v-if="!(currentProject.logs || []).length" state="empty" title="暂无操作记录" description="后续更新会自动记录在这里。" />
        </div>
      </section>
    </AModal>

    <AModal
      v-model:visible="fileDialog.visible"
      header="上传资料"
      :confirm-btn="{ content: '开始上传', loading: fileDialog.saving }"
      modal-class="mobile-sheet-modal"
      @confirm="saveFile"
    >
      <AForm :model="fileDialog" layout="vertical" class="mobile-form">
        <AFormItem field="categoryKey" label="资料分类">
          <ASelect v-model="fileDialog.categoryKey" :options="categoryOptions" placeholder="请选择资料分类" />
        </AFormItem>
        <AFormItem field="displayName" label="资料名称">
          <AInput v-model="fileDialog.displayName" placeholder="请输入资料名称" />
        </AFormItem>
        <AFormItem field="file" label="文件">
          <input ref="fileInputRef" class="native-file" type="file" @change="onFilePicked" />
        </AFormItem>
      </AForm>
    </AModal>

    <AModal
      v-model:visible="settlementDialog.visible"
      :header="settlementDialog.mode === 'create' ? '新增结算' : '编辑结算'"
      :confirm-btn="{ content: '保存结算', loading: settlementDialog.saving }"
      modal-class="mobile-sheet-modal"
      @confirm="saveSettlement"
    >
      <AForm :model="settlementForm" layout="vertical" class="mobile-form">
        <AFormItem field="settlementName" label="结算名称"><AInput v-model="settlementForm.settlementName" placeholder="如：一期竣工结算" /></AFormItem>
        <AFormItem field="settlementStatus" label="付款状态"><ASelect v-model="settlementForm.settlementStatus" :options="settlementStatusOptions" /></AFormItem>
        <AFormItem field="settlementType" label="结算事项"><ASelect v-model="settlementForm.settlementType" :options="settlementTypeOptions" /></AFormItem>
        <AFormItem field="applyAmount" label="申报金额"><AInputNumber v-model="settlementForm.applyAmount" :min="0" :precision="2" hide-button /></AFormItem>
        <AFormItem field="approvedAmount" label="核定金额"><AInputNumber v-model="settlementForm.approvedAmount" :min="0" :precision="2" hide-button /></AFormItem>
        <AFormItem field="paidAmount" label="已付款金额"><AInputNumber v-model="settlementForm.paidAmount" :min="0" :precision="2" hide-button /></AFormItem>
        <AFormItem field="remark" label="备注"><ATextarea v-model="settlementForm.remark" :auto-size="{ minRows: 3, maxRows: 5 }" /></AFormItem>
      </AForm>
    </AModal>

    <AModal
      v-model:visible="variationDialog.visible"
      :header="variationDialog.mode === 'create' ? '新增变更签证' : '编辑变更签证'"
      :confirm-btn="{ content: '保存签证', loading: variationDialog.saving }"
      modal-class="mobile-sheet-modal"
      @confirm="saveVariation"
    >
      <AForm :model="variationForm" layout="vertical" class="mobile-form">
        <AFormItem field="variationName" label="签证名称"><AInput v-model="variationForm.variationName" placeholder="如：设计变更签证 01" /></AFormItem>
        <AFormItem field="variationStatus" label="确认状态"><ASelect v-model="variationForm.variationStatus" :options="variationStatusOptions" /></AFormItem>
        <AFormItem field="variationType" label="签证事项"><ASelect v-model="variationForm.variationType" :options="variationTypeOptions" /></AFormItem>
        <AFormItem field="amount" label="金额"><AInputNumber v-model="variationForm.amount" :min="0" :precision="2" hide-button /></AFormItem>
        <AFormItem field="remark" label="备注"><ATextarea v-model="variationForm.remark" :auto-size="{ minRows: 3, maxRows: 5 }" /></AFormItem>
      </AForm>
    </AModal>

    <AModal
      v-model:visible="confirmState.visible"
      :header="confirmState.title"
      :confirm-btn="{ content: confirmState.confirmText, loading: confirmState.loading }"
      :cancel-btn="{ content: '取消' }"
      modal-class="mobile-sheet-modal"
      @confirm="confirmPrimaryAction"
      @cancel="confirmState.visible = false"
    >
      <p class="confirm-message">{{ confirmState.message }}</p>
    </AModal>

    <ProjectStageTransitionModal
      v-model:visible="lifecycleTransitionVisible"
      :project-id="currentProject?.id || ''"
      :snapshot="lifecycleTransitionSnapshot"
      @transitioned="handleLifecycleTransitioned"
      @refresh="refreshLifecycleDetail"
    />
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import StatePanel from '@/components/StatePanel.vue'
import MoneyDisplay from '@/components/MoneyDisplay.vue'
import ProjectLifecycleStatus from '@/components/project/ProjectLifecycleStatus.vue'
import ProjectStageTransitionModal from '@/components/project/ProjectStageTransitionModal.vue'
import { MessagePlugin } from '@/ui/message'
import { friendlyErrorMessage } from '@/utils/errors'
import { auditStartEligibilityMessage, getAuditStartEligibility } from '@/utils/auditEligibility'
import {
  flattenLoadedProjectPages,
  getLoadedProjectPageCount,
  settleLifecycleRefresh,
} from '@/utils/projectLifecycleRefresh'
import {
  businessColor,
  businessLabel,
  projectStatusOptions as projectStatusDict,
  settlementStatusOptions as settlementStatusDict,
  variationStatusOptions as variationStatusDict,
} from '@/utils/businessDictionaries'
import type { ProjectDocumentCategory, ProjectFile, ProjectFilters, ProjectMeta, ProjectRecord, ProjectSettlement, ProjectSummary, ProjectVariation } from '@/types'
import type { ProjectLifecycleSnapshot } from '@/types/projectLifecycle'
import {
  fetchProjectMeta,
  fetchProjectRecord,
  fetchProjectRecords,
  fetchProjectSummary,
  saveProjectSettlement,
  saveProjectVariation,
  startProjectAudit,
  updateProjectRecord,
  updateProjectSettlement,
  updateProjectVariation,
  uploadProjectFile,
} from '@/api/projects'

type DetailTab = 'overview' | 'files' | 'settlements' | 'variations' | 'logs'
type QuickFilter = '' | 'all' | 'active' | 'settlement' | 'audit' | 'missing'

const router = useRouter()
const filters = reactive<ProjectFilters>({
  keyword: '',
  projectStatus: '',
  settlementStatus: '',
  managerName: '',
  onlyMissingDocuments: false,
  onlyAuditLinked: false,
  onlyRisk: false,
  onlyUpcomingDue: false,
  onlyMonthlyNew: false,
  sort: 'updatedAt',
  page: 1,
  pageSize: 10,
})
const meta = reactive<ProjectMeta>({ categories: [], projectStatuses: [], settlementStatuses: [], dictionaryOptions: {}, auditStages: [] })
const summary = reactive<ProjectSummary>({
  totalProjects: 0,
  activeProjects: 0,
  settlementProjects: 0,
  auditLinkedProjects: 0,
  missingDocuments: 0,
  contractMissing: 0,
  variationAmount: 0,
})
const records = ref<ProjectRecord[]>([])
const currentProject = ref<ProjectRecord | null>(null)
const loading = ref(false)
const loadingMore = ref(false)
const detailLoading = ref(false)
const detailVisible = ref(false)
const filterVisible = ref(false)
const activeQuickFilter = ref<QuickFilter>('')
const activeTab = ref<DetailTab>('overview')
const total = ref(0)
const error = ref('')
const auditStarting = ref(false)
const statusSaving = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const lifecycleStatusRef = ref<InstanceType<typeof ProjectLifecycleStatus> | null>(null)
const lifecycleTransitionVisible = ref(false)
const lifecycleTransitionSnapshot = ref<ProjectLifecycleSnapshot | null>(null)

const statusForm = reactive({ settlementStatus: '' })
const fileDialog = reactive({ visible: false, saving: false, projectId: '', categoryKey: '', displayName: '', file: null as File | null })
const settlementDialog = reactive({ visible: false, mode: 'create' as 'create' | 'edit', saving: false, id: '' })
const variationDialog = reactive({ visible: false, mode: 'create' as 'create' | 'edit', saving: false, id: '' })
const confirmState = reactive({
  visible: false,
  title: '',
  message: '',
  confirmText: '确认',
  loading: false,
  onConfirm: null as null | (() => Promise<void> | void),
})
const settlementForm = reactive({
  settlementName: '',
  settlementType: 'progress',
  settlementStatus: 'not_started',
  applyAmount: 0,
  approvedAmount: 0,
  paidAmount: 0,
  applyDate: '',
  expectedPayDate: '',
  paidDate: '',
  remark: '',
})
const variationForm = reactive({
  variationName: '',
  variationType: 'change',
  variationStatus: 'pending',
  amount: 0,
  occurredDate: '',
  approvedDate: '',
  remark: '',
})

const sortOptions = [
  { label: '按更新时间', value: 'updatedAt' },
  { label: '按合同金额', value: 'contractAmount' },
  { label: '按资料完整度', value: 'documentCompletion' },
  { label: '按计划完成日期', value: 'plannedEndDate' },
]
const settlementTypeOptions = [
  { label: '进度款结算', value: 'progress' },
  { label: '竣工结算', value: 'final' },
  { label: '补充结算', value: 'supplement' },
  { label: '其他结算', value: 'other' },
]
const variationTypeOptions = [
  { label: '设计变更', value: 'change' },
  { label: '现场签证', value: 'visa' },
  { label: '工程量调整', value: 'quantity_adjustment' },
  { label: '价格调整', value: 'price_adjustment' },
  { label: '其他事项', value: 'other' },
]
const variationStatusOptions = variationStatusDict.map(({ label, value }) => ({ label, value }))
const tabs: Array<{ label: string; value: DetailTab }> = [
  { label: '概览', value: 'overview' },
  { label: '资料', value: 'files' },
  { label: '结算', value: 'settlements' },
  { label: '签证', value: 'variations' },
  { label: '日志', value: 'logs' },
]
const defaultProjectStatuses = projectStatusDict.map(({ label, value }) => ({ label, value }))
const defaultSettlementStatuses = settlementStatusDict.map(({ label, value }) => ({ label, value }))
const projectStatusOptions = computed(() => meta.projectStatuses.length ? meta.projectStatuses : defaultProjectStatuses)
const settlementStatusOptions = computed(() => meta.settlementStatuses.length ? meta.settlementStatuses : defaultSettlementStatuses)
const categoryOptions = computed(() => meta.categories.map((item) => ({ label: item.categoryName, value: item.categoryKey })))
const summaryCards = computed(() => [
  { key: 'all' as const, label: '项目总数', value: summary.totalProjects },
  { key: 'active' as const, label: '推进中', value: summary.activeProjects },
  { key: 'settlement' as const, label: '付款未清', value: summary.settlementProjects },
  { key: 'missing' as const, label: '资料不齐', value: summary.missingDocuments },
])
const activeFilterLabels = computed(() => {
  const chips: Array<{ key: keyof ProjectFilters; label: string; value: string }> = []
  if (filters.projectStatus) chips.push({ key: 'projectStatus', label: '项目状态', value: projectStatusLabel(filters.projectStatus) })
  if (filters.settlementStatus) chips.push({ key: 'settlementStatus', label: '结算状态', value: settlementStatusLabel(filters.settlementStatus) })
  if (filters.managerName) chips.push({ key: 'managerName', label: '负责人', value: filters.managerName })
  if (filters.onlyMissingDocuments) chips.push({ key: 'onlyMissingDocuments', label: '资料', value: '不齐' })
  if (filters.onlyAuditLinked) chips.push({ key: 'onlyAuditLinked', label: '审计', value: '已进入' })
  return chips
})

function tagTheme(color: string) {
  if (color === 'green') return 'success'
  if (color === 'red') return 'danger'
  if (color === 'orange') return 'warning'
  if (color === 'arcoblue') return 'primary'
  return 'default'
}

function projectTheme(status: string) {
  return tagTheme(businessColor(projectStatusDict, status, businessColor(variationStatusDict, status, 'orange')))
}

function settlementTheme(status: string) {
  return tagTheme(businessColor(settlementStatusDict, status, 'gray'))
}

function projectStatusLabel(value: string) {
  return projectStatusOptions.value.find((item) => item.value === value)?.label || businessLabel(projectStatusDict, value, '未设置')
}

function settlementStatusLabel(value: string) {
  return settlementStatusOptions.value.find((item) => item.value === value)?.label || businessLabel(settlementStatusDict, value, '未设置')
}

function variationStatusLabel(value: string) {
  return businessLabel(variationStatusDict, value, '未设置')
}

function settlementTypeLabel(value: string) {
  return settlementTypeOptions.find((item) => item.value === value)?.label || value || '未设置'
}

function sortLabel(value: string) {
  return sortOptions.find((item) => item.value === value)?.label || '按更新时间'
}

function variationTypeLabel(value: string) {
  return variationTypeOptions.find((item) => item.value === value)?.label || value || '未设置'
}

function shortDate(iso: string) {
  if (!iso) return '暂无'
  return new Date(iso).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

function formatDate(iso: string) {
  if (!iso) return '暂无'
  return new Date(iso).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function isOverdue(record: ProjectRecord) {
  if (!record.plannedEndDate || record.projectStatus === 'archived') return false
  return record.plannedEndDate < new Date().toISOString().slice(0, 10)
}

function nextAction(record: ProjectRecord) {
  if (record.missingRequiredCount > 0) return { level: 'warning', text: `待补 ${record.missingRequiredCount} 类资料` }
  if (isOverdue(record)) return { level: 'danger', text: '计划完成时间已超期' }
  if (!record.auditProjectId && ['pending_submission', 'first_audit', 'second_audit'].includes(record.projectStatus)) return { level: 'primary', text: '可发起或查看审计联动' }
  if (record.settlementStatus === 'partially_paid') return { level: 'warning', text: '付款部分未结清' }
  return { level: 'success', text: '当前项目正常推进' }
}

function filesByCategory(categoryKey: string) {
  return (currentProject.value?.files || []).filter((file) => file.categoryKey === categoryKey)
}

function clearFilter(key: keyof ProjectFilters) {
  if (key === 'onlyMissingDocuments') filters.onlyMissingDocuments = false
  else if (key === 'onlyAuditLinked') filters.onlyAuditLinked = false
  else if (key === 'managerName') filters.managerName = ''
  else if (key === 'projectStatus') filters.projectStatus = ''
  else if (key === 'settlementStatus') filters.settlementStatus = ''
  else if (key === 'keyword') filters.keyword = ''
  else if (key === 'sort') filters.sort = 'updatedAt'
  filters.page = 1
  activeQuickFilter.value = ''
  loadRecords()
}

function resetFilters() {
  filters.keyword = ''
  filters.projectStatus = ''
  filters.settlementStatus = ''
  filters.managerName = ''
  filters.onlyMissingDocuments = false
  filters.onlyAuditLinked = false
  filters.onlyRisk = false
  filters.onlyUpcomingDue = false
  filters.onlyMonthlyNew = false
  filters.sort = 'updatedAt'
  filters.page = 1
  activeQuickFilter.value = ''
  filterVisible.value = false
  loadRecords()
}

function applyFilters() {
  filters.page = 1
  activeQuickFilter.value = ''
  loadRecords()
}

function applyFiltersFromModal() {
  filterVisible.value = false
  applyFilters()
}

function applyQuickFilter(key: QuickFilter) {
  activeQuickFilter.value = key
  filters.projectStatus = ''
  filters.settlementStatus = ''
  filters.onlyMissingDocuments = false
  filters.onlyAuditLinked = false
  filters.onlyRisk = false
  filters.page = 1
  if (key === 'active') filters.projectStatus = 'under_construction'
  if (key === 'settlement') filters.settlementStatus = 'partially_paid'
  if (key === 'audit') filters.onlyAuditLinked = true
  if (key === 'missing') filters.onlyMissingDocuments = true
  loadRecords()
}

async function loadMeta() {
  const value = await fetchProjectMeta()
  meta.categories = value.categories || []
  meta.projectStatuses = value.projectStatuses || []
  meta.settlementStatuses = value.settlementStatuses || []
  meta.dictionaryOptions = value.dictionaryOptions || {}
  meta.auditStages = value.auditStages || []
}

async function loadSummary() {
  Object.assign(summary, await fetchProjectSummary())
}

async function loadRecords(append = false) {
  if (append) loadingMore.value = true
  else loading.value = true
  error.value = ''
  try {
    const result = await fetchProjectRecords(filters)
    records.value = append ? [...records.value, ...result.data] : result.data
    total.value = result.total
    filters.page = result.page
    filters.pageSize = result.pageSize
  } catch (err) {
    error.value = friendlyErrorMessage(err, '项目加载失败，请稍后重试或联系管理员')
    MessagePlugin.error(error.value)
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

async function refreshLoadedRecords() {
  const loadedPageCount = getLoadedProjectPageCount(records.value.length, filters.pageSize)
  const pages = await Promise.all(
    Array.from({ length: loadedPageCount }, (_, index) => fetchProjectRecords({
      ...filters,
      page: index + 1,
      pageSize: filters.pageSize,
    })),
  )
  records.value = flattenLoadedProjectPages(pages.map((page) => page.data))
  total.value = pages[0]?.total || 0
  filters.pageSize = pages[0]?.pageSize || filters.pageSize
}

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadMeta(), loadSummary()])
    filters.page = 1
    await loadRecords()
  } catch (err) {
    error.value = friendlyErrorMessage(err, '移动端项目数据加载失败，请稍后重试或联系管理员')
    MessagePlugin.error(error.value)
  } finally {
    loading.value = false
  }
}

function loadMore() {
  filters.page += 1
  loadRecords(true)
}

async function openDetail(record: ProjectRecord) {
  detailVisible.value = true
  activeTab.value = 'overview'
  detailLoading.value = true
  try {
    currentProject.value = await fetchProjectRecord(record.id)
    statusForm.settlementStatus = currentProject.value.settlementStatus
  } catch (err) {
    currentProject.value = null
    MessagePlugin.error(friendlyErrorMessage(err, '项目详情加载失败，请稍后重试或联系管理员'))
  } finally {
    detailLoading.value = false
  }
}

async function refreshCurrentProject() {
  if (!currentProject.value) return
  currentProject.value = await fetchProjectRecord(currentProject.value.id)
  statusForm.settlementStatus = currentProject.value.settlementStatus
}

async function saveStatus() {
  if (!currentProject.value) return
  statusSaving.value = true
  try {
    await updateProjectRecord(currentProject.value.id, {
      settlementStatus: statusForm.settlementStatus,
    })
    MessagePlugin.success('结算状态已更新')
    await Promise.all([refreshCurrentProject(), loadSummary(), loadRecords()])
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '项目状态保存失败，请稍后重试或联系管理员'))
  } finally {
    statusSaving.value = false
  }
}

function openFileDialog(categoryKey?: string) {
  if (!currentProject.value) return
  fileDialog.projectId = currentProject.value.id
  fileDialog.categoryKey = categoryKey || meta.categories[0]?.categoryKey || ''
  fileDialog.displayName = ''
  fileDialog.file = null
  fileDialog.visible = true
}

function onFilePicked(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] || null
  fileDialog.file = file
  if (file && !fileDialog.displayName) fileDialog.displayName = file.name.replace(/\.[^.]+$/, '')
}

async function saveFile() {
  if (!fileDialog.projectId) return
  if (!fileDialog.categoryKey) {
    MessagePlugin.error('请选择资料分类')
    return
  }
  if (!fileDialog.displayName.trim()) {
    MessagePlugin.error('请填写资料名称')
    return
  }
  if (!fileDialog.file) {
    MessagePlugin.error('请先选择要上传的文件')
    return
  }
  fileDialog.saving = true
  try {
    await uploadProjectFile(fileDialog.projectId, {
      categoryKey: fileDialog.categoryKey,
      displayName: fileDialog.displayName,
      file: fileDialog.file,
    })
    MessagePlugin.success('资料已上传')
    fileDialog.visible = false
    if (fileInputRef.value) fileInputRef.value.value = ''
    await Promise.all([refreshCurrentProject(), loadRecords()])
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '资料上传失败，请检查文件后重试'))
  } finally {
    fileDialog.saving = false
  }
}

function fillSettlementForm(record?: ProjectSettlement | null) {
  Object.assign(settlementForm, {
    settlementName: record?.settlementName || '',
    settlementType: record?.settlementType || 'progress',
    settlementStatus: record?.settlementStatus || 'not_started',
    applyAmount: record?.applyAmount || 0,
    approvedAmount: record?.approvedAmount || 0,
    paidAmount: record?.paidAmount || 0,
    applyDate: record?.applyDate || '',
    expectedPayDate: record?.expectedPayDate || '',
    paidDate: record?.paidDate || '',
    remark: record?.remark || '',
  })
}

function openSettlementDialog(record?: ProjectSettlement | null) {
  if (!currentProject.value) return
  settlementDialog.mode = record ? 'edit' : 'create'
  settlementDialog.id = record?.id || ''
  fillSettlementForm(record || null)
  settlementDialog.visible = true
}

async function saveSettlement() {
  if (!currentProject.value) return
  if (!settlementForm.settlementName.trim()) {
    MessagePlugin.error('请填写结算名称')
    return
  }
  settlementDialog.saving = true
  try {
    const payload = { ...settlementForm }
    if (settlementDialog.mode === 'edit' && settlementDialog.id) await updateProjectSettlement(settlementDialog.id, payload)
    else await saveProjectSettlement(currentProject.value.id, payload)
    MessagePlugin.success('结算已保存')
    settlementDialog.visible = false
    await Promise.all([refreshCurrentProject(), loadSummary(), loadRecords()])
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '结算保存失败，请稍后重试或联系管理员'))
  } finally {
    settlementDialog.saving = false
  }
}

function fillVariationForm(record?: ProjectVariation | null) {
  Object.assign(variationForm, {
    variationName: record?.variationName || '',
    variationType: record?.variationType || 'change',
    variationStatus: record?.variationStatus || 'pending',
    amount: record?.amount || 0,
    occurredDate: record?.occurredDate || '',
    approvedDate: record?.approvedDate || '',
    remark: record?.remark || '',
  })
}

function openVariationDialog(record?: ProjectVariation | null) {
  if (!currentProject.value) return
  variationDialog.mode = record ? 'edit' : 'create'
  variationDialog.id = record?.id || ''
  fillVariationForm(record || null)
  variationDialog.visible = true
}

async function saveVariation() {
  if (!currentProject.value) return
  if (!variationForm.variationName.trim()) {
    MessagePlugin.error('请填写签证名称')
    return
  }
  variationDialog.saving = true
  try {
    const payload = { ...variationForm, amount: Number(variationForm.amount || 0) }
    if (variationDialog.mode === 'edit' && variationDialog.id) await updateProjectVariation(variationDialog.id, payload)
    else await saveProjectVariation(currentProject.value.id, payload)
    MessagePlugin.success('签证已保存')
    variationDialog.visible = false
    await Promise.all([refreshCurrentProject(), loadSummary(), loadRecords()])
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '签证保存失败，请稍后重试或联系管理员'))
  } finally {
    variationDialog.saving = false
  }
}

function startAudit(record: ProjectRecord) {
  if (!record?.id) return
  if (record.auditProjectId) {
    goAudit(record.auditProjectId)
    return
  }
  const eligibility = getAuditStartEligibility(record)
  if (!eligibility.eligible) {
    MessagePlugin.warning(auditStartEligibilityMessage(eligibility.reason))
    return
  }
  confirmState.title = '发起审计流程？'
  confirmState.message = `将「${record.projectName}」发起审计流程，系统会自动带入项目主数据。`
  confirmState.confirmText = '发起审计'
  confirmState.onConfirm = async () => {
    await runStartAudit(record)
  }
  confirmState.visible = true
}

function openLifecycleTransition(snapshot: ProjectLifecycleSnapshot) {
  lifecycleTransitionSnapshot.value = snapshot
  lifecycleTransitionVisible.value = true
}

async function refreshLifecycleDetail() {
  lifecycleTransitionVisible.value = false
  if (!currentProject.value) return
  const { ancillary } = await settleLifecycleRefresh({
    snapshot: () => lifecycleStatusRef.value?.refresh(),
    ancillary: [refreshCurrentProject, loadSummary, refreshLoadedRecords],
  })
  if (ancillary.some((result) => result.status === 'rejected')) {
    MessagePlugin.warning('项目阶段已更新，但部分页面数据刷新失败，请稍后重试。')
  }
}

async function handleLifecycleTransitioned(_snapshot: ProjectLifecycleSnapshot) {
  await refreshLifecycleDetail()
  MessagePlugin.success('项目阶段已推进')
}

async function confirmPrimaryAction() {
  if (!confirmState.onConfirm) return
  confirmState.loading = true
  try {
    await confirmState.onConfirm()
    confirmState.visible = false
  } finally {
    confirmState.loading = false
  }
}

async function runStartAudit(record: ProjectRecord) {
  auditStarting.value = true
  try {
    const auditProject = await startProjectAudit(record.id)
    MessagePlugin.success('已发起审计流程')
    await Promise.all([refreshCurrentProject(), loadSummary(), loadRecords()])
    goAudit(auditProject.id)
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '发起审计失败，请稍后重试或联系管理员'))
  } finally {
    auditStarting.value = false
  }
}

function goAudit(id: string) {
  router.push({ path: '/audit', query: { projectId: id } })
}

onMounted(loadAll)
</script>

<style scoped>
.mobile-project {
  min-height: 100vh;
  display: grid;
  align-content: start;
  gap: 14px;
  padding: 0 12px calc(82px + env(safe-area-inset-bottom));
  background:
    linear-gradient(180deg, #edf4ff 0, #f7f8fa 188px),
    #f7f8fa;
  color: #1d2129;
}

.mobile-hero {
  position: sticky;
  top: 0;
  z-index: 30;
  display: grid;
  gap: 12px;
  padding: calc(12px + env(safe-area-inset-top)) 0 12px;
  background:
    linear-gradient(180deg, rgba(237, 244, 255, .98) 0%, rgba(247, 248, 250, .94) 100%);
  backdrop-filter: blur(14px);
}

.mobile-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.mobile-top span {
  display: block;
  color: #4e5969;
  font-size: 12px;
  line-height: 18px;
  font-weight: 600;
}

.mobile-top h1 {
  margin: 0;
  font-size: 24px;
  line-height: 32px;
  font-weight: 700;
}

.mobile-search {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 42px;
  gap: 8px;
  align-items: center;
}

.mobile-search :deep(.arco-input-wrapper) {
  min-height: 42px;
  border-color: #d8e5ff;
  border-radius: 8px;
  background: rgba(255, 255, 255, .92);
  box-shadow: 0 8px 22px rgba(22, 93, 255, .08);
}

.icon-action {
  width: 42px;
  height: 42px;
  color: #165dff !important;
  border-color: #bedaff !important;
  background: rgba(255, 255, 255, .92) !important;
  box-shadow: 0 8px 22px rgba(22, 93, 255, .08);
}

.metric-strip {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 2px;
  scrollbar-width: none;
}

.metric-strip::-webkit-scrollbar {
  display: none;
}

.metric-strip button {
  flex: 0 0 104px;
  min-height: 74px;
  padding: 10px;
  display: grid;
  gap: 4px;
  text-align: left;
  border: 1px solid #e5e6eb;
  background: #fff;
  border-radius: 8px;
  color: inherit;
}

.metric-strip button.active {
  border-color: #165dff;
  background: #eef4ff;
  box-shadow: 0 8px 20px rgba(22, 93, 255, .12);
}

.metric-strip span,
.card-progress span,
.card-meta,
.detail-block span,
.mobile-list-block span,
.log-row em {
  color: #86909c;
  font-size: 12px;
}

.metric-strip strong {
  font-size: 20px;
  line-height: 24px;
}

.filter-chips {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 2px;
  scrollbar-width: none;
}

.filter-chips::-webkit-scrollbar {
  display: none;
}

.filter-chips button {
  flex: 0 0 auto;
  min-height: 32px;
  padding: 0 10px;
  border: 1px solid #bedaff;
  border-radius: 8px;
  background: #eef4ff;
  color: #165dff;
  font: inherit;
  font-size: 12px;
}

.filter-chips b {
  margin-left: 4px;
}

.mobile-alert-message {
  display: grid;
  gap: 3px;
  color: #4e5969;
}

.mobile-alert-message strong {
  color: #1d2129;
  font-size: 14px;
}

.mobile-alert-message span {
  font-size: 12px;
  line-height: 18px;
}

.project-list {
  display: grid;
  gap: 10px;
}

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 2px;
}

.list-head div {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.list-head strong {
  font-size: 15px;
  line-height: 20px;
}

.list-head span {
  color: #86909c;
  font-size: 12px;
}

.project-card {
  display: grid;
  gap: 11px;
  padding: 13px;
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  box-shadow: 0 8px 22px rgba(29, 33, 41, .05);
  transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease;
}

.project-card:active {
  transform: scale(.992);
  border-color: #bedaff;
  box-shadow: 0 4px 12px rgba(29, 33, 41, .06);
}

.card-head {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 10px;
}

.card-head h2,
.detail-title h2 {
  margin: 0;
  color: #1d2129;
  font-size: 16px;
  line-height: 22px;
  font-weight: 700;
  word-break: break-word;
}

.card-head p,
.detail-title p {
  margin: 4px 0 0;
  color: #86909c;
  font-size: 12px;
  line-height: 18px;
}

.tag-row {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.card-progress {
  display: grid;
  gap: 7px;
}

.card-progress div {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-progress i {
  height: 6px;
  background: #f2f3f5;
  border-radius: 999px;
  overflow: hidden;
}

.card-progress em {
  display: block;
  height: 100%;
  background: #165dff;
  border-radius: inherit;
}

.card-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.card-meta span {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta :deep(.arco-icon) {
  flex: 0 0 auto;
  color: #a9aeb8;
}

.next-tip {
  min-height: 32px;
  display: flex;
  align-items: center;
  padding: 0 10px;
  background: #f7f8fa;
  border-radius: 6px;
  color: #4e5969;
  font-size: 12px;
  font-weight: 600;
}

.next-tip[data-level='warning'] {
  color: #b77900;
  background: #fff7e8;
}

.next-tip[data-level='danger'] {
  color: #cb272d;
  background: #fff1f0;
}

.next-tip[data-level='primary'] {
  color: #165dff;
  background: #eef4ff;
}

.next-tip[data-level='success'] {
  color: #00a870;
  background: #e8fffb;
}

.load-more {
  display: grid;
  gap: 8px;
  justify-items: center;
  color: #86909c;
  font-size: 12px;
}

.bottom-nav {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 50;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  min-height: calc(64px + env(safe-area-inset-bottom));
  padding: 6px 10px calc(6px + env(safe-area-inset-bottom));
  background: rgba(255, 255, 255, .96);
  border-top: 1px solid #e5e6eb;
  backdrop-filter: blur(12px);
}

.bottom-nav a,
.bottom-nav button {
  min-width: 0;
  min-height: 52px;
  display: grid;
  justify-items: center;
  align-content: center;
  gap: 3px;
  color: #86909c;
  border: 0;
  background: transparent;
  text-decoration: none;
  font: inherit;
  font-size: 11px;
}

.bottom-nav i {
  width: 28px;
  height: 24px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  font-style: normal;
}

.bottom-nav .active {
  color: #165dff;
  font-weight: 600;
}

.bottom-nav .active i {
  background: #eef4ff;
}

.mobile-form {
  display: grid;
  gap: 10px;
}

.mobile-form :deep(.arco-form-item) {
  margin-bottom: 0;
}

.mobile-form :deep(.arco-input-wrapper),
.mobile-form :deep(.arco-select-view),
.mobile-form :deep(.arco-input-number),
.status-form :deep(.arco-select-view) {
  width: 100%;
}

.native-file {
  width: 100%;
  min-height: 36px;
  font: inherit;
}

.detail-mobile {
  display: grid;
  gap: 12px;
}

.detail-title {
  display: grid;
  gap: 6px;
}

.quick-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.quick-actions :deep(.arco-btn) {
  min-width: 0;
  min-height: 38px;
  padding-inline: 8px;
}

.status-edit {
  display: grid;
  gap: 10px;
  padding: 12px;
  background: #f7faff;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
}

.status-form {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 8px;
}

.status-form :deep(.arco-form-item) {
  margin-bottom: 0;
}

.mobile-tabs {
  display: flex;
  gap: 4px;
  padding: 4px;
  overflow-x: auto;
  background: #f2f3f5;
  border-radius: 8px;
  scrollbar-width: none;
}

.mobile-tabs::-webkit-scrollbar {
  display: none;
}

.mobile-tabs button {
  flex: 1 0 58px;
  min-height: 34px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #4e5969;
  font: inherit;
  font-size: 13px;
}

.mobile-tabs button.active {
  background: #fff;
  color: #165dff;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(29, 33, 41, .06);
}

.detail-block {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.detail-block article,
.log-row {
  display: grid;
  gap: 4px;
  padding: 10px;
  background: #f7f8fa;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
}

.detail-block strong,
.mobile-list-block strong {
  min-width: 0;
  color: #1d2129;
  font-size: 14px;
  line-height: 20px;
}

.mobile-list-block {
  display: grid;
  gap: 8px;
}

.mobile-list-block > button {
  width: 100%;
  min-height: 58px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px;
  text-align: left;
  color: inherit;
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 8px;
  font: inherit;
}

.mobile-list-block > button div {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.confirm-message {
  margin: 0;
  color: #4e5969;
  line-height: 1.7;
}

:global(.mobile-detail-modal) {
  width: min(100vw, 560px) !important;
  max-width: 100vw;
  margin: 0;
}

:global(.mobile-detail-modal .arco-modal) {
  width: 100% !important;
  max-width: 100vw;
  min-height: 100vh;
  border-radius: 0;
}

:global(.mobile-detail-modal .arco-modal-body) {
  max-height: calc(100vh - 112px);
  overflow: auto;
  padding-bottom: calc(20px + env(safe-area-inset-bottom));
}

:global(.mobile-sheet-modal) {
  width: min(100vw - 24px, 520px) !important;
}

@media (min-width: 700px) {
  .mobile-project {
    max-width: 560px;
    margin: 0 auto;
    border-inline: 1px solid #e5e6eb;
  }

  .bottom-nav {
    left: 50%;
    width: 560px;
    transform: translateX(-50%);
    border-inline: 1px solid #e5e6eb;
  }
}

@media (max-width: 360px) {
  .metric-strip button {
    flex-basis: 96px;
  }

  .quick-actions {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

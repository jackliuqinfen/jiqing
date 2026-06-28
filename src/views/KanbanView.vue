<template>
  <div class="audit-shell" :class="[`layout-${layoutMode}`, { 'audit-shell--embedded': embedded }]">
    <header class="audit-header" :class="{ 'audit-header--embedded': embedded }">
      <div v-if="!embedded" class="brand">
        <div class="brand-mark"><t-icon name="layers" /></div>
        <div>
          <h1>江苏集庆·工程管理系统</h1>
          <p>审计看板 · 工程管理工作台</p>
        </div>
      </div>
      <div class="header-actions">
        <div class="segmented">
          <button
            v-for="item in viewModes"
            :key="item.value"
            :aria-label="item.label"
            :class="{ active: viewMode === item.value }"
            @click="viewMode = item.value"
          >
            <t-icon :name="item.icon" />
            <span>{{ item.label }}</span>
          </button>
        </div>
        <select v-model="layoutMode" class="native-select layout-select" aria-label="布局模式">
          <option value="horizontal">横向</option>
          <option value="vertical">纵向</option>
          <option value="compact">紧凑</option>
          <option value="standard">标准</option>
          <option value="bigscreen">大屏</option>
        </select>
        <t-button theme="primary" size="small" @click="openCreate">
          <template #icon><t-icon name="add" /></template>
          新增项目
        </t-button>
        <t-button variant="outline" size="small" :loading="store.loading" @click="store.refreshAll">
          <template #icon><t-icon name="refresh" /></template>
          刷新
        </t-button>
        <template v-if="!embedded">
          <t-button v-if="authStore.isAdmin" variant="outline" size="small" @click="router.push('/admin')">
            <template #icon><t-icon name="setting" /></template>
            后台
          </t-button>
          <t-button v-if="authStore.isAuthenticated" variant="text" size="small" @click="logout">退出</t-button>
          <t-button v-else theme="primary" size="small" @click="router.push('/login')">登录</t-button>
        </template>
      </div>
    </header>

    <main class="audit-main">
      <section class="summary-grid">
        <article v-for="card in summaryCards" :key="card.label" class="summary-card">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <em>{{ card.hint }}</em>
        </article>
      </section>

      <section class="toolbar">
        <input v-model="store.filters.keyword" class="native-input keyword" placeholder="搜索项目、楼栋、结算编号" @keyup.enter="store.refreshProjects" />
        <select v-model="store.filters.stage" class="native-select" @change="store.refreshProjects">
          <option value="">全部阶段</option>
          <option v-for="stage in store.meta.stages" :key="stage.code" :value="stage.code">{{ stage.title }}</option>
        </select>
        <select v-model="store.filters.priority" class="native-select" @change="store.refreshProjects">
          <option value="">全部优先级</option>
          <option v-for="option in options.priority" :key="option.id" :value="option.optionValue">{{ option.optionLabel }}</option>
        </select>
        <select v-model="store.filters.category" class="native-select" @change="store.refreshProjects">
          <option value="">全部分类</option>
          <option v-for="option in options.category" :key="option.id" :value="option.optionValue">{{ option.optionLabel }}</option>
        </select>
        <select v-model="store.filters.status" class="native-select" @change="store.refreshProjects">
          <option value="">全部状态</option>
          <option v-for="option in options.status" :key="option.id" :value="option.optionValue">{{ option.optionLabel }}</option>
        </select>
        <input v-model="store.filters.owner" class="native-input small-filter" placeholder="负责人" @keyup.enter="store.refreshProjects" />
        <input v-model="store.filters.startDate" class="native-input date-filter" type="date" @change="store.refreshProjects" />
        <input v-model="store.filters.endDate" class="native-input date-filter" type="date" @change="store.refreshProjects" />
        <select v-model="store.filters.sort" class="native-select" @change="store.refreshProjects">
          <option value="stage">按阶段</option>
          <option value="plannedEndDate">按计划日期</option>
          <option value="progress">按进度</option>
          <option value="amount">按金额</option>
          <option value="updatedAt">按更新</option>
        </select>
        <label class="check-filter">
          <input v-model="store.filters.onlyOverdue" type="checkbox" @change="store.refreshProjects" />
          仅超期
        </label>
        <t-button size="small" variant="outline" @click="applyFilters">查询</t-button>
        <t-button size="small" variant="text" @click="resetFilters">重置</t-button>
      </section>

      <t-alert v-if="store.error" theme="error" :close="false" class="error-alert">
        <template #message>{{ store.error }}</template>
      </t-alert>

      <div v-if="store.loading && store.projects.length === 0" class="center-state">
        <t-loading size="large" text="正在加载数据库数据..." />
      </div>

      <section v-else-if="viewMode === 'kanban'" class="kanban-board">
        <div v-for="stage in store.meta.stages" :key="stage.code" class="kanban-column">
          <div class="column-head" :style="{ borderTopColor: stage.color }">
            <div>
              <h2>{{ stage.title }}</h2>
              <span>{{ stage.code }}</span>
            </div>
            <strong>{{ stageCount(stage.code) }}</strong>
          </div>
          <div class="column-body">
            <button
              v-for="project in store.projectsByStage[stage.code]"
              :key="project.id"
              class="project-card"
              type="button"
              @click="openDetail(project)"
            >
              <div class="card-title-row">
                <strong>{{ project.projectName }}</strong>
                <span class="priority" :class="`priority-${project.priority}`">{{ project.priority }}</span>
              </div>
              <div class="card-meta">{{ project.sectionBuilding }} · {{ project.settlementNo }}</div>
              <div class="card-fields">
                <span v-for="field in visibleCardFields" :key="field.id">
                  {{ field.fieldLabel }}: {{ displayField(project, field) }}
                </span>
              </div>
              <div class="card-footer">
                <span>{{ money(project.amount.submittedAmount) }}</span>
                <span :class="{ overdue: isOverdue(project) }">{{ project.deadline.auditDeadline || '未设期限' }}</span>
              </div>
            </button>
            <div v-if="stageCount(stage.code) === 0" class="empty-column">暂无项目</div>
          </div>
        </div>
      </section>

      <section v-else-if="viewMode === 'gantt'" class="gantt-view">
        <div class="gantt-head">
          <span>项目</span>
          <span>周期</span>
        </div>
        <div v-for="project in store.projects" :key="project.id" class="gantt-row" @click="openDetail(project)">
          <div class="gantt-name">
            <strong>{{ project.projectName }}</strong>
            <span>{{ stageTitle(project.stage) }} · {{ project.contractor.name }}</span>
          </div>
          <div class="gantt-track">
            <div class="gantt-bar" :style="ganttStyle(project)">
              <span>{{ project.deadline.submitDate }} 至 {{ project.deadline.auditDeadline }}</span>
            </div>
          </div>
        </div>
      </section>

      <section v-else class="table-view">
        <table>
          <thead>
            <tr>
              <th v-for="field in store.tableFields" :key="field.id">{{ field.fieldLabel }}</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="project in store.projects" :key="project.id">
              <td v-for="field in store.tableFields" :key="field.id">{{ displayField(project, field) }}</td>
              <td><button class="link-button" @click="openDetail(project)">查看</button></td>
            </tr>
          </tbody>
        </table>
      </section>

      <section v-if="!store.loading" class="pager">
        <span>共 {{ store.total }} 条，第 {{ store.filters.page }} 页</span>
        <select v-model.number="store.filters.pageSize" class="native-select" @change="changePage(1)">
          <option :value="10">10 条/页</option>
          <option :value="20">20 条/页</option>
          <option :value="50">50 条/页</option>
        </select>
        <t-button size="small" variant="outline" :disabled="store.filters.page <= 1" @click="changePage(store.filters.page - 1)">上一页</t-button>
        <t-button size="small" variant="outline" :disabled="store.filters.page >= totalPages" @click="changePage(store.filters.page + 1)">下一页</t-button>
      </section>
    </main>

    <aside v-if="detailVisible" class="drawer">
      <div class="drawer-panel">
        <div class="drawer-head">
          <div>
            <h2>{{ editing ? '编辑项目' : store.selectedProject?.projectName }}</h2>
            <p>{{ editing ? '按字段配置生成表单' : '项目详情与进度流转' }}</p>
          </div>
          <button class="icon-button" @click="closeDrawer"><t-icon name="close" /></button>
        </div>

        <form v-if="editing" class="project-form" @submit.prevent="saveProject">
          <label v-for="field in store.formFields" :key="field.id" class="form-field">
            <span>{{ field.fieldLabel }}<b v-if="field.required">*</b></span>
            <select v-if="field.fieldType === 'select'" v-model="formValues[field.fieldKey]" class="native-select">
              <option value="">请选择</option>
              <option v-for="option in optionList(field.optionGroup)" :key="option.id" :value="option.optionValue">{{ option.optionLabel }}</option>
              <option value="__custom">手动录入</option>
            </select>
            <textarea v-else-if="field.fieldType === 'textarea'" v-model="formValues[field.fieldKey]" class="native-textarea" rows="3" />
            <input v-else :type="inputType(field.fieldType)" v-model="formValues[field.fieldKey]" class="native-input" />
            <div v-if="formValues[field.fieldKey] === '__custom'" class="custom-option">
              <input v-model="customOptionValues[field.fieldKey]" class="native-input" placeholder="录入新选项" />
              <t-button size="small" variant="outline" @click.prevent="saveCustomOption(field)">保存到选项库</t-button>
            </div>
          </label>
          <div class="drawer-actions">
            <t-button variant="outline" @click="editing = false">取消</t-button>
            <t-button theme="primary" type="submit" :loading="store.saving">保存</t-button>
          </div>
        </form>

        <div v-else-if="store.selectedProject" class="detail-view">
          <div class="detail-status">
            <span class="stage-pill">{{ stageTitle(store.selectedProject.stage) }}</span>
            <span :class="{ overdue: isOverdue(store.selectedProject) }">期限 {{ store.selectedProject.deadline.auditDeadline || '-' }}</span>
          </div>
          <dl class="detail-grid">
            <template v-for="field in store.detailFields" :key="field.id">
              <dt>{{ field.fieldLabel }}</dt>
              <dd>{{ displayField(store.selectedProject, field) }}</dd>
            </template>
          </dl>
          <div class="progress-box">
            <h3>进度流转</h3>
            <div class="stage-actions">
              <button
                v-for="stage in store.meta.stages"
                :key="stage.code"
                :class="{ active: stage.code === store.selectedProject.stage }"
                type="button"
                @click="moveProject(stage.code)"
              >
                {{ stage.title }}
              </button>
            </div>
          </div>
          <div class="stage-history">
            <h3>阶段记录</h3>
            <p v-for="stage in store.selectedProject.stages || []" :key="stage.id">
              {{ stage.stage_name }} · {{ stage.status }} · {{ stage.handler_name || stage.owner || '-' }} · {{ stage.entered_at }}
            </p>
            <p v-if="(store.selectedProject.stages || []).length === 0">暂无阶段记录</p>
          </div>
          <div class="attachment-box">
            <div class="section-title-row">
              <h3>附件信息</h3>
              <t-button v-if="authStore.isEditor" size="small" variant="outline" :loading="attachmentUploading" @click="triggerAttachmentSelect">
                <template #icon><t-icon name="upload" /></template>
                上传
              </t-button>
              <input ref="attachmentInputRef" class="attachment-input" type="file" @change="handleAttachmentUpload" />
            </div>
            <div v-if="(store.selectedProject.attachments || []).length" class="attachment-list">
              <div v-for="file in store.selectedProject.attachments || []" :key="file.id" class="attachment-item">
                <div class="attachment-main">
                  <strong>{{ attachmentName(file) }}</strong>
                  <span>{{ attachmentType(file) }} · {{ formatFileSize(file.fileSize) }} · {{ attachmentUploader(file) }} · {{ attachmentCreatedAt(file) }}</span>
                </div>
                <div class="attachment-actions">
                  <button type="button" :disabled="!file.canPreview" @click="openAttachmentPreview(file)">预览</button>
                  <button type="button" @click="downloadAttachment(file)">下载</button>
                  <button v-if="authStore.isEditor" type="button" class="danger-text" @click="removeAttachment(file)">删除</button>
                </div>
              </div>
            </div>
            <p v-else>暂无附件</p>
          </div>
          <div class="log-box">
            <h3>操作日志</h3>
            <p v-for="log in store.selectedProject.logs || []" :key="log.id">{{ log.created_at }} · {{ log.operator }} · {{ log.note || log.action }}</p>
          </div>
          <div class="drawer-actions">
            <t-button variant="outline" @click="startEdit(store.selectedProject)">编辑</t-button>
          </div>
        </div>
      </div>
    </aside>

    <div v-if="attachmentPreview.visible" class="preview-mask">
      <div class="preview-panel">
        <div class="preview-head">
          <div>
            <h3>{{ attachmentPreview.title }}</h3>
            <p>{{ attachmentPreview.hint }}</p>
          </div>
          <button class="icon-button" @click="closeAttachmentPreview"><t-icon name="close" /></button>
        </div>
        <div class="preview-body">
          <p v-if="attachmentPreview.loading" class="preview-message">正在加载预览...</p>
          <img v-else-if="attachmentPreview.kind === 'image'" :src="attachmentPreview.url" alt="附件预览" />
          <iframe v-else-if="attachmentPreview.kind === 'pdf'" :src="attachmentPreview.url" title="PDF 预览" />
          <pre v-else-if="attachmentPreview.kind === 'text'">{{ attachmentPreview.text }}</pre>
          <video v-else-if="attachmentPreview.kind === 'video'" :src="attachmentPreview.url" controls />
          <audio v-else-if="attachmentPreview.kind === 'audio'" :src="attachmentPreview.url" controls />
          <p v-else class="preview-message">{{ attachmentPreview.error || '该文件类型暂不支持在线预览，请下载查看' }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { MessagePlugin } from '@/ui/message'
import { fetchAttachmentDownloadBlob, fetchAttachmentPreviewBlob } from '@/api/audit'
import { useAuditStore } from '@/store/audit'
import { useAuthStore } from '@/store/auth'
import type { AuditFieldConfig, AuditLayoutMode, AuditProject, AuditProjectAttachment, AuditStageCode, AuditViewMode } from '@/types/audit'

const router = useRouter()
const store = useAuditStore()
const authStore = useAuthStore()
defineProps<{ embedded?: boolean }>()
const viewMode = ref<AuditViewMode>('kanban')
const layoutMode = ref<AuditLayoutMode>('horizontal')
const detailVisible = ref(false)
const editing = ref(false)
const editingId = ref('')
const formValues = reactive<Record<string, string>>({})
const customOptionValues = reactive<Record<string, string>>({})
const attachmentInputRef = ref<HTMLInputElement | null>(null)
const attachmentUploading = ref(false)
const attachmentPreview = reactive({
  visible: false,
  loading: false,
  title: '',
  hint: '',
  kind: '',
  url: '',
  text: '',
  error: '',
})

const viewModes: { value: AuditViewMode; label: string; icon: string }[] = [
  { value: 'kanban', label: '看板', icon: 'view-column' },
  { value: 'gantt', label: '甘特', icon: 'chart' },
  { value: 'table', label: '表格', icon: 'view-list' },
]

const options = computed(() => store.meta.options)
const visibleCardFields = computed(() => store.cardFields.filter((field) => !['project_name', 'current_stage'].includes(field.fieldKey)).slice(0, 5))
const totalPages = computed(() => Math.max(1, Math.ceil(store.total / store.filters.pageSize)))
const summaryCards = computed(() => [
  { label: '总项目', value: store.summary.totalProjects, hint: '数据库实时统计' },
  { label: '在审项目', value: store.summary.inAuditProjects, hint: '一审 + 二审' },
  { label: '已完成', value: store.summary.completedProjects, hint: '已完成/归档' },
  { label: '超期督办', value: store.summary.overdueProjects, hint: '未归档且过期' },
  { label: '本月新增', value: store.summary.monthlyNewProjects, hint: '按创建时间统计' },
  { label: '即将到期', value: store.summary.upcomingDueProjects, hint: '7 天内计划完成' },
  { label: '送审金额', value: money(store.summary.totalSubmittedAmount), hint: '全部项目合计' },
])

onMounted(() => {
  store.refreshAll()
})

function money(value: number) {
  if (!value) return '0'
  if (value >= 100000000) return `${(value / 100000000).toFixed(2)} 亿`
  if (value >= 10000) return `${(value / 10000).toFixed(1)} 万`
  return value.toLocaleString('zh-CN')
}

function displayField(project: AuditProject, field: AuditFieldConfig) {
  const value = store.readField(project, field)
  if (field.fieldType === 'number') return money(Number(value))
  if (typeof value === 'boolean') return value ? '是' : '否'
  return value || '-'
}

function stageTitle(code: string) {
  return store.meta.stages.find((stage) => stage.code === code)?.title || code
}

function stageCount(code: string) {
  return store.projectsByStage[code]?.length || 0
}

function isOverdue(project: AuditProject) {
  return Boolean(project.deadline.auditDeadline && project.deadline.auditDeadline < new Date().toISOString().slice(0, 10) && project.stage !== 'archived')
}

function applyFilters() {
  store.filters.page = 1
  store.refreshProjects()
}

function resetFilters() {
  store.resetFilters()
  store.refreshProjects()
}

function changePage(page: number) {
  store.filters.page = Math.min(Math.max(page, 1), totalPages.value)
  store.refreshProjects()
}

async function openDetail(project: AuditProject) {
  await store.selectProject(project)
  detailVisible.value = true
  editing.value = false
}

function closeDrawer() {
  detailVisible.value = false
  editing.value = false
  store.selectedProject = null
  closeAttachmentPreview()
}

function openCreate() {
  editingId.value = ''
  store.selectedProject = null
  resetForm()
  detailVisible.value = true
  editing.value = true
}

function startEdit(project: AuditProject) {
  editingId.value = project.id
  resetForm(project)
  editing.value = true
}

function resetForm(project?: AuditProject) {
  for (const key of Object.keys(formValues)) delete formValues[key]
  for (const field of store.formFields) {
    formValues[field.fieldKey] = project ? String(store.readField(project, field) || '') : defaultValue(field)
  }
}

function defaultValue(field: AuditFieldConfig) {
  if (field.fieldKey === 'current_stage') return 'submitted'
  if (field.fieldKey === 'priority') return 'S2'
  if (field.fieldKey === 'doc_status') return '资料齐全'
  if (field.fieldKey === 'status') return 'active'
  if (field.fieldKey === 'audit_type') return '工程审计'
  if (field.fieldKey === 'progress_percent') return '0'
  return ''
}

function optionList(group: string) {
  return group ? store.meta.options[group] || [] : []
}

function inputType(type: string) {
  if (type === 'number') return 'number'
  if (type === 'date') return 'date'
  return 'text'
}

async function saveCustomOption(field: AuditFieldConfig) {
  const value = customOptionValues[field.fieldKey]?.trim()
  if (!field.optionGroup || !value) return
  await store.addOption(field.optionGroup, value)
  formValues[field.fieldKey] = value
  customOptionValues[field.fieldKey] = ''
  MessagePlugin.success('已保存到选项库')
}

function valuesToProject(): Partial<AuditProject> {
  const normalizedValues = Object.fromEntries(
    Object.entries(formValues).map(([key, value]) => [key, value === '__custom' ? (customOptionValues[key] || '') : value])
  )
  const knownFields = new Set([
    'project_code', 'project_name', 'audited_unit', 'audit_type', 'section_building', 'settlement_no',
    'category', 'priority', 'manager_name', 'contractor_name', 'start_date', 'planned_end_date',
    'actual_end_date', 'progress_percent', 'status', 'is_delayed', 'delay_days', 'submitted_amount',
    'current_stage', 'doc_status', 'description', 'remark_coordination',
  ])
  const customFields = Object.fromEntries(
    Object.entries(normalizedValues).filter(([key, value]) => !knownFields.has(key) && value !== '')
  )
  return {
    id: editingId.value || undefined,
    projectCode: normalizedValues.project_code || normalizedValues.settlement_no,
    projectName: normalizedValues.project_name,
    auditedUnit: normalizedValues.audited_unit,
    auditType: normalizedValues.audit_type || normalizedValues.category,
    sectionBuilding: normalizedValues.section_building,
    settlementNo: normalizedValues.settlement_no,
    category: normalizedValues.category,
    priority: normalizedValues.priority,
    contractor: { name: normalizedValues.contractor_name || '', phone: '' },
    firstAudit: { companyName: '', auditor: { name: '' } },
    secondAudit: { department: '', auditor: { name: '' } },
    amount: {
      contractAmount: 0,
      submittedAmount: Number(normalizedValues.submitted_amount || 0),
      firstAuditAmount: 0,
      secondAuditAmount: 0,
      auditDifference: 0,
      finalPayable: 0,
      paidAmount: 0,
    },
    deadline: { submitDate: normalizedValues.start_date || new Date().toISOString().slice(0, 10), auditDeadline: normalizedValues.planned_end_date || normalizedValues.audit_deadline || '' },
    startDate: normalizedValues.start_date || new Date().toISOString().slice(0, 10),
    plannedEndDate: normalizedValues.planned_end_date || normalizedValues.audit_deadline || '',
    actualEndDate: normalizedValues.actual_end_date || '',
    docStatus: normalizedValues.doc_status,
    stage: (normalizedValues.current_stage || 'submitted') as AuditStageCode,
    status: normalizedValues.status || 'active',
    progressPercent: Number(normalizedValues.progress_percent || 0),
    managerName: normalizedValues.manager_name || normalizedValues.contractor_name || '',
    isDelayed: normalizedValues.is_delayed === 'true',
    delayDays: Number(normalizedValues.delay_days || 0),
    description: normalizedValues.description || '',
    remark: { dispute: '', coordination: normalizedValues.remark_coordination || '' },
    customFields,
  }
}

async function saveProject() {
  if (!formValues.project_name?.trim()) {
    MessagePlugin.warning('项目名称不能为空')
    return
  }
  await store.saveProject({ ...valuesToProject(), operator: authStore.displayName || '前端用户' } as Partial<AuditProject>)
  MessagePlugin.success('项目已保存')
  detailVisible.value = false
  editing.value = false
}

async function moveProject(stageCode: AuditStageCode) {
  if (!store.selectedProject || store.selectedProject.stage === stageCode) return
  await store.moveProject(store.selectedProject, stageCode, authStore.displayName || '前端用户')
  MessagePlugin.success('进度已更新')
}

function attachmentName(file: AuditProjectAttachment) {
  return file.originalName || file.file_name || '-'
}

function attachmentType(file: AuditProjectAttachment) {
  return file.fileExt || file.mimeType || file.file_type || '未知类型'
}

function attachmentUploader(file: AuditProjectAttachment) {
  return file.uploadedByName || file.uploadedBy || file.uploaded_by || '-'
}

function attachmentCreatedAt(file: AuditProjectAttachment) {
  return (file.createdAt || file.uploaded_at || '').replace('T', ' ') || '-'
}

function formatFileSize(size = 0) {
  if (!size) return '0 B'
  if (size >= 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  if (size >= 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${size} B`
}

function triggerAttachmentSelect() {
  attachmentInputRef.value?.click()
}

async function handleAttachmentUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  attachmentUploading.value = true
  try {
    await store.uploadAttachment(file)
    MessagePlugin.success('附件已上传')
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '附件上传失败')
  } finally {
    attachmentUploading.value = false
    input.value = ''
  }
}

function previewKind(file: AuditProjectAttachment) {
  const mime = file.mimeType || file.file_type || ''
  const ext = file.fileExt || ''
  if (mime.startsWith('image/')) return 'image'
  if (mime === 'application/pdf' || ext === '.pdf') return 'pdf'
  if (mime.startsWith('video/')) return 'video'
  if (mime.startsWith('audio/')) return 'audio'
  if (mime.startsWith('text/') || ['.txt', '.csv', '.json', '.log', '.md', '.xml', '.yml', '.yaml'].includes(ext)) return 'text'
  return 'unsupported'
}

async function openAttachmentPreview(file: AuditProjectAttachment) {
  closeAttachmentPreview()
  attachmentPreview.visible = true
  attachmentPreview.loading = true
  attachmentPreview.title = attachmentName(file)
  attachmentPreview.hint = `${attachmentType(file)} · ${formatFileSize(file.fileSize)}`
  attachmentPreview.kind = previewKind(file)
  try {
    if (attachmentPreview.kind === 'unsupported') {
      attachmentPreview.error = '该文件类型暂不支持在线预览，请下载查看'
      return
    }
    const blob = await fetchAttachmentPreviewBlob(file.id)
    if (attachmentPreview.kind === 'text') {
      attachmentPreview.text = await blob.text()
    } else {
      attachmentPreview.url = URL.createObjectURL(blob)
    }
  } catch (err) {
    attachmentPreview.kind = 'unsupported'
    attachmentPreview.error = err instanceof Error ? err.message : '预览失败'
  } finally {
    attachmentPreview.loading = false
  }
}

function closeAttachmentPreview() {
  if (attachmentPreview.url) URL.revokeObjectURL(attachmentPreview.url)
  attachmentPreview.visible = false
  attachmentPreview.loading = false
  attachmentPreview.title = ''
  attachmentPreview.hint = ''
  attachmentPreview.kind = ''
  attachmentPreview.url = ''
  attachmentPreview.text = ''
  attachmentPreview.error = ''
}

async function downloadAttachment(file: AuditProjectAttachment) {
  try {
    const blob = await fetchAttachmentDownloadBlob(file.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = attachmentName(file)
    link.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '下载失败')
  }
}

async function removeAttachment(file: AuditProjectAttachment) {
  if (!window.confirm(`确认删除附件「${attachmentName(file)}」？`)) return
  try {
    await store.removeAttachment(file.id)
    MessagePlugin.success('附件已删除')
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '删除失败')
  }
}

function ganttStyle(project: AuditProject) {
  const dates = store.projects.flatMap((item) => [item.deadline.submitDate, item.deadline.auditDeadline]).filter(Boolean).sort()
  const min = dates[0] || new Date().toISOString().slice(0, 10)
  const max = dates[dates.length - 1] || min
  const total = Math.max(new Date(max).getTime() - new Date(min).getTime(), 86400000)
  const start = Math.max(new Date(project.deadline.submitDate || min).getTime() - new Date(min).getTime(), 0)
  const end = Math.max(new Date(project.deadline.auditDeadline || max).getTime() - new Date(min).getTime(), start + 86400000)
  const left = Math.max(0, Math.min(95, (start / total) * 100))
  const width = Math.max(6, Math.min(100 - left, ((end - start) / total) * 100))
  const color = store.meta.stages.find((stage) => stage.code === project.stage)?.color || '#3366FF'
  return { left: `${left}%`, width: `${width}%`, backgroundColor: color }
}

async function logout() {
  await authStore.logout()
  MessagePlugin.success('已退出')
}
</script>

<style scoped>
.audit-shell {
  min-height: 100vh;
  background: var(--bg-page);
  color: var(--text-primary);
}
.audit-shell--embedded {
  min-height: auto;
  background: transparent;
}

.audit-header {
  min-height: 60px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-5);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-elevated);
}
.audit-header--embedded {
  height: auto;
  justify-content: flex-end;
  padding: var(--space-3);
  background: transparent;
  border: 0;
  box-shadow: none;
}

.brand, .header-actions, .segmented, .card-title-row, .card-footer, .detail-status, .drawer-actions, .stage-actions, .section-title-row, .attachment-actions {
  display: flex;
  align-items: center;
}

.brand { gap: var(--space-3); min-width: 260px; }
.brand-mark {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  background: var(--color-brand-ink);
  color: var(--text-on-brand);
}
.brand h1 { font-size: var(--text-xl); margin: 0; }
.brand p { font-size: var(--text-xs); color: var(--text-secondary); margin: 0; }
.header-actions { gap: var(--space-2); flex-wrap: wrap; justify-content: flex-end; }

.segmented {
  border: 1px solid var(--border-color);
  background: var(--bg-muted);
  border-radius: var(--radius-md);
  overflow: hidden;
}
.segmented button {
  height: 32px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  border-right: 1px solid var(--border-color);
  padding: 0 10px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
}
.segmented button:last-child { border-right: 0; }
.segmented button.active { background: var(--color-brand-500); color: var(--text-on-brand); }

.audit-main { padding: var(--space-5); }
.audit-shell--embedded .audit-main { padding: 0; }
.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(176px, 1fr));
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.summary-card {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-4);
  box-shadow: var(--shadow-elevated);
}
.summary-card span, .summary-card em { display: block; color: var(--text-secondary); font-size: var(--text-xs); font-style: normal; }
.summary-card strong { display: block; margin: 4px 0; font-size: var(--text-2xl); }

.toolbar {
  display: grid;
  grid-template-columns: minmax(260px, 1.8fr) repeat(auto-fit, minmax(132px, 1fr));
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-elevated);
  margin-bottom: var(--space-4);
  align-items: center;
}
.native-input, .native-select, .native-textarea {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: #fff;
  color: var(--text-primary);
  min-height: 34px;
  padding: 6px 10px;
  font: inherit;
  outline: none;
}
.native-input:focus,
.native-select:focus,
.native-textarea:focus {
  border-color: var(--color-brand-500);
  box-shadow: 0 0 0 2px var(--color-brand-50);
}
.native-textarea { resize: vertical; min-height: 76px; }
.keyword { min-width: 260px; flex: 1; }
.small-filter { width: 120px; }
.date-filter { width: 144px; }
.layout-select { width: 86px; }
.check-filter {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 var(--space-2);
  white-space: nowrap;
  font-size: var(--text-sm);
  color: var(--text-secondary);
}
.error-alert { margin-bottom: var(--space-4); }
.center-state { min-height: 360px; display: grid; place-items: center; }

.kanban-board {
  display: grid;
  grid-template-columns: repeat(5, minmax(260px, 1fr));
  gap: var(--space-3);
  overflow-x: auto;
  padding-bottom: var(--space-2);
}
.kanban-column {
  min-width: 260px;
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-elevated);
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 238px);
  overflow: hidden;
}
.column-head {
  border-top: 4px solid;
  border-bottom: 1px solid var(--border-color);
  padding: var(--space-3);
  display: flex;
  justify-content: space-between;
  gap: var(--space-2);
}
.column-head h2 { font-size: var(--text-md); margin: 0; }
.column-head span { font-size: var(--text-xs); color: var(--text-tertiary); }
.column-head strong { font-size: var(--text-xl); }
.column-body { padding: var(--space-2); overflow-y: auto; display: flex; flex-direction: column; gap: var(--space-2); }

.project-card {
  width: 100%;
  text-align: left;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: #fff;
  padding: var(--space-3);
  cursor: pointer;
  transition: border-color var(--duration-fast), box-shadow var(--duration-fast), transform var(--duration-fast);
}
.project-card:hover {
  border-color: var(--color-brand-500);
  background: #fff;
  box-shadow: var(--shadow-elevated);
  transform: translateY(-1px);
}
.card-title-row { justify-content: space-between; gap: var(--space-2); align-items: flex-start; }
.card-title-row strong { font-size: var(--text-sm); line-height: 1.45; }
.priority {
  padding: 1px 6px;
  font-size: 11px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
}
.priority-S0 { color: #E34D59; border-color: #E34D59; }
.priority-S1 { color: #ED7B2F; border-color: #ED7B2F; }
.card-meta, .card-fields span, .card-footer { font-size: var(--text-xs); color: var(--text-secondary); }
.card-meta { margin-top: 6px; }
.card-fields { display: grid; gap: 3px; margin-top: var(--space-2); }
.card-footer { justify-content: space-between; margin-top: var(--space-2); padding-top: var(--space-2); border-top: 1px solid var(--border-color); }
.overdue { color: var(--color-danger); font-weight: 600; }
.empty-column { padding: var(--space-5); text-align: center; color: var(--text-tertiary); font-size: var(--text-sm); }

.gantt-view, .table-view {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-elevated);
  overflow: auto;
}
.gantt-head, .gantt-row {
  display: grid;
  grid-template-columns: 320px minmax(560px, 1fr);
}
.gantt-head { background: var(--bg-muted); color: var(--text-secondary); font-size: var(--text-xs); border-bottom: 1px solid var(--border-color); }
.gantt-head span, .gantt-name { padding: var(--space-3); }
.gantt-row { border-bottom: 1px solid var(--border-color); cursor: pointer; }
.gantt-row:hover { background: var(--bg-muted); }
.gantt-name strong, .gantt-name span { display: block; }
.gantt-name span { font-size: var(--text-xs); color: var(--text-secondary); margin-top: 3px; }
.gantt-track { position: relative; min-height: 54px; margin: 0 var(--space-3); border-left: 1px solid var(--border-color); border-right: 1px solid var(--border-color); }
.gantt-bar {
  position: absolute;
  top: 14px;
  height: 26px;
  color: var(--text-on-brand);
  font-size: 11px;
  display: flex;
  align-items: center;
  padding: 0 8px;
  overflow: hidden;
  white-space: nowrap;
}

.table-view table { width: 100%; border-collapse: collapse; min-width: 980px; }
.table-view th, .table-view td { border-bottom: 1px solid var(--border-color); padding: 10px; text-align: left; font-size: var(--text-sm); }
.table-view th { background: var(--bg-muted); color: var(--text-secondary); font-weight: 600; }
.link-button { border: 0; background: transparent; color: var(--color-brand-500); cursor: pointer; }
.pager {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-3);
  padding: var(--space-3);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.drawer {
  position: fixed;
  inset: 0;
  background: rgba(17, 24, 39, 0.22);
  display: flex;
  justify-content: flex-end;
  z-index: 1000;
}
.drawer-panel {
  width: min(720px, 100vw);
  height: 100%;
  overflow-y: auto;
  background: var(--bg-surface);
  border-left: 1px solid var(--border-color-strong);
  box-shadow: var(--shadow-overlay);
}
.drawer-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-5);
  border-bottom: 1px solid var(--border-color);
}
.drawer-head h2 { font-size: var(--text-xl); margin: 0; }
.drawer-head p { font-size: var(--text-sm); color: var(--text-secondary); margin: 3px 0 0; }
.icon-button {
  width: 32px;
  height: 32px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: #fff;
  cursor: pointer;
}
.project-form, .detail-view { padding: var(--space-5); }
.project-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-4); }
.form-field { display: grid; gap: 6px; font-size: var(--text-sm); color: var(--text-secondary); }
.form-field b { color: var(--color-danger); margin-left: 2px; }
.custom-option { display: flex; gap: var(--space-2); }
.drawer-actions { grid-column: 1 / -1; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-2); }

.detail-status { justify-content: space-between; padding-bottom: var(--space-4); border-bottom: 1px solid var(--border-color); }
.stage-pill { color: var(--color-brand-600); background: var(--color-brand-50); border: 1px solid var(--color-brand-100); padding: 3px 8px; }
.detail-grid { display: grid; grid-template-columns: 120px 1fr; gap: 10px 16px; margin: var(--space-5) 0; }
.detail-grid dt { color: var(--text-secondary); font-size: var(--text-sm); }
.detail-grid dd { margin: 0; }
.progress-box, .stage-history, .attachment-box, .log-box { border-top: 1px solid var(--border-color); padding-top: var(--space-4); margin-top: var(--space-4); }
.progress-box h3, .stage-history h3, .attachment-box h3, .log-box h3 { font-size: var(--text-md); margin: 0 0 var(--space-3); }
.section-title-row { justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-3); }
.section-title-row h3 { margin: 0; }
.stage-actions { gap: var(--space-2); flex-wrap: wrap; }
.stage-actions button {
  border: 1px solid var(--border-color-strong);
  background: #fff;
  padding: 6px 10px;
  cursor: pointer;
}
.stage-actions button.active { background: var(--color-brand-500); border-color: var(--color-brand-500); color: var(--text-on-brand); }
.stage-history p, .attachment-box p, .log-box p { font-size: var(--text-xs); color: var(--text-secondary); margin: 0 0 6px; }
.attachment-input { display: none; }
.attachment-list { display: grid; gap: var(--space-2); }
.attachment-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-3);
  align-items: center;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-page);
}
.attachment-main { display: grid; gap: 4px; min-width: 0; }
.attachment-main strong {
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.attachment-main span { color: var(--text-secondary); font-size: var(--text-xs); }
.attachment-actions { gap: 6px; }
.attachment-actions button {
  border: 1px solid var(--border-color);
  background: #fff;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: var(--text-xs);
  padding: 5px 8px;
}
.attachment-actions button:disabled { cursor: not-allowed; opacity: .45; }
.attachment-actions .danger-text { color: var(--color-danger); }
.preview-mask {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: var(--space-5);
  background: rgba(15, 23, 42, .48);
}
.preview-panel {
  width: min(960px, 92vw);
  max-height: 88vh;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  background: var(--bg-surface);
  border: 1px solid var(--border-color-strong);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-overlay);
  overflow: hidden;
}
.preview-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-4);
  border-bottom: 1px solid var(--border-color);
}
.preview-head h3 { margin: 0; font-size: var(--text-lg); }
.preview-head p { margin: 4px 0 0; color: var(--text-secondary); font-size: var(--text-xs); }
.preview-body {
  min-height: 360px;
  overflow: auto;
  padding: var(--space-4);
  background: #f8fafc;
}
.preview-body img, .preview-body video {
  max-width: 100%;
  max-height: 68vh;
  display: block;
  margin: 0 auto;
}
.preview-body iframe {
  width: 100%;
  min-height: 68vh;
  border: 0;
  background: #fff;
}
.preview-body audio { width: 100%; }
.preview-body pre {
  min-height: 320px;
  margin: 0;
  padding: var(--space-4);
  overflow: auto;
  background: #fff;
  color: var(--text-primary);
  font-size: var(--text-sm);
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}
.preview-message { color: var(--text-secondary); font-size: var(--text-sm); }

.layout-vertical .kanban-board { grid-template-columns: 1fr; }
.layout-vertical .kanban-column { max-height: none; }
.layout-compact .audit-main { padding: var(--space-3); }
.layout-compact .summary-grid { grid-template-columns: repeat(4, 1fr); gap: var(--space-2); }
.layout-compact .project-card { padding: var(--space-2); }
.layout-bigscreen .audit-header { height: 72px; }
.layout-bigscreen .summary-card strong { font-size: var(--text-3xl); }
.layout-bigscreen .kanban-column { max-height: calc(100vh - 260px); }

@media (max-width: 960px) {
  .audit-header { height: auto; align-items: flex-start; padding: var(--space-3); flex-direction: column; }
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .toolbar { grid-template-columns: repeat(2, minmax(180px, 1fr)); }
  .keyword { min-width: 100%; grid-column: 1 / -1; }
  .kanban-board { grid-template-columns: repeat(5, 260px); }
  .project-form { grid-template-columns: 1fr; }
  .attachment-item { grid-template-columns: 1fr; }
  .attachment-actions { flex-wrap: wrap; }
}

@media (max-width: 640px) {
  .summary-grid { grid-template-columns: 1fr; }
  .toolbar { grid-template-columns: 1fr; }
  .keyword { min-width: 100%; }
  .small-filter, .date-filter { width: 100%; }
  .segmented span { display: none; }
  .gantt-head, .gantt-row { grid-template-columns: 220px 520px; }
}
</style>

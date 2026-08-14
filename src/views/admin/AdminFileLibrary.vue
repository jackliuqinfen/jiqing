<template>
  <div class="file-library">
    <PageHeader title="项目资料中心" description="统一归集项目资料与审计证据，按项目、类型和阶段快速筛选">
      <template #meta>
        <ATag variant="light" theme="primary">共 {{ filteredFiles.length }} 个文件</ATag>
        <ATag variant="light">项目 {{ projectGroups.length }} 组</ATag>
        <ATag v-if="keyword || fileType || selectedProject || selectedStage || uploader" variant="light">已应用筛选</ATag>
      </template>
      <template #actions>
        <AButton v-if="isDesktop" variant="outline" @click="syncDialogVisible = true">
          <template #icon><AIcon name="folder" /></template>
          本地同步
        </AButton>
        <AButton theme="primary" @click="openUploadDialog">
          <template #icon><AIcon name="upload" /></template>
          上传资料
        </AButton>
        <AButton variant="outline" :loading="loading" @click="loadFiles">
          <template #icon><AIcon name="refresh" /></template>
          刷新
        </AButton>
      </template>
    </PageHeader>

    <div class="library-toolbar">
      <AInput v-model="keyword" placeholder="搜索项目名称或文件名" clearable :style="{ width: '280px' }">
        <template #prefix-icon><AIcon name="search" /></template>
      </AInput>
      <ASelect
        v-model="fileType"
        placeholder="文件类型"
        clearable
        :style="{ width: '150px' }"
        :options="fileTypeOptions"
      />
      <ASelect v-model="selectedStage" placeholder="审计阶段" clearable :style="{ width: '170px' }" :options="stageOptions" />
      <AInput v-model="uploader" placeholder="上传人" clearable :style="{ width: '160px' }" />
      <span class="library-count">共 {{ filteredFiles.length }} 个文件</span>
    </div>

    <StatePanel
      v-if="loading && files.length === 0"
      state="loading"
      title="正在加载项目资料中心"
      description="系统正在整理各项目附件，请稍候。"
    />

    <StatePanel
      v-else-if="fetchError"
      state="error"
      title="项目资料中心加载失败"
      description="文件列表暂时没有读取成功，可能是网络异常或附件服务繁忙。你可以重试，或联系管理员检查上传服务。"
    >
      <template #actions>
        <AButton theme="primary" :loading="loading" @click="loadFiles">
          <template #icon><AIcon name="refresh" /></template>
          重新加载
        </AButton>
      </template>
    </StatePanel>

    <StatePanel
      v-else-if="filteredFiles.length === 0"
      state="empty"
      title="未找到文件"
      :description="keyword || fileType || selectedProject || selectedStage || uploader ? '请调整筛选条件后再试，或清除筛选查看全部资料。' : '当前还没有归集到项目资料或审计证据。'"
    >
      <template #actions>
        <AButton theme="primary" @click="openUploadDialog">
          <template #icon><AIcon name="upload" /></template>
          上传资料
        </AButton>
        <AButton v-if="keyword || fileType || selectedProject || selectedStage || uploader" variant="outline" @click="clearFilters">清除筛选</AButton>
        <AButton theme="primary" :loading="loading" @click="loadFiles">
          <template #icon><AIcon name="refresh" /></template>
          重新加载
        </AButton>
      </template>
    </StatePanel>

    <template v-else>
      <div class="summary-grid">
        <div class="summary-item">
          <span>项目数</span>
          <strong>{{ projectGroups.length }}</strong>
        </div>
        <div class="summary-item">
          <span>文件总量</span>
          <strong>{{ filteredFiles.length }}</strong>
        </div>
        <div class="summary-item">
          <span>存储占用</span>
          <strong>{{ formatFileSize(totalSize) }}</strong>
        </div>
        <div class="summary-item">
          <span>可预览</span>
          <strong>{{ previewableCount }}</strong>
        </div>
      </div>

      <div class="library-layout">
        <section class="group-panel">
          <div class="panel-head">
            <strong>项目归类</strong>
            <span>{{ projectGroups.length }} 组</span>
          </div>
          <button
            type="button"
            class="group-item"
            :class="{ 'group-item--active': selectedProject === '' }"
            @click="selectedProject = ''"
          >
            <span>全部项目</span>
            <strong>{{ files.length }}</strong>
          </button>
          <button
            v-for="group in projectGroups"
            :key="group.name"
            type="button"
            class="group-item"
            :class="{ 'group-item--active': selectedProject === group.name }"
            @click="selectedProject = group.name"
          >
            <span>{{ group.name }}</span>
            <strong>{{ group.count }}</strong>
          </button>
        </section>

        <section class="file-panel">
          <div class="type-strip">
            <button
              v-for="type in typeGroups"
              :key="type.value"
              type="button"
              class="type-pill"
              :class="{ 'type-pill--active': fileType === type.value }"
              @click="fileType = fileType === type.value ? '' : type.value"
            >
              <span>{{ type.label }}</span>
              <strong>{{ type.count }}</strong>
            </button>
          </div>

          <ATable
            :data="filteredFiles"
            :columns="tableColumns"
            row-key="id"
            :loading="loading"
            :bordered="true"
            hover
            @row-contextmenu="openFileContextMenu"
          >
          <template #file="{ row }">
            <div class="file-cell">
              <AIcon :name="fileIcon(row)" />
              <div>
                <strong>{{ attachmentName(row) }}</strong>
                <span>{{ typeLabel(row) }} · {{ formatFileSize(row.fileSize) }}</span>
              </div>
            </div>
          </template>
          <template #project="{ row }">
            <div class="project-cell">
              <strong>{{ row.projectName || '未关联项目' }}</strong>
              <span>{{ row.projectCode || row.managerName || '—' }}</span>
            </div>
          </template>
          <template #stage="{ row }">
            <div class="uploaded-cell">
              <strong>{{ row.stageLabel || '项目资料' }}</strong>
              <span>{{ row.sourceLabel }} · {{ row.evidenceStatus }}</span>
            </div>
          </template>
          <template #uploaded="{ row }">
            <div class="uploaded-cell">
              <strong>{{ row.uploadedByName || row.uploadedBy || '-' }}</strong>
              <span>{{ formatDateTime(row.uploadedAt || row.createdAt || row.uploaded_at || '') }}</span>
            </div>
          </template>
          <template #actions="{ row }">
            <div class="action-cell">
              <button type="button" :disabled="!row.canPreview" @click="openPreview(row)">预览</button>
              <button type="button" @click="downloadFile(row)">下载</button>
            </div>
          </template>
          </ATable>
        </section>
      </div>
    </template>

    <div v-if="preview.visible" class="preview-mask">
      <div class="preview-panel">
        <div class="preview-head">
          <div>
            <h3>{{ preview.title }}</h3>
            <p>{{ preview.hint }}</p>
          </div>
          <button type="button" @click="closePreview">关闭</button>
        </div>
        <div class="preview-body">
          <p v-if="preview.loading" class="preview-message">正在加载预览...</p>
          <img v-else-if="preview.kind === 'image'" :src="preview.url" alt="附件预览" />
          <iframe v-else-if="preview.kind === 'pdf'" :src="preview.url" title="PDF 预览" />
          <pre v-else-if="preview.kind === 'text'">{{ preview.text }}</pre>
          <video v-else-if="preview.kind === 'video'" :src="preview.url" controls />
          <audio v-else-if="preview.kind === 'audio'" :src="preview.url" controls />
          <p v-else class="preview-message">{{ preview.error || '该文件类型暂不支持在线预览，请下载查看' }}</p>
        </div>
      </div>
    </div>

    <AModal
      v-model:visible="uploadDialog.visible"
      header="上传项目资料"
      :confirm-btn="{ content: '开始上传', loading: uploadDialog.saving }"
      width="640px"
      :mask-closable="false"
      @confirm="saveUpload"
      @cancel="closeUploadDialog"
    >
      <AForm :model="uploadDialog" layout="vertical" class="upload-form">
        <AFormItem field="projectId" label="选择项目" required>
          <ASelect
            v-model="uploadDialog.projectId"
            :options="projectOptions"
            placeholder="搜索或选择项目"
            allow-search
            allow-clear
            :loading="projectsLoading"
          />
        </AFormItem>
        <AFormItem field="categoryKey" label="资料类型" required>
          <ASelect
            v-model="uploadDialog.categoryKey"
            :options="categoryOptions"
            placeholder="请选择资料类型"
            allow-search
            allow-clear
          />
        </AFormItem>
        <AFormItem field="displayName" label="资料名称" required>
          <AInput v-model="uploadDialog.displayName" placeholder="请输入资料名称，如：合同文件、竣工验收证明" allow-clear />
        </AFormItem>
        <AFormItem field="file" label="文件" required>
          <input ref="uploadInputRef" class="native-file" type="file" @change="onUploadFilePicked" />
        </AFormItem>
        <p class="dialog-hint">同一项目、同一资料类型、同一资料名称重复上传时，系统会按新版本处理。</p>
      </AForm>
    </AModal>

    <DesktopSyncDialog
      v-if="isDesktop"
      v-model:visible="syncDialogVisible"
    />

    <ObjectContextMenu
      v-model:visible="fileContextMenu.visible"
      :x="fileContextMenu.x"
      :y="fileContextMenu.y"
      :items="fileContextMenuItems"
      @select="handleFileContextAction"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { TableData } from '@arco-design/web-vue'
import {
  fetchAttachmentDownloadBlob,
  fetchAttachmentPreviewBlob,
} from '@/api/audit'
import {
  fetchProjectEvidence,
  fetchProjectFileDownloadBlob,
  fetchProjectFilePreviewBlob,
  fetchProjectMeta,
  fetchProjectRecords,
  uploadProjectFile,
} from '@/api/projects'
import { MessagePlugin } from '@/ui/message'
import type { ProjectEvidenceFile, ProjectMeta, ProjectRecord } from '@/types'
import { auditStageOptions } from '@/utils/businessDictionaries'
import DesktopSyncDialog from '@/components/desktop/DesktopSyncDialog.vue'
import PageHeader from '@/components/PageHeader.vue'
import StatePanel from '@/components/StatePanel.vue'
import ObjectContextMenu, { type ObjectContextMenuItem } from '@/components/workspace/ObjectContextMenu.vue'
import { useDesktopClient } from '@/composables/useDesktopClient'

const route = useRoute()
const router = useRouter()
const { isDesktop } = useDesktopClient()
const MATERIALS_WORKSPACE_STATE_KEY = 'materials-workspace-state-v1'
const tableColumns = [
  { colKey: 'file', title: '文件', width: 320 },
  { colKey: 'project', title: '项目名称' },
  { colKey: 'stage', title: '归属', width: 180 },
  { colKey: 'uploaded', title: '上传信息', width: 190 },
  { colKey: 'actions', title: '操作', width: 130 },
]

const fileTypeOptions = [
  { label: '图片', value: 'image' },
  { label: 'PDF', value: 'pdf' },
  { label: '文本', value: 'text' },
  { label: '音频', value: 'audio' },
  { label: '视频', value: 'video' },
  { label: '其他', value: 'other' },
]

const stageOptions = auditStageOptions.map(({ label, value }) => ({ label, value }))

const files = ref<ProjectEvidenceFile[]>([])
const projects = ref<ProjectRecord[]>([])
const meta = reactive<ProjectMeta>({
  categories: [],
  projectStatuses: [],
  settlementStatuses: [],
  auditStages: [],
})
const loading = ref(false)
const projectsLoading = ref(false)
const fetchError = ref('')
const keyword = ref('')
const fileType = ref('')
const selectedProject = ref('')
const selectedStage = ref('')
const uploader = ref('')
const uploadInputRef = ref<HTMLInputElement | null>(null)
const syncDialogVisible = ref(false)
const restoringWorkspace = ref(false)

const uploadDialog = reactive({
  visible: false,
  saving: false,
  projectId: '',
  categoryKey: '',
  displayName: '',
  file: null as File | null,
})

const preview = reactive({
  visible: false,
  loading: false,
  title: '',
  hint: '',
  kind: '',
  url: '',
  text: '',
  error: '',
})

const fileContextMenu = reactive({
  visible: false,
  x: 0,
  y: 0,
  file: null as ProjectEvidenceFile | null,
})

const filteredFiles = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  const uploaderKeyword = uploader.value.trim().toLowerCase()
  return files.value.filter((file) => {
    if (selectedProject.value && (file.projectName || '未关联项目') !== selectedProject.value) return false
    if (selectedStage.value && file.stage !== selectedStage.value) return false
    if (fileType.value && fileCategory(file) !== fileType.value) return false
    if (uploaderKeyword && ![file.uploadedByName, file.uploadedBy].join(' ').toLowerCase().includes(uploaderKeyword)) return false
    if (!kw) return true
    return [attachmentName(file), file.projectName, file.projectCode, file.managerName, typeLabel(file)]
      .join(' ')
      .toLowerCase()
      .includes(kw)
  })
})

const projectGroups = computed(() => {
  const map = new Map<string, number>()
  files.value.forEach((file) => {
    const name = file.projectName || '未关联项目'
    map.set(name, (map.get(name) || 0) + 1)
  })
  return Array.from(map.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'zh-CN'))
})

const typeGroups = computed(() => {
  const map = new Map<string, number>()
  files.value.forEach((file) => map.set(fileCategory(file), (map.get(fileCategory(file)) || 0) + 1))
  return fileTypeOptions.map((option) => ({
    ...option,
    count: map.get(String(option.value)) || 0,
  }))
})

const totalSize = computed(() => filteredFiles.value.reduce((sum, file) => sum + Number(file.fileSize || 0), 0))
const previewableCount = computed(() => filteredFiles.value.filter((file) => file.canPreview).length)
const projectOptions = computed(() => projects.value.map((project) => ({
  label: `${project.projectName}（${project.projectCode || '未编号'}）`,
  value: project.id,
})))
const categoryOptions = computed(() => meta.categories.map((category) => ({
  label: category.categoryName,
  value: category.categoryKey,
})))

const fileContextMenuItems = computed<ObjectContextMenuItem[]>(() => {
  const file = fileContextMenu.file
  if (!file) return []
  return [
    { key: 'preview', label: '预览资料', icon: 'eye', disabled: !file.canPreview },
    { key: 'download', label: '下载到本地', icon: 'rollback' },
    { key: 'copy-name', label: '复制文件名', icon: 'file-copy' },
    { key: 'divider-1', divider: true },
    { key: 'open-project', label: '打开所属项目', icon: 'task', disabled: !file.projectId },
  ]
})

watch([keyword, fileType, selectedStage, uploader], () => {
  if (restoringWorkspace.value) return
  selectedProject.value = ''
})

watch([keyword, fileType, selectedProject, selectedStage, uploader], saveMaterialsWorkspaceState)

watch(
  () => route.query.fileType,
  (value) => {
    fileType.value = typeof value === 'string' ? value : ''
  },
  { immediate: true },
)

watch(
  [() => route.query.desktopSync, isDesktop],
  ([request, desktop]) => {
    if (desktop && typeof request === 'string' && request.length > 0) {
      syncDialogVisible.value = true
    }
  },
  { immediate: true },
)

function clearFilters() {
  keyword.value = ''
  fileType.value = ''
  selectedProject.value = ''
  selectedStage.value = ''
  uploader.value = ''
}

function saveMaterialsWorkspaceState() {
  const scrollContainer = document.querySelector<HTMLElement>('.system-content')
  window.sessionStorage.setItem(MATERIALS_WORKSPACE_STATE_KEY, JSON.stringify({
    keyword: keyword.value,
    fileType: fileType.value,
    selectedProject: selectedProject.value,
    selectedStage: selectedStage.value,
    uploader: uploader.value,
    scrollTop: scrollContainer?.scrollTop || 0,
  }))
}

function restoreMaterialsWorkspaceState() {
  try {
    const raw = window.sessionStorage.getItem(MATERIALS_WORKSPACE_STATE_KEY)
    if (!raw) return 0
    const state = JSON.parse(raw) as Record<string, unknown>
    restoringWorkspace.value = true
    keyword.value = typeof state.keyword === 'string' ? state.keyword : ''
    fileType.value = typeof state.fileType === 'string' ? state.fileType : ''
    selectedProject.value = typeof state.selectedProject === 'string' ? state.selectedProject : ''
    selectedStage.value = typeof state.selectedStage === 'string' ? state.selectedStage : ''
    uploader.value = typeof state.uploader === 'string' ? state.uploader : ''
    return Math.max(0, Number(state.scrollTop || 0))
  } catch {
    return 0
  } finally {
    nextTick(() => {
      restoringWorkspace.value = false
    })
  }
}

function attachmentName(file: ProjectEvidenceFile) {
  return file.displayName || file.originalName || file.file_name || '-'
}

function fileCategory(file: ProjectEvidenceFile) {
  const mime = file.mimeType || file.file_type || ''
  const ext = (file.fileExt || '').toLowerCase()
  if (mime.startsWith('image/')) return 'image'
  if (mime === 'application/pdf' || ext === '.pdf') return 'pdf'
  if (mime.startsWith('text/') || ['.txt', '.csv', '.md', '.json', '.xml', '.log'].includes(ext)) return 'text'
  if (mime.startsWith('audio/')) return 'audio'
  if (mime.startsWith('video/')) return 'video'
  return 'other'
}

function typeLabel(file: ProjectEvidenceFile) {
  const option = fileTypeOptions.find((item) => item.value === fileCategory(file))
  return option?.label || file.mimeType || file.file_type || '其他'
}

function fileIcon(file: ProjectEvidenceFile) {
  const category = fileCategory(file)
  if (category === 'image') return 'image'
  if (category === 'text') return 'file-copy'
  if (category === 'audio' || category === 'video') return 'play-circle'
  return 'file-paste'
}

function previewKind(file: ProjectEvidenceFile) {
  const category = fileCategory(file)
  if (['image', 'pdf', 'text', 'audio', 'video'].includes(category)) return category
  return 'unsupported'
}

function formatFileSize(size: number) {
  if (!size) return '0 B'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function formatDateTime(iso: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function loadFiles() {
  loading.value = true
  fetchError.value = ''
  try {
    files.value = await fetchProjectEvidence({
      keyword: keyword.value,
      fileType: fileType.value,
      stage: selectedStage.value,
      uploader: uploader.value,
    })
  } catch (err) {
    fetchError.value = err instanceof Error ? err.message : '获取项目资料中心失败'
    MessagePlugin.error(fetchError.value)
  } finally {
    loading.value = false
  }
}

async function loadUploadOptions() {
  projectsLoading.value = true
  try {
    const [metaResult, projectResult] = await Promise.all([
      fetchProjectMeta(),
      fetchProjectRecords({ page: 1, pageSize: 500, sort: 'updatedAt' }),
    ])
    Object.assign(meta, metaResult)
    projects.value = projectResult.data
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '上传选项加载失败')
  } finally {
    projectsLoading.value = false
  }
}

function resetUploadDialog() {
  uploadDialog.projectId = ''
  uploadDialog.categoryKey = ''
  uploadDialog.displayName = ''
  uploadDialog.file = null
  if (uploadInputRef.value) uploadInputRef.value.value = ''
}

async function openUploadDialog() {
  if (!projects.value.length || !meta.categories.length) {
    await loadUploadOptions()
  }
  resetUploadDialog()
  uploadDialog.visible = true
}

function closeUploadDialog() {
  if (uploadDialog.saving) return
  uploadDialog.visible = false
  resetUploadDialog()
}

function onUploadFilePicked(event: Event) {
  const input = event.target as HTMLInputElement
  uploadDialog.file = input.files?.[0] || null
  if (!uploadDialog.displayName && uploadDialog.file) {
    uploadDialog.displayName = uploadDialog.file.name.replace(/\.[^.]+$/, '')
  }
}

async function saveUpload() {
  if (!uploadDialog.projectId) {
    MessagePlugin.error('请先选择项目')
    return
  }
  if (!uploadDialog.categoryKey) {
    MessagePlugin.error('请选择资料类型')
    return
  }
  if (!uploadDialog.displayName.trim()) {
    MessagePlugin.error('请填写资料名称')
    return
  }
  if (!uploadDialog.file) {
    MessagePlugin.error('请选择要上传的文件')
    return
  }
  uploadDialog.saving = true
  try {
    await uploadProjectFile(uploadDialog.projectId, {
      categoryKey: uploadDialog.categoryKey,
      displayName: uploadDialog.displayName.trim(),
      file: uploadDialog.file,
    })
    const project = projects.value.find((item) => item.id === uploadDialog.projectId)
    MessagePlugin.success('资料已上传')
    uploadDialog.visible = false
    resetUploadDialog()
    await loadFiles()
    if (project?.projectName) selectedProject.value = project.projectName
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '资料上传失败')
  } finally {
    uploadDialog.saving = false
  }
}

async function openPreview(file: ProjectEvidenceFile) {
  closePreview()
  preview.visible = true
  preview.loading = true
  preview.title = attachmentName(file)
  preview.hint = `${file.projectName || '未关联项目'} · ${typeLabel(file)} · ${formatFileSize(file.fileSize)}`
  preview.kind = previewKind(file)
  try {
    if (preview.kind === 'unsupported') {
      preview.error = '该文件类型暂不支持在线预览，请下载查看'
      return
    }
    const blob = file.source === 'project' ? await fetchProjectFilePreviewBlob(file.id) : await fetchAttachmentPreviewBlob(file.id)
    if (preview.kind === 'text') preview.text = await blob.text()
    else preview.url = URL.createObjectURL(blob)
  } catch (err) {
    preview.kind = 'unsupported'
    preview.error = err instanceof Error ? err.message : '预览失败'
  } finally {
    preview.loading = false
  }
}

function closePreview() {
  if (preview.url) URL.revokeObjectURL(preview.url)
  preview.visible = false
  preview.loading = false
  preview.title = ''
  preview.hint = ''
  preview.kind = ''
  preview.url = ''
  preview.text = ''
  preview.error = ''
}

async function downloadFile(file: ProjectEvidenceFile) {
  try {
    const blob = file.source === 'project' ? await fetchProjectFileDownloadBlob(file.id) : await fetchAttachmentDownloadBlob(file.id)
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

function openFileContextMenu(file: TableData, event: Event) {
  const pointer = event as MouseEvent
  pointer.preventDefault()
  fileContextMenu.file = file as ProjectEvidenceFile
  fileContextMenu.x = pointer.clientX
  fileContextMenu.y = pointer.clientY
  fileContextMenu.visible = true
}

async function handleFileContextAction(action: string) {
  const file = fileContextMenu.file
  if (!file) return
  if (action === 'preview' && file.canPreview) await openPreview(file)
  if (action === 'download') await downloadFile(file)
  if (action === 'copy-name') {
    try {
      await navigator.clipboard.writeText(attachmentName(file))
      MessagePlugin.success('文件名已复制')
    } catch {
      MessagePlugin.warning('复制失败，请手动选择文件名')
    }
  }
  if (action === 'open-project' && file.projectId) {
    await router.push({
      path: '/project-management',
      query: {
        projectId: file.projectId,
        projectName: file.projectName || '项目详情',
      },
    })
  }
}

function handleSidebarAction(event: Event) {
  const action = (event as CustomEvent<{ action?: string }>).detail?.action
  if (action === 'materials:upload') openUploadDialog()
}

onMounted(async () => {
  const restoredScrollTop = restoreMaterialsWorkspaceState()
  window.addEventListener('jiqing-sidebar-action', handleSidebarAction)
  await Promise.all([loadFiles(), loadUploadOptions()])
  await nextTick()
  const scrollContainer = document.querySelector<HTMLElement>('.system-content')
  if (scrollContainer && restoredScrollTop > 0) scrollContainer.scrollTop = restoredScrollTop
})

onBeforeUnmount(() => {
  saveMaterialsWorkspaceState()
  window.removeEventListener('jiqing-sidebar-action', handleSidebarAction)
})
</script>

<style scoped>
.file-library { max-width: 1320px; }

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-6);
}

.page-header-left { min-width: 0; }
.page-title { font-size: var(--text-2xl); font-weight: 700; color: var(--text-primary); margin: 0 0 var(--space-1); }
.page-desc { font-size: var(--text-sm); color: var(--text-secondary); margin: 0; }

.library-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  padding: var(--space-3);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
}

.library-count { margin-left: auto; font-size: var(--text-xs); color: var(--text-tertiary); }

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.summary-item {
  display: grid;
  gap: 6px;
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
}

.summary-item span { font-size: var(--text-xs); color: var(--text-secondary); }
.summary-item strong { font-size: var(--text-xl); color: var(--text-primary); }

.library-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: var(--space-4);
}

.group-panel,
.file-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
}

.group-panel {
  align-self: start;
  max-height: calc(100vh - 250px);
  overflow: auto;
  padding: var(--space-3);
}

.panel-head {
  display: flex;
  justify-content: space-between;
  padding: 0 var(--space-1) var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.panel-head strong { color: var(--text-primary); }

.group-item,
.type-pill {
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
  color: var(--text-primary);
  cursor: pointer;
}

.group-item {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: 9px var(--space-3);
  margin-bottom: var(--space-2);
  text-align: left;
}

.group-item span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.group-item--active,
.type-pill--active {
  border-color: var(--color-brand-400);
  background: var(--color-brand-50);
  color: var(--color-brand-500);
}

.file-panel { padding: var(--space-4); min-width: 0; }

.type-strip {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.type-pill {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 7px 10px;
  font-size: var(--text-xs);
}

.file-cell,
.project-cell,
.uploaded-cell {
  display: grid;
  gap: 2px;
}

.file-cell {
  grid-template-columns: 22px minmax(0, 1fr);
  align-items: center;
}

.file-cell strong,
.project-cell strong,
.uploaded-cell strong {
  min-width: 0;
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-cell span,
.project-cell span,
.uploaded-cell span {
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.action-cell { display: flex; gap: var(--space-2); }
.action-cell button {
  border: 0;
  background: transparent;
  color: var(--color-brand-500);
  cursor: pointer;
  font-size: var(--text-xs);
  padding: 0;
}
.action-cell button:disabled { color: var(--text-tertiary); cursor: not-allowed; }

.preview-mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-6);
  background: rgba(10, 18, 32, .56);
}

.preview-panel {
  width: min(980px, 100%);
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-surface);
  border: 1px solid var(--border-color-strong);
}

.preview-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4);
  border-bottom: 1px solid var(--border-color);
}

.preview-head h3 { margin: 0; font-size: var(--text-lg); }
.preview-head p { margin: 4px 0 0; color: var(--text-secondary); font-size: var(--text-xs); }
.preview-head button { border: 0; background: transparent; color: var(--color-brand-500); cursor: pointer; }

.preview-body {
  min-height: 420px;
  overflow: auto;
  padding: var(--space-4);
  background: var(--bg-page);
}

.preview-body img,
.preview-body video {
  display: block;
  max-width: 100%;
  max-height: 68vh;
  margin: 0 auto;
}

.preview-body iframe { width: 100%; height: 68vh; border: 0; background: #FFFFFF; }
.preview-body audio { width: 100%; }
.preview-body pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  line-height: 1.7;
}

.preview-message { color: var(--text-secondary); font-size: var(--text-sm); }

.upload-form {
  display: grid;
  gap: var(--space-3);
}

.upload-form :deep(.arco-form-item) {
  margin-bottom: 0;
}

.upload-form :deep(.arco-select-view-single),
.upload-form :deep(.arco-input-wrapper) {
  width: 100%;
}

.native-file {
  width: 100%;
}

.dialog-hint {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  line-height: 1.6;
}

@media (max-width: 980px) {
  .summary-grid { grid-template-columns: repeat(2, 1fr); }
  .library-layout { grid-template-columns: 1fr; }
  .group-panel { max-height: 260px; }
}

@media (max-width: 720px) {
  .page-header,
  .library-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .library-count { margin-left: 0; }
  .summary-grid { grid-template-columns: 1fr; }
}
</style>

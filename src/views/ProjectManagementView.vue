<template>
  <div class="project-management">
    <PageHeader
      title="项目管理"
      description="统一管理项目主数据、资料台账、合同付款条款、付款结算和变更签证，并为审计看板预留联动入口。"
    >
      <template #meta>
        <t-tag variant="light" theme="primary">主数据源</t-tag>
        <t-tag variant="light">资料工作台闭环</t-tag>
        <t-tag variant="light" :theme="summary.auditLinkedProjects ? 'success' : 'warning'">
          {{ summary.auditLinkedProjects ? `已联动 ${summary.auditLinkedProjects} 个审计项目` : '待联动审计项目' }}
        </t-tag>
      </template>
      <template #actions>
        <t-button variant="outline" :loading="loading" @click="loadAll">
          <template #icon><t-icon name="refresh" /></template>
          刷新
        </t-button>
        <t-button theme="primary" @click="openProjectForm()">
          <template #icon><t-icon name="add" /></template>
          新建项目
        </t-button>
      </template>
    </PageHeader>

    <section class="summary-grid">
      <button
        v-for="card in summaryCards"
        :key="card.key"
        type="button"
        class="summary-card"
        :class="{ 'summary-card--active': activeSummaryKey === card.key }"
        @click="applySummaryFilter(card.key)"
      >
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <em>{{ card.hint }}</em>
      </button>
    </section>

    <section class="toolbar">
      <t-input v-model="filters.keyword" clearable placeholder="搜索项目名称、编号、施工单位、负责人" @keyup.enter="loadRecords">
        <template #prefix-icon><t-icon name="search" /></template>
      </t-input>
      <t-select v-model="filters.projectStatus" clearable placeholder="项目状态" :options="meta.projectStatuses" @change="loadRecords" />
      <t-select v-model="filters.settlementStatus" clearable placeholder="结算状态" :options="meta.settlementStatuses" @change="loadRecords" />
      <t-input v-model="filters.managerName" clearable placeholder="负责人" @keyup.enter="loadRecords" />
      <label class="toolbar-check">
        <input v-model="filters.onlyMissingDocuments" type="checkbox" @change="loadRecords" />
        仅看资料不齐
      </label>
      <t-select v-model="filters.sort" :options="sortOptions" placeholder="排序" @change="loadRecords" />
      <t-button theme="primary" @click="loadRecords">查询</t-button>
      <t-button variant="outline" @click="resetFilters">重置</t-button>
    </section>

    <t-alert v-if="error" theme="error" :close="false" class="page-alert">
      <template #message>{{ error }}</template>
    </t-alert>

    <StatePanel
      v-if="loading && records.length === 0"
      state="loading"
      title="正在加载项目台账"
      description="系统正在整理项目主数据、资料和结算基础信息。"
    />

    <StatePanel
      v-else-if="!loading && records.length === 0"
      state="empty"
      title="未找到项目"
      description="请调整筛选条件，或先新建一个项目作为资料工作台的起点。"
    >
      <template #actions>
        <t-button variant="outline" @click="resetFilters">清除筛选</t-button>
        <t-button theme="primary" @click="openProjectForm()">新建项目</t-button>
      </template>
    </StatePanel>

    <section v-else class="workspace">
      <div class="ledger-panel">
        <div class="panel-head">
          <div>
            <h3>项目台账</h3>
            <p>点击项目名称查看资料、结算和签证详情。</p>
          </div>
          <div class="panel-head__meta">
            <span>共 {{ total }} 条</span>
            <span>第 {{ page }} / {{ totalPages }} 页</span>
          </div>
        </div>

        <t-table :data="records" :columns="tableColumns" :loading="loading" bordered hover>
          <template #project="{ row }">
            <button class="project-link" type="button" @click="selectProject(row)">
              <strong>{{ row.projectName }}</strong>
              <span>{{ row.projectCode }} · {{ row.managerName || row.contractorName }}</span>
            </button>
          </template>
          <template #status="{ row }">
            <div class="status-stack">
              <t-tag variant="light" :theme="statusTheme(row.projectStatus)">{{ projectStatusLabel(row.projectStatus) }}</t-tag>
              <t-tag variant="light" :theme="settlementTheme(row.settlementStatus)">{{ settlementStatusLabel(row.settlementStatus) }}</t-tag>
            </div>
          </template>
          <template #docs="{ row }">
            <div class="progress-cell">
              <strong>{{ row.documentCompletion }}%</strong>
              <span>{{ row.missingRequiredCount > 0 ? `缺 ${row.missingRequiredCount} 类` : '资料齐全' }}</span>
            </div>
          </template>
          <template #amount="{ row }">
            <div class="amount-cell">
              <strong>{{ formatWan(row.contractAmount || row.submittedAmount || 0) }}</strong>
              <span>合同 / 送审</span>
            </div>
          </template>
          <template #audit="{ row }">
            <div class="audit-cell">
              <span>一审：{{ row.firstAuditMaterialStatus }}</span>
              <span>二审：{{ row.secondAuditMaterialStatus }}</span>
            </div>
          </template>
          <template #actions="{ row }">
            <div class="action-cell">
              <button type="button" @click="selectProject(row)">查看</button>
              <button type="button" @click="openProjectForm(row)">编辑</button>
              <button type="button" :disabled="!canDelete" @click="confirmDeleteProject(row)">删除</button>
            </div>
          </template>
        </t-table>

        <div class="pager">
          <span>共 {{ total }} 条，第 {{ page }} 页</span>
          <t-select v-model="filters.pageSize" :options="pageSizeOptions" style="width: 120px" @change="loadRecords" />
          <t-button variant="outline" :disabled="page <= 1" @click="changePage(page - 1)">上一页</t-button>
          <t-button variant="outline" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</t-button>
        </div>
      </div>

      <aside class="detail-panel">
        <template v-if="detailLoading">
          <StatePanel state="loading" title="正在加载项目详情" description="请稍候，正在读取该项目的资料和结算信息。" />
        </template>
        <template v-else-if="currentProject">
          <div class="detail-head">
            <div>
              <h3>{{ currentProject.projectName }}</h3>
              <p>{{ currentProject.projectCode }} · {{ currentProject.constructionUnit || currentProject.ownerUnit || '未填写建设单位' }}</p>
            </div>
            <div class="detail-head__actions">
              <t-button size="small" variant="outline" @click="openProjectForm(currentProject)">编辑</t-button>
              <t-button
                v-if="currentProject.auditProjectId"
                size="small"
                variant="outline"
                @click="goAudit(currentProject.auditProjectId)"
              >
                查看审计进度
              </t-button>
              <t-button
                v-else
                size="small"
                variant="outline"
                :loading="auditStarting"
                @click="startAudit(currentProject)"
              >
                发起审计
              </t-button>
              <t-button size="small" theme="primary" @click="openFileDialog()">上传资料</t-button>
            </div>
          </div>

          <div class="detail-metrics">
            <article>
              <span>资料完整度</span>
              <strong>{{ currentProject.documentCompletion }}%</strong>
            </article>
            <article>
              <span>合同金额</span>
              <strong>{{ formatWan(currentProject.contractAmount || 0) }}</strong>
            </article>
            <article>
              <span>变更签证</span>
              <strong>{{ currentProject.variationCount }} 项</strong>
            </article>
            <article>
              <span>联动审计</span>
              <strong>{{ currentProject.auditProjectId ? '已关联' : '未关联' }}</strong>
            </article>
          </div>

          <div class="detail-tabs" role="tablist" aria-label="项目详情分区">
            <button v-for="tab in tabs" :key="tab.value" type="button" :class="{ active: activeTab === tab.value }" @click="activeTab = tab.value">
              {{ tab.label }}
            </button>
          </div>

          <div v-if="activeTab === 'overview'" class="detail-section">
            <div class="info-grid">
              <article>
                <span>负责人</span>
                <strong>{{ currentProject.managerName || '未填写' }}</strong>
              </article>
              <article>
                <span>施工单位</span>
                <strong>{{ currentProject.contractorName || '未填写' }}</strong>
              </article>
              <article>
                <span>项目状态</span>
                <strong>{{ projectStatusLabel(currentProject.projectStatus) }}</strong>
              </article>
              <article>
                <span>结算状态</span>
                <strong>{{ settlementStatusLabel(currentProject.settlementStatus) }}</strong>
              </article>
              <article>
                <span>一审资料</span>
                <strong>{{ currentProject.firstAuditMaterialStatus }}</strong>
              </article>
              <article>
                <span>二审资料</span>
                <strong>{{ currentProject.secondAuditMaterialStatus }}</strong>
              </article>
            </div>

            <div class="link-box">
              <div>
                <span class="mini-label">审计联动</span>
                <strong>{{ currentProject.auditProjectId ? '已关联审计看板卡片' : '尚未关联审计看板' }}</strong>
                <p>{{ currentProject.auditProjectId ? '审计看板将读取项目主数据，并维护阶段、金额和审计记录。' : '可从项目主档案发起审计，系统会自动带入项目名称、金额、负责人和计划日期。' }}</p>
              </div>
              <t-button
                :variant="currentProject.auditProjectId ? 'outline' : undefined"
                :theme="currentProject.auditProjectId ? 'default' : 'primary'"
                :loading="auditStarting"
                @click="currentProject.auditProjectId ? goAudit(currentProject.auditProjectId) : startAudit(currentProject)"
              >
                {{ currentProject.auditProjectId ? '查看审计进度' : '发起审计' }}
              </t-button>
            </div>

            <div class="document-grid">
              <article v-for="category in meta.categories" :key="category.categoryKey" class="doc-card">
                <div class="doc-card__head">
                  <div>
                    <strong>{{ category.categoryName }}</strong>
                    <span>{{ category.description }}</span>
                  </div>
                  <t-tag v-if="category.required" variant="light" theme="primary">必填</t-tag>
                </div>
                <div class="doc-card__body">
                  <div class="doc-files">
                    <button
                      v-for="file in filesByCategory(category.categoryKey)"
                      :key="file.id"
                      type="button"
                      class="file-pill"
                      @click="previewFile(file)"
                    >
                      <span>{{ file.displayName }}</span>
                      <small>V{{ file.versionNo }}</small>
                    </button>
                    <span v-if="filesByCategory(category.categoryKey).length === 0" class="file-empty">暂无资料</span>
                  </div>
                  <div class="doc-actions">
                    <t-button size="small" variant="outline" @click="openFileDialog(category)">上传资料</t-button>
                    <span>{{ category.categoryKey }}</span>
                  </div>
                </div>
              </article>
            </div>
          </div>

          <div v-else-if="activeTab === 'files'" class="detail-section">
            <div class="section-head">
              <strong>资料列表</strong>
              <t-button size="small" theme="primary" @click="openFileDialog()">上传资料</t-button>
            </div>
            <t-table :data="currentProject.files || []" :columns="fileColumns" bordered hover>
              <template #name="{ row }">
                <div class="file-cell">
                  <strong>{{ row.displayName }}</strong>
                  <span>{{ row.originalName }} · V{{ row.versionNo }}</span>
                </div>
              </template>
              <template #category="{ row }">
                <t-tag variant="light">{{ row.categoryName }}</t-tag>
              </template>
          <template #size="{ row }">{{ formatSize(row.fileSize) }}</template>
          <template #uploadedAt="{ row }">{{ formatDate(row.uploadedAt) }}</template>
          <template #actions="{ row }">
            <div class="action-cell">
                  <button :disabled="!row.canPreview" type="button" @click="previewFile(row)">预览</button>
                  <button type="button" @click="downloadFile(row)">下载</button>
                  <button type="button" @click="openRenameDialog(row)">重命名</button>
                  <button type="button" :disabled="!canDelete" @click="confirmDeleteFile(row)">删除</button>
                </div>
              </template>
            </t-table>
          </div>

          <div v-else-if="activeTab === 'settlements'" class="detail-section">
            <div class="section-head">
              <strong>付款结算</strong>
              <t-button size="small" theme="primary" @click="openSettlementDialog()">新增结算</t-button>
            </div>
            <t-table :data="currentProject.settlements || []" :columns="settlementColumns" bordered hover>
              <template #name="{ row }">
                <div class="file-cell">
                  <strong>{{ row.settlementName }}</strong>
                  <span>{{ row.settlementType }}</span>
                </div>
              </template>
              <template #status="{ row }">
                <t-tag variant="light" :theme="settlementTheme(row.settlementStatus)">{{ settlementStatusLabel(row.settlementStatus) }}</t-tag>
              </template>
              <template #amount="{ row }">{{ formatWan(row.approvedAmount || row.applyAmount || 0) }}</template>
              <template #actions="{ row }">
                <div class="action-cell">
                  <button type="button" @click="openSettlementDialog(row)">编辑</button>
                </div>
              </template>
            </t-table>
          </div>

          <div v-else-if="activeTab === 'variations'" class="detail-section">
            <div class="section-head">
              <strong>变更签证</strong>
              <t-button size="small" theme="primary" @click="openVariationDialog()">新增签证</t-button>
            </div>
            <t-table :data="currentProject.variations || []" :columns="variationColumns" bordered hover>
              <template #name="{ row }">
                <div class="file-cell">
                  <strong>{{ row.variationName }}</strong>
                  <span>{{ row.variationType }}</span>
                </div>
              </template>
              <template #status="{ row }">
                <t-tag variant="light" :theme="statusTheme(row.variationStatus)">{{ variationStatusLabel(row.variationStatus) }}</t-tag>
              </template>
              <template #amount="{ row }">{{ formatWan(row.amount || 0) }}</template>
              <template #actions="{ row }">
                <div class="action-cell">
                  <button type="button" @click="openVariationDialog(row)">编辑</button>
                </div>
              </template>
            </t-table>
          </div>

          <div v-else class="detail-section">
            <div class="section-head">
              <strong>操作日志</strong>
              <span>最新 {{ (currentProject.logs || []).length }} 条</span>
            </div>
            <div class="log-list">
              <article v-for="log in currentProject.logs || []" :key="log.id">
                <strong>{{ log.content }}</strong>
                <span>{{ log.operatorName || '系统' }} · {{ formatDate(log.createdAt) }}</span>
              </article>
              <div v-if="(currentProject.logs || []).length === 0" class="log-empty">暂无操作记录</div>
            </div>
          </div>
        </template>
      </aside>
    </section>

    <t-dialog
      v-model:visible="projectDialog.visible"
      :header="projectDialog.mode === 'create' ? '新建项目' : '编辑项目'"
      :confirm-btn="{ content: '保存项目', loading: projectDialog.saving }"
      width="880px"
      @confirm="saveProject"
    >
      <div class="dialog-grid">
        <label v-for="field in projectFieldsLeft" :key="field.key">
          <span>{{ field.label }}<b v-if="field.required">*</b></span>
          <t-input v-model="projectForm[field.key]" :placeholder="field.placeholder" />
        </label>
        <label v-for="field in projectFieldsRight" :key="field.key">
          <span>{{ field.label }}<b v-if="field.required">*</b></span>
          <t-input v-model="projectForm[field.key]" :placeholder="field.placeholder" />
        </label>
        <label>
          <span>项目状态</span>
          <t-select v-model="projectForm.projectStatus" :options="meta.projectStatuses" />
        </label>
        <label>
          <span>结算状态</span>
          <t-select v-model="projectForm.settlementStatus" :options="meta.settlementStatuses" />
        </label>
        <label>
          <span>合同金额</span>
          <t-input-number v-model="projectForm.contractAmount" :min="0" :precision="2" />
        </label>
        <label>
          <span>送审金额</span>
          <t-input-number v-model="projectForm.submittedAmount" :min="0" :precision="2" />
        </label>
        <label>
          <span>已付款金额</span>
          <t-input-number v-model="projectForm.paidAmount" :min="0" :precision="2" />
        </label>
        <label>
          <span>审计联动</span>
          <t-input v-model="projectForm.auditProjectId" readonly placeholder="保存项目后可从详情中发起审计" />
        </label>
        <label class="dialog-span-2">
          <span>付款条款</span>
          <t-textarea v-model="projectForm.paymentTerms" :auto-size="{ minRows: 3, maxRows: 6 }" placeholder="如：按节点完成后支付 80%，结算定案后支付尾款" />
        </label>
        <label class="dialog-span-2">
          <span>项目说明</span>
          <t-textarea v-model="projectForm.description" :auto-size="{ minRows: 3, maxRows: 6 }" placeholder="项目背景、当前资料状态、需要提醒的事项" />
        </label>
      </div>
    </t-dialog>

    <t-dialog
      v-model:visible="fileDialog.visible"
      header="上传资料"
      :confirm-btn="{ content: '开始上传', loading: fileDialog.saving }"
      width="620px"
      @confirm="saveFile"
    >
      <div class="dialog-grid dialog-grid--single">
        <label>
          <span>资料分类</span>
          <t-select v-model="fileDialog.categoryKey" :options="categoryOptions" />
        </label>
        <label>
          <span>资料名称</span>
          <t-input v-model="fileDialog.displayName" placeholder="请输入便于识别的资料名称" />
        </label>
        <label>
          <span>文件</span>
          <input ref="fileInputRef" type="file" class="native-file" @change="onFilePicked" />
        </label>
        <p class="dialog-hint">同一项目、同一分类、同一资料名称再次上传时会自动作为新版本处理。</p>
      </div>
    </t-dialog>

    <t-dialog
      v-model:visible="settlementDialog.visible"
      :header="settlementDialog.mode === 'create' ? '新增结算' : '编辑结算'"
      :confirm-btn="{ content: '保存结算', loading: settlementDialog.saving }"
      width="700px"
      @confirm="saveSettlement"
    >
      <div class="dialog-grid">
        <label class="dialog-span-2">
          <span>结算名称</span>
          <t-input v-model="settlementForm.settlementName" placeholder="如：一期竣工结算" />
        </label>
        <label>
          <span>结算状态</span>
          <t-select v-model="settlementForm.settlementStatus" :options="meta.settlementStatuses" />
        </label>
        <label>
          <span>结算类型</span>
          <t-input v-model="settlementForm.settlementType" placeholder="progress / final / other" />
        </label>
        <label>
          <span>申报金额</span>
          <t-input-number v-model="settlementForm.applyAmount" :min="0" :precision="2" />
        </label>
        <label>
          <span>核定金额</span>
          <t-input-number v-model="settlementForm.approvedAmount" :min="0" :precision="2" />
        </label>
        <label>
          <span>已付款金额</span>
          <t-input-number v-model="settlementForm.paidAmount" :min="0" :precision="2" />
        </label>
        <label>
          <span>申报日期</span>
          <t-input v-model="settlementForm.applyDate" placeholder="YYYY-MM-DD" />
        </label>
        <label>
          <span>预计付款日期</span>
          <t-input v-model="settlementForm.expectedPayDate" placeholder="YYYY-MM-DD" />
        </label>
        <label>
          <span>实际付款日期</span>
          <t-input v-model="settlementForm.paidDate" placeholder="YYYY-MM-DD" />
        </label>
        <label class="dialog-span-2">
          <span>备注</span>
          <t-textarea v-model="settlementForm.remark" :auto-size="{ minRows: 3, maxRows: 5 }" />
        </label>
      </div>
    </t-dialog>

    <t-dialog
      v-model:visible="variationDialog.visible"
      :header="variationDialog.mode === 'create' ? '新增变更签证' : '编辑变更签证'"
      :confirm-btn="{ content: '保存签证', loading: variationDialog.saving }"
      width="700px"
      @confirm="saveVariation"
    >
      <div class="dialog-grid">
        <label class="dialog-span-2">
          <span>签证名称</span>
          <t-input v-model="variationForm.variationName" placeholder="如：设计变更签证 01" />
        </label>
        <label>
          <span>签证状态</span>
          <t-input v-model="variationForm.variationStatus" placeholder="pending / approved / rejected" />
        </label>
        <label>
          <span>签证类型</span>
          <t-input v-model="variationForm.variationType" placeholder="change / visa / other" />
        </label>
        <label>
          <span>金额</span>
          <t-input-number v-model="variationForm.amount" :min="0" :precision="2" />
        </label>
        <label>
          <span>发生日期</span>
          <t-input v-model="variationForm.occurredDate" placeholder="YYYY-MM-DD" />
        </label>
        <label>
          <span>确认日期</span>
          <t-input v-model="variationForm.approvedDate" placeholder="YYYY-MM-DD" />
        </label>
        <label class="dialog-span-2">
          <span>备注</span>
          <t-textarea v-model="variationForm.remark" :auto-size="{ minRows: 3, maxRows: 5 }" />
        </label>
      </div>
    </t-dialog>

    <t-dialog
      v-model:visible="renameDialog.visible"
      header="重命名资料"
      :confirm-btn="{ content: '保存名称', loading: renameDialog.saving }"
      width="520px"
      @confirm="saveRename"
    >
      <div class="dialog-grid dialog-grid--single">
        <label>
          <span>新的资料名称</span>
          <t-input v-model="renameDialog.displayName" placeholder="请输入新的资料名称" />
        </label>
      </div>
    </t-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import StatePanel from '@/components/StatePanel.vue'
import { MessagePlugin } from '@/ui/message'
import { formatWan } from '@/utils/format'
import type { ProjectDocumentCategory, ProjectFile, ProjectFilters, ProjectMeta, ProjectRecord, ProjectSettlement, ProjectSummary, ProjectVariation } from '@/types'
import {
  createProjectRecord,
  deleteProjectFile,
  deleteProjectRecord,
  fetchProjectFileDownloadBlob,
  fetchProjectFilePreviewBlob,
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
  renameProjectFile,
} from '@/api/projects'

const router = useRouter()
const route = useRoute()
type DetailTab = 'overview' | 'files' | 'settlements' | 'variations' | 'logs'

const tableColumns = [
  { colKey: 'project', title: '项目', width: 320 },
  { colKey: 'status', title: '状态', width: 170 },
  { colKey: 'docs', title: '资料', width: 110 },
  { colKey: 'amount', title: '金额', width: 140 },
  { colKey: 'audit', title: '审计联动', width: 170 },
  { colKey: 'actions', title: '操作', width: 160 },
]

const fileColumns = [
  { colKey: 'name', title: '资料名称', width: 260 },
  { colKey: 'category', title: '分类', width: 130 },
  { colKey: 'size', title: '大小', width: 110 },
  { colKey: 'uploadedAt', title: '上传时间', width: 170 },
  { colKey: 'actions', title: '操作', width: 170 },
]

const settlementColumns = [
  { colKey: 'name', title: '结算事项', width: 260 },
  { colKey: 'status', title: '状态', width: 120 },
  { colKey: 'amount', title: '金额', width: 140 },
  { colKey: 'actions', title: '操作', width: 100 },
]

const variationColumns = [
  { colKey: 'name', title: '签证事项', width: 260 },
  { colKey: 'status', title: '状态', width: 120 },
  { colKey: 'amount', title: '金额', width: 140 },
  { colKey: 'actions', title: '操作', width: 100 },
]

const sortOptions = [
  { label: '按更新时间', value: 'updatedAt' },
  { label: '按项目名称', value: 'projectName' },
  { label: '按合同金额', value: 'contractAmount' },
  { label: '按资料完整度', value: 'documentCompletion' },
  { label: '按计划完成日期', value: 'plannedEndDate' },
]

const pageSizeOptions = [
  { label: '10 条/页', value: 10 },
  { label: '20 条/页', value: 20 },
  { label: '50 条/页', value: 50 },
]

const tabs: Array<{ label: string; value: DetailTab }> = [
  { label: '概览', value: 'overview' },
  { label: '资料', value: 'files' },
  { label: '结算', value: 'settlements' },
  { label: '签证', value: 'variations' },
  { label: '日志', value: 'logs' },
]

const filters = reactive<ProjectFilters>({
  keyword: '',
  projectStatus: '',
  settlementStatus: '',
  managerName: '',
  onlyMissingDocuments: false,
  sort: 'updatedAt',
  page: 1,
  pageSize: 10,
})

const meta = reactive<ProjectMeta>({
  categories: [],
  projectStatuses: [],
  settlementStatuses: [],
  auditStages: [],
})

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
const detailLoading = ref(false)
const auditStarting = ref(false)
const error = ref('')
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const activeTab = ref<DetailTab>('overview')
const activeSummaryKey = ref('')
const canDelete = true

const projectDialog = reactive({ visible: false, mode: 'create' as 'create' | 'edit', saving: false })
const fileDialog = reactive({
  visible: false,
  saving: false,
  projectId: '',
  categoryKey: '',
  displayName: '',
  file: null as File | null,
})
const settlementDialog = reactive({ visible: false, mode: 'create' as 'create' | 'edit', saving: false, id: '' })
const variationDialog = reactive({ visible: false, mode: 'create' as 'create' | 'edit', saving: false, id: '' })
const renameDialog = reactive({ visible: false, saving: false, id: '', displayName: '' })
const fileInputRef = ref<HTMLInputElement | null>(null)

const projectForm = reactive({
  id: '',
  projectCode: '',
  projectName: '',
  constructionUnit: '',
  contractorName: '',
  contractorContact: '',
  ownerUnit: '',
  companyRole: '工程咨询',
  managerName: '',
  projectStatus: 'active',
  settlementStatus: 'not_started',
  auditStage: 'not_linked',
  contractAmount: 0,
  submittedAmount: 0,
  paidAmount: 0,
  paymentTerms: '',
  plannedStartDate: '',
  plannedEndDate: '',
  description: '',
  auditProjectId: '',
})
type ProjectFormKey = keyof typeof projectForm

const settlementForm = reactive({
  settlementName: '',
  settlementType: 'progress',
  settlementStatus: 'pending',
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

const projectFieldsLeft: Array<{ key: ProjectFormKey; label: string; placeholder: string; required: boolean }> = [
  { key: 'projectCode', label: '项目编号', placeholder: '系统将保留该编号', required: false },
  { key: 'projectName', label: '项目名称', placeholder: '请输入项目名称', required: true },
  { key: 'constructionUnit', label: '施工单位', placeholder: '请输入施工单位', required: false },
  { key: 'ownerUnit', label: '建设单位', placeholder: '请输入建设单位', required: false },
]

const projectFieldsRight: Array<{ key: ProjectFormKey; label: string; placeholder: string; required: boolean }> = [
  { key: 'contractorName', label: '施工联系人/负责人', placeholder: '请输入负责人姓名', required: false },
  { key: 'contractorContact', label: '联系电话', placeholder: '请输入联系电话', required: false },
  { key: 'managerName', label: '项目负责人', placeholder: '请输入项目负责人', required: false },
  { key: 'companyRole', label: '我方角色', placeholder: '请输入我方角色', required: false },
]

const categoryOptions = computed(() => meta.categories.map((item) => ({ label: item.categoryName, value: item.categoryKey })))

const summaryCards = computed(() => [
  { key: 'all', label: '项目总数', value: summary.totalProjects, hint: '全部项目主数据' },
  { key: 'active', label: '进行中', value: summary.activeProjects, hint: '正在推进的项目' },
  { key: 'settlement', label: '结算中', value: summary.settlementProjects, hint: '进入付款结算的项目' },
  { key: 'audit', label: '已联动审计', value: summary.auditLinkedProjects, hint: '已绑定 project_id 的项目' },
  { key: 'missing', label: '资料不齐', value: summary.missingDocuments, hint: '需要补资料的项目' },
  { key: 'variation', label: '变更签证金额', value: formatWan(summary.variationAmount || 0), hint: '汇总已维护的签证金额' },
])

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

function statusTheme(status: string) {
  if (['completed', 'approved'].includes(status)) return 'success'
  if (['rejected', 'paused'].includes(status)) return 'danger'
  if (['reviewing', 'settlement', 'active'].includes(status)) return 'primary'
  return 'warning'
}

function settlementTheme(status: string) {
  if (status === 'paid' || status === 'approved') return 'success'
  if (status === 'rejected') return 'danger'
  if (status === 'reviewing') return 'warning'
  return 'primary'
}

function projectStatusLabel(value: string) {
  return meta.projectStatuses.find((item) => item.value === value)?.label || value || '未设置'
}

function settlementStatusLabel(value: string) {
  return meta.settlementStatuses.find((item) => item.value === value)?.label || value || '未设置'
}

function variationStatusLabel(value: string) {
  const map: Record<string, string> = { pending: '待确认', approved: '已确认', rejected: '已驳回' }
  return map[value] || value || '未设置'
}

function formatSize(size: number) {
  if (!size) return '0 B'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

function formatDate(iso: string) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function filesByCategory(categoryKey: string) {
  return (currentProject.value?.files || []).filter((file) => file.categoryKey === categoryKey)
}

function fillProjectForm(record?: ProjectRecord | null) {
  Object.assign(projectForm, {
    id: record?.id || '',
    projectCode: record?.projectCode || '',
    projectName: record?.projectName || '',
    constructionUnit: record?.constructionUnit || '',
    contractorName: record?.contractorName || '',
    contractorContact: record?.contractorContact || '',
    ownerUnit: record?.ownerUnit || '',
    companyRole: record?.companyRole || '工程咨询',
    managerName: record?.managerName || '',
    projectStatus: record?.projectStatus || 'active',
    settlementStatus: record?.settlementStatus || 'not_started',
    auditStage: record?.auditStage || 'not_linked',
    contractAmount: record?.contractAmount || 0,
    submittedAmount: record?.submittedAmount || 0,
    paidAmount: record?.paidAmount || 0,
    paymentTerms: record?.paymentTerms || '',
    plannedStartDate: record?.plannedStartDate || '',
    plannedEndDate: record?.plannedEndDate || '',
    description: record?.description || '',
    auditProjectId: record?.auditProjectId || '',
  })
}

function fillSettlementForm(record?: ProjectSettlement | null) {
  Object.assign(settlementForm, {
    settlementName: record?.settlementName || '',
    settlementType: record?.settlementType || 'progress',
    settlementStatus: record?.settlementStatus || 'pending',
    applyAmount: record?.applyAmount || 0,
    approvedAmount: record?.approvedAmount || 0,
    paidAmount: record?.paidAmount || 0,
    applyDate: record?.applyDate || '',
    expectedPayDate: record?.expectedPayDate || '',
    paidDate: record?.paidDate || '',
    remark: record?.remark || '',
  })
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

function clearFilters() {
  filters.keyword = ''
  filters.projectStatus = ''
  filters.settlementStatus = ''
  filters.managerName = ''
  filters.onlyMissingDocuments = false
  filters.sort = 'updatedAt'
  filters.page = 1
  filters.pageSize = 10
}

function applySummaryFilter(key: string) {
  activeSummaryKey.value = key
  if (key === 'active') filters.projectStatus = 'active'
  else if (key === 'settlement') filters.settlementStatus = 'pending'
  else if (key === 'audit') filters.onlyMissingDocuments = false
  else if (key === 'missing') filters.onlyMissingDocuments = true
  else {
    filters.projectStatus = ''
    filters.settlementStatus = ''
    filters.onlyMissingDocuments = false
  }
  filters.page = 1
  loadRecords()
}

function resetFilters() {
  activeSummaryKey.value = ''
  clearFilters()
  loadRecords()
}

function changePage(nextPage: number) {
  filters.page = nextPage
  loadRecords()
}

function openProjectForm(record?: ProjectRecord | null) {
  projectDialog.mode = record ? 'edit' : 'create'
  fillProjectForm(record || null)
  projectDialog.visible = true
}

function openFileDialog(category?: ProjectDocumentCategory | null) {
  if (!currentProject.value) return
  fileDialog.projectId = currentProject.value.id
  fileDialog.categoryKey = category?.categoryKey || meta.categories[0]?.categoryKey || ''
  fileDialog.displayName = ''
  fileDialog.file = null
  fileDialog.visible = true
}

function onFilePicked(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] || null
  fileDialog.file = file
  if (file && !fileDialog.displayName) {
    fileDialog.displayName = file.name.replace(/\.[^.]+$/, '')
  }
}

function openSettlementDialog(record?: ProjectSettlement | null) {
  if (!currentProject.value) return
  settlementDialog.mode = record ? 'edit' : 'create'
  settlementDialog.id = record?.id || ''
  fillSettlementForm(record || null)
  settlementDialog.visible = true
}

function openVariationDialog(record?: ProjectVariation | null) {
  if (!currentProject.value) return
  variationDialog.mode = record ? 'edit' : 'create'
  variationDialog.id = record?.id || ''
  fillVariationForm(record || null)
  variationDialog.visible = true
}

function openRenameDialog(file: ProjectFile) {
  renameDialog.id = file.id
  renameDialog.displayName = file.displayName
  renameDialog.visible = true
}

async function loadMeta() {
  const value = await fetchProjectMeta()
  meta.categories = value.categories || []
  meta.projectStatuses = value.projectStatuses || []
  meta.settlementStatuses = value.settlementStatuses || []
  meta.auditStages = value.auditStages || []
}

async function loadSummary() {
  const value = await fetchProjectSummary()
  Object.assign(summary, value)
}

async function loadRecords() {
  loading.value = true
  error.value = ''
  try {
    const result = await fetchProjectRecords({
      ...filters,
      page: filters.page,
      pageSize: filters.pageSize,
    })
    records.value = result.data
    total.value = result.total
    page.value = result.page
    pageSize.value = result.pageSize
    if (!currentProject.value || !records.value.find((item) => item.id === currentProject.value?.id)) {
      const targetId = String(route.query.projectId || '')
      const targetRecord = targetId ? records.value.find((item) => item.id === targetId) : null
      if (targetRecord) await loadCurrentProject(targetRecord.id)
      else if (records.value[0]) await loadCurrentProject(records.value[0].id)
      else currentProject.value = null
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '项目列表加载失败'
    MessagePlugin.error(error.value)
  } finally {
    loading.value = false
  }
}

async function loadCurrentProject(id: string) {
  detailLoading.value = true
  try {
    currentProject.value = await fetchProjectRecord(id)
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '项目详情加载失败')
  } finally {
    detailLoading.value = false
  }
}

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadMeta(), loadSummary()])
    await loadRecords()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载失败'
    MessagePlugin.error(error.value)
  } finally {
    loading.value = false
  }
}

async function selectProject(record: ProjectRecord, fetchDetail = true) {
  if (currentProject.value?.id === record.id && !fetchDetail) return
  if (!fetchDetail) {
    currentProject.value = record
    activeTab.value = 'overview'
    return
  }
  await loadCurrentProject(record.id)
  activeTab.value = 'overview'
}

async function saveProject() {
  if (!projectForm.projectName.trim()) {
    MessagePlugin.error('请先填写项目名称')
    return
  }
  projectDialog.saving = true
  try {
    const payload = {
      ...projectForm,
      contractAmount: Number(projectForm.contractAmount || 0),
      submittedAmount: Number(projectForm.submittedAmount || 0),
      paidAmount: Number(projectForm.paidAmount || 0),
    }
    const result = projectDialog.mode === 'create'
      ? await createProjectRecord(payload)
      : await updateProjectRecord(projectForm.id, payload)
    MessagePlugin.success('项目已保存')
    projectDialog.visible = false
    await loadRecords()
    await selectProject(result)
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '保存失败')
  } finally {
    projectDialog.saving = false
  }
}

async function startAudit(record: ProjectRecord) {
  if (!record?.id) return
  if (record.auditProjectId) {
    MessagePlugin.warning('该项目已进入审计流程，请直接查看审计进度')
    return
  }
  if (!window.confirm(`确认将「${record.projectName}」发起审计流程？系统会自动带入项目主数据。`)) return
  auditStarting.value = true
  try {
    const auditProject = await startProjectAudit(record.id)
    MessagePlugin.success('已发起审计流程')
    await loadSummary()
    await loadRecords()
    await loadCurrentProject(record.id)
    goAudit(auditProject.id)
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '发起审计失败，请稍后重试或联系管理员')
  } finally {
    auditStarting.value = false
  }
}

async function saveFile() {
  if (!currentProject.value) return
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
    fileDialog.file = null
    if (fileInputRef.value) fileInputRef.value.value = ''
    await loadCurrentProject(fileDialog.projectId)
    await loadRecords()
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '资料上传失败')
  } finally {
    fileDialog.saving = false
  }
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
    if (settlementDialog.mode === 'edit' && settlementDialog.id) {
      await updateProjectSettlement(settlementDialog.id, payload)
    } else {
      await saveProjectSettlement(currentProject.value.id, payload)
    }
    MessagePlugin.success('结算已保存')
    settlementDialog.visible = false
    await loadCurrentProject(currentProject.value.id)
    await loadSummary()
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '结算保存失败')
  } finally {
    settlementDialog.saving = false
  }
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
    if (variationDialog.mode === 'edit' && variationDialog.id) {
      await updateProjectVariation(variationDialog.id, payload)
    } else {
      await saveProjectVariation(currentProject.value.id, payload)
    }
    MessagePlugin.success('签证已保存')
    variationDialog.visible = false
    await loadCurrentProject(currentProject.value.id)
    await loadSummary()
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '签证保存失败')
  } finally {
    variationDialog.saving = false
  }
}

async function saveRename() {
  renameDialog.saving = true
  try {
    await renameProjectFile(renameDialog.id, renameDialog.displayName)
    MessagePlugin.success('资料名称已更新')
    renameDialog.visible = false
    if (currentProject.value) await loadCurrentProject(currentProject.value.id)
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '重命名失败')
  } finally {
    renameDialog.saving = false
  }
}

async function previewFile(file: ProjectFile) {
  try {
    const blob = await fetchProjectFilePreviewBlob(file.id)
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank', 'noopener,noreferrer')
    window.setTimeout(() => URL.revokeObjectURL(url), 5000)
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '预览失败，请下载查看')
  }
}

async function downloadFile(file: ProjectFile) {
  try {
    const blob = await fetchProjectFileDownloadBlob(file.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = file.displayName || file.originalName || '附件'
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 3000)
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '下载失败')
  }
}

async function confirmDeleteProject(record: ProjectRecord) {
  if (!window.confirm(`确认删除项目「${record.projectName}」吗？删除后可在数据库恢复前不可见。`)) return
  try {
    await deleteProjectRecord(record.id)
    MessagePlugin.success('项目已删除')
    await loadAll()
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '删除失败')
  }
}

async function confirmDeleteFile(file: ProjectFile) {
  if (!window.confirm(`确认删除资料「${file.displayName}」吗？`)) return
  try {
    await deleteProjectFile(file.id)
    MessagePlugin.success('资料已删除')
    if (currentProject.value) await loadCurrentProject(currentProject.value.id)
  } catch (err) {
    MessagePlugin.error(err instanceof Error ? err.message : '删除失败')
  }
}

function goAudit(id: string) {
  router.push({ path: '/audit', query: { projectId: id } })
}

onMounted(loadAll)
</script>

<style scoped>
.project-management {
  display: grid;
  gap: var(--space-4);
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: var(--space-3);
}

.summary-card {
  text-align: left;
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  cursor: pointer;
}

.summary-card--active {
  border-color: var(--color-brand-400);
  background: var(--color-brand-50);
}

.summary-card span,
.summary-card em {
  display: block;
  font-style: normal;
}

.summary-card span { color: var(--text-secondary); font-size: var(--text-xs); }
.summary-card strong { display: block; margin: 6px 0 4px; font-size: var(--text-2xl); }
.summary-card em { color: var(--text-tertiary); font-size: var(--text-xs); }

.toolbar {
  display: grid;
  grid-template-columns: minmax(220px, 1.5fr) repeat(5, minmax(0, 1fr)) auto auto;
  gap: var(--space-3);
  align-items: center;
  padding: var(--space-3);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
}

.toolbar-check {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.page-alert {
  border-radius: var(--radius-md);
}

.workspace {
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(360px, 1fr);
  gap: var(--space-4);
  align-items: start;
}

.ledger-panel,
.detail-panel {
  min-width: 0;
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
}

.ledger-panel {
  padding: var(--space-4);
}

.panel-head,
.detail-head,
.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.panel-head h3,
.detail-head h3,
.section-head strong {
  margin: 0;
  font-size: var(--text-xl);
}

.panel-head p,
.detail-head p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.panel-head__meta,
.detail-head__actions,
.action-cell,
.status-stack,
.audit-cell,
.progress-cell,
.amount-cell,
.file-cell,
.log-list,
.info-grid,
.detail-metrics,
.dialog-grid,
.doc-card__head,
.doc-card__body {
  display: grid;
}

.panel-head__meta {
  justify-items: end;
  gap: 4px;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.project-link {
  display: grid;
  gap: 2px;
  width: 100%;
  padding: 0;
  background: transparent;
  border: 0;
  text-align: left;
  cursor: pointer;
}

.project-link strong { font-size: var(--text-sm); color: var(--text-primary); }
.project-link span { color: var(--text-secondary); font-size: var(--text-xs); }

.status-stack,
.audit-cell,
.progress-cell,
.amount-cell {
  gap: 4px;
}

.progress-cell strong,
.amount-cell strong { font-size: var(--text-md); }
.progress-cell span,
.amount-cell span,
.audit-cell span,
.log-list span,
.doc-card__head span,
.doc-actions span,
.file-empty {
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.action-cell { grid-auto-flow: column; justify-content: start; gap: var(--space-3); }
.action-cell button {
  border: 0;
  background: transparent;
  color: var(--color-brand-600);
  cursor: pointer;
  font-size: var(--text-xs);
  padding: 0;
}
.action-cell button:disabled { color: var(--text-tertiary); cursor: not-allowed; }

.pager {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-4);
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.detail-panel {
  padding: var(--space-4);
  position: sticky;
  top: var(--space-4);
}

.detail-metrics {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-2);
  margin: var(--space-4) 0;
}

.detail-metrics article,
.info-grid article {
  padding: var(--space-3);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
}

.detail-metrics span,
.info-grid span {
  display: block;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.detail-metrics strong,
.info-grid strong {
  display: block;
  margin-top: 6px;
  font-size: var(--text-md);
}

.detail-tabs {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
  margin-bottom: var(--space-3);
}

.detail-tabs button {
  flex: 0 0 auto;
  border: 1px solid var(--border-color);
  background: var(--bg-muted);
  color: var(--text-secondary);
  cursor: pointer;
  padding: 8px 12px;
}

.detail-tabs button.active {
  color: var(--color-brand-600);
  border-color: var(--color-brand-400);
  background: var(--color-brand-50);
}

.detail-section { display: grid; gap: var(--space-4); }

.info-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2);
}

.link-box {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
}

.link-box p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.mini-label {
  color: var(--color-brand-600);
  font-size: var(--text-xs);
}

.document-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.doc-card {
  padding: var(--space-3);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
}

.doc-card__head,
.doc-card__body {
  gap: var(--space-2);
}

.doc-card__head {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
}

.doc-card__head strong { display: block; font-size: var(--text-sm); }

.doc-files {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 34px;
}

.file-pill {
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
  cursor: pointer;
  padding: 6px 8px;
  display: inline-flex;
  gap: 6px;
  align-items: center;
}

.file-pill span { font-size: var(--text-xs); }
.file-pill small { color: var(--text-tertiary); font-size: 10px; }

.doc-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.section-head {
  align-items: center;
}

.log-list {
  gap: 10px;
}

.log-list article {
  padding: var(--space-3);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
}

.log-list strong {
  display: block;
  margin-bottom: 4px;
  font-size: var(--text-sm);
}

.log-empty {
  padding: var(--space-4);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  text-align: center;
}

.dialog-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.dialog-grid--single {
  grid-template-columns: 1fr;
}

.dialog-span-2 {
  grid-column: span 2;
}

.dialog-grid label {
  display: grid;
  gap: 6px;
}

.dialog-grid span {
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.dialog-hint {
  grid-column: span 2;
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.native-file {
  width: 100%;
}

@media (max-width: 1280px) {
  .summary-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .toolbar { grid-template-columns: 1fr 1fr 1fr 1fr; }
  .workspace { grid-template-columns: 1fr; }
  .detail-panel { position: static; }
}

@media (max-width: 760px) {
  .summary-grid,
  .document-grid,
  .detail-metrics,
  .info-grid,
  .dialog-grid { grid-template-columns: 1fr; }
  .dialog-span-2,
  .dialog-hint { grid-column: span 1; }
  .toolbar {
    grid-template-columns: 1fr;
  }
  .pager,
  .link-box,
  .panel-head,
  .detail-head {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>

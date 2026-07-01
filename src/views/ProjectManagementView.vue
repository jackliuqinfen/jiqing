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

    <section class="project-dashboard" aria-label="项目总览">
      <article class="dashboard-panel dashboard-panel--hero">
        <div class="dashboard-panel__head">
          <div>
            <span class="mini-label">今日重点</span>
            <h3>项目总览工作台</h3>
            <p>先看风险、到期、资料缺口，再进入对应项目处理。</p>
          </div>
          <t-button size="small" theme="primary" variant="outline" @click="applyDashboardAction('risk')">查看风险项目</t-button>
        </div>
        <div class="focus-metrics">
          <button type="button" @click="applyDashboardAction('due')">
            <span>即将到期</span>
            <strong>{{ dueSoonProjects.length }}</strong>
            <em>7 天内计划完成</em>
          </button>
          <button type="button" @click="applyDashboardAction('risk')">
            <span>风险项目</span>
            <strong>{{ riskProjects.length }}</strong>
            <em>资料缺口或超期</em>
          </button>
          <button type="button" @click="applyDashboardAction('missing')">
            <span>待补资料</span>
            <strong>{{ summary.missingDocuments }}</strong>
            <em>影响审计流转</em>
          </button>
        </div>
      </article>

      <article class="dashboard-panel">
        <div class="dashboard-panel__head">
          <div>
            <h3>负责人分布</h3>
            <p>点击负责人快速查看对应项目。</p>
          </div>
        </div>
        <div class="owner-list">
          <button v-for="owner in ownerDistribution" :key="owner.name" type="button" @click="filterByOwner(owner.name)">
            <span>{{ owner.name }}</span>
            <strong>{{ owner.count }}</strong>
          </button>
          <p v-if="ownerDistribution.length === 0" class="quiet-empty">暂无负责人数据</p>
        </div>
      </article>

      <article class="dashboard-panel">
        <div class="dashboard-panel__head">
          <div>
            <h3>最近更新</h3>
            <p>优先回到刚变化的项目。</p>
          </div>
        </div>
        <div class="recent-list">
          <button v-for="project in recentProjects" :key="project.id" type="button" @click="selectProject(project)">
            <strong>{{ project.projectName }}</strong>
            <span>{{ project.managerName || '未分配负责人' }} · {{ shortDate(project.updatedAt) }}</span>
          </button>
          <p v-if="recentProjects.length === 0" class="quiet-empty">暂无最近更新</p>
        </div>
      </article>
    </section>

    <section class="project-work-items" aria-label="待办与异常">
      <div class="project-work-items__head">
        <div>
          <span class="mini-label">待办与异常</span>
          <h3>优先处理事项</h3>
          <p>来自资料缺失、到期提醒、金额异常和审计结论确认。</p>
        </div>
        <t-button size="small" variant="outline" @click="applyDashboardAction('risk')">查看风险项目</t-button>
      </div>
      <div class="project-work-list">
        <button
          v-for="item in projectWorkItems"
          :key="item.id"
          type="button"
          class="project-work-card"
          :data-level="item.level"
          @click="openProjectWorkItem(item)"
        >
          <span>{{ item.type }}</span>
          <strong>{{ item.projectName || '未命名项目' }}</strong>
          <em>{{ item.owner || '未分配负责人' }} · {{ item.dueDate || '未设期限' }}</em>
          <b>{{ item.action || '查看处理' }}</b>
        </button>
        <p v-if="projectWorkItems.length === 0" class="quiet-empty">当前没有需要优先处理的事项。</p>
      </div>
    </section>

    <section class="toolbar">
      <t-input v-model="filters.keyword" class="project-keyword-input" clearable placeholder="搜索项目名称、编号、施工单位、负责人" @keyup.enter="applyToolbarFilters">
        <template #prefix-icon><t-icon name="search" /></template>
      </t-input>
      <t-select v-model="filters.projectStatus" clearable placeholder="项目状态" :options="meta.projectStatuses" @change="applyToolbarFilters" />
      <t-select v-model="filters.settlementStatus" clearable placeholder="结算状态" :options="meta.settlementStatuses" @change="applyToolbarFilters" />
      <t-input v-model="filters.managerName" clearable placeholder="负责人" @keyup.enter="applyToolbarFilters" />
      <label class="toolbar-check">
        <input v-model="filters.onlyMissingDocuments" type="checkbox" @change="applyToolbarFilters" />
        仅看资料不齐
      </label>
      <t-select v-model="filters.sort" :options="sortOptions" placeholder="排序" @change="applyToolbarFilters" />
      <t-button theme="primary" @click="applyToolbarFilters">查询</t-button>
      <t-button variant="outline" @click="resetFilters">重置</t-button>
    </section>

    <section v-if="activeFilterChips.length" class="active-filter-strip" aria-label="已应用筛选">
      <span>已应用筛选</span>
      <button v-for="chip in activeFilterChips" :key="chip.key" type="button" @click="clearActiveFilterChip(chip.key)">
        {{ chip.label }}：{{ chip.value }}
        <b aria-hidden="true">×</b>
      </button>
      <button type="button" class="active-filter-strip__clear" @click="resetFilters">清除全部</button>
    </section>

    <t-alert v-if="error" theme="error" :close="false" class="page-alert">
      <template #message>
        <div class="recoverable-alert">
          <div>
            <strong>数据加载失败</strong>
            <span>{{ error }}</span>
          </div>
          <t-button size="small" variant="outline" :loading="loading" @click="loadAll">重新加载</t-button>
        </div>
      </template>
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
            <span>当前显示 {{ displayRecords.length }} 条 / 共 {{ total }} 条</span>
            <span>第 {{ page }} / {{ totalPages }} 页</span>
          </div>
        </div>

        <div class="list-utility-bar">
          <div class="saved-views" aria-label="保存的筛选方案">
            <button type="button" :class="{ active: activeSavedView === 'all' }" @click="applySavedProjectView('all')">全部项目</button>
            <button type="button" :class="{ active: activeSavedView === 'risk' }" @click="applySavedProjectView('risk')">风险优先</button>
            <button type="button" :class="{ active: activeSavedView === 'audit' }" @click="applySavedProjectView('audit')">已进审计</button>
          </div>
          <div v-if="savedFilterViews.length" class="custom-views" aria-label="我的筛选方案">
            <span
              v-for="view in savedFilterViews"
              :key="view.id"
              class="custom-view-chip"
              :class="{ active: activeCustomFilterId === view.id }"
            >
              <button type="button" @click="applySavedFilterView(view)">{{ view.name }}</button>
              <button type="button" aria-label="删除筛选方案" @click="deleteSavedFilterView(view)">×</button>
            </span>
          </div>
          <div class="table-tools">
            <span v-if="selectedRecords.length">已选 {{ selectedRecords.length }} 项</span>
            <t-button size="small" variant="outline" :disabled="displayRecords.length === 0" @click="selectCurrentPage">选择当前页</t-button>
            <t-button size="small" variant="outline" :disabled="selectedRecords.length === 0" @click="batchMarkFocus">标记关注</t-button>
            <t-button
              size="small"
              theme="primary"
              variant="outline"
              :loading="batchAuditing"
              :disabled="batchAuditCandidates.length === 0"
              @click="batchStartAudit"
            >
              批量发起审计
            </t-button>
            <t-button size="small" variant="text" :disabled="selectedRecords.length === 0" @click="clearProjectSelection">清空选择</t-button>
            <t-button size="small" variant="outline" @click="saveCurrentFilterView">保存筛选</t-button>
            <t-select v-model="groupBy" :options="projectGroupOptions" size="small" style="width: 138px" />
            <t-button size="small" variant="outline" @click="columnSettingsVisible = !columnSettingsVisible">列显示</t-button>
          </div>
        </div>

        <div v-if="columnSettingsVisible" class="column-settings-panel">
          <label v-for="column in configurableColumns" :key="column.colKey">
            <input
              type="checkbox"
              :checked="visibleProjectColumnKeys.includes(String(column.colKey))"
              @change="toggleProjectColumn(String(column.colKey))"
            />
            {{ column.title }}
          </label>
        </div>

        <StatePanel
          v-if="displayRecords.length === 0"
          class="view-empty-state"
          state="empty"
          title="当前筛选下暂无项目"
          description="可以调整筛选条件，或切换到全部项目查看完整台账。"
        />

        <div v-else class="project-table-groups" :class="{ 'project-table-groups--plain': groupBy === 'none' }">
          <section v-for="group in groupedDisplayRecords" :key="group.key" class="project-table-group">
            <header v-if="groupBy !== 'none'" class="project-table-group__head">
              <div>
                <strong>{{ group.label }}</strong>
                <span>{{ group.hint }}</span>
              </div>
              <em>{{ group.records.length }} 项</em>
            </header>
            <t-table
              :data="group.records"
              :columns="tableColumns"
              :loading="loading"
              :table-layout="'fixed'"
              :horizontal-scroll-affixed-bottom="true"
              bordered
              hover
            >
              <template #select="{ row }">
                <input
                  type="checkbox"
                  :checked="selectedProjectIds.includes(row.id)"
                  aria-label="选择项目"
                  @change="toggleProjectSelection(row.id)"
                />
              </template>
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
                  <span>一审：{{ materialStatusLabel(row.firstAuditMaterialStatus) }}</span>
                  <span>二审：{{ materialStatusLabel(row.secondAuditMaterialStatus) }}</span>
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
          </section>
        </div>

        <div v-if="displayRecords.length > 0" class="pager">
          <span>当前显示 {{ displayRecords.length }} 条 / 共 {{ total }} 条，第 {{ page }} 页</span>
          <t-select v-model="filters.pageSize" :options="pageSizeOptions" style="width: 120px" @change="loadRecords" />
          <t-button variant="outline" :disabled="page <= 1" @click="changePage(page - 1)">上一页</t-button>
          <t-button variant="outline" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</t-button>
        </div>
      </div>

      <section class="detail-panel" aria-label="项目详情">
        <template v-if="detailLoading">
          <StatePanel state="loading" title="正在加载项目详情" description="请稍候，正在读取该项目的资料和结算信息。" />
        </template>
        <template v-else-if="currentProject">
          <div class="detail-head">
            <div>
              <span class="stage-pill">{{ projectStatusLabel(currentProject.projectStatus) }}</span>
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

          <div class="project-detail-brief">
            <article>
              <span>项目负责人</span>
              <strong>{{ currentProject.managerName || '未分配' }}</strong>
              <em>{{ currentProject.contractorContact || '暂无联系电话' }}</em>
            </article>
            <article>
              <span>计划周期</span>
              <strong>{{ shortDate(currentProject.plannedStartDate) }} - {{ shortDate(currentProject.plannedEndDate) }}</strong>
              <em :class="{ overdue: isProjectOverdue(currentProject) }">{{ isProjectOverdue(currentProject) ? '已超过计划完成时间' : '按计划跟进' }}</em>
            </article>
            <article>
              <span>协作单位</span>
              <strong>{{ currentProject.contractorName || currentProject.ownerUnit || '未填写' }}</strong>
              <em>{{ currentProject.companyRole || '工程咨询' }}</em>
            </article>
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

          <div class="next-action-panel">
            <div class="section-head">
              <strong>下一步建议</strong>
              <span>根据资料、期限和审计联动状态生成</span>
            </div>
            <div class="next-action-list">
              <button v-for="item in projectActionHints" :key="item.label" type="button" :data-level="item.level" @click="item.action">
                <span>{{ item.label }}</span>
                <strong>{{ item.title }}</strong>
                <em>{{ item.description }}</em>
              </button>
            </div>
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
                <strong>{{ materialStatusLabel(currentProject.firstAuditMaterialStatus) }}</strong>
              </article>
              <article>
                <span>二审资料</span>
                <strong>{{ materialStatusLabel(currentProject.secondAuditMaterialStatus) }}</strong>
              </article>
            </div>

            <div class="link-box">
              <div>
                <span class="mini-label">审计联动</span>
                <strong>{{ currentProject.auditProjectId ? '已进入审计流程' : '尚未进入审计流程' }}</strong>
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

            <div class="project-timeline-card">
              <div class="section-head">
                <strong>项目推进脉络</strong>
                <span>按关键业务节点快速回看</span>
              </div>
              <div class="project-timeline">
                <article v-for="item in projectTimeline" :key="item.label" :class="{ done: item.done }">
                  <span />
                  <div>
                    <strong>{{ item.label }}</strong>
                    <p>{{ item.text }}</p>
                  </div>
                </article>
              </div>
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
                    <button
                      v-if="filesByCategory(category.categoryKey).length === 0"
                      type="button"
                      class="inline-empty-action"
                      @click="openFileDialog(category)"
                    >
                      <strong>{{ category.required ? '必填资料待补充' : '暂无归档资料' }}</strong>
                      <span>点击上传{{ category.categoryName }}</span>
                    </button>
                  </div>
                  <div class="doc-actions">
                    <t-button size="small" variant="outline" @click="openFileDialog(category)">上传资料</t-button>
                    <span>{{ filesByCategory(category.categoryKey).length ? `${filesByCategory(category.categoryKey).length} 份资料` : '待补充' }}</span>
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
            <div v-if="(currentProject.files || []).length === 0" class="detail-empty-action">
              <strong>当前项目还没有上传资料</strong>
              <span>建议先上传合同、招投标、过程资料或结算资料，后续审计会直接引用这些文件。</span>
              <t-button size="small" theme="primary" @click="openFileDialog()">上传资料</t-button>
            </div>
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
            <div v-if="(currentProject.settlements || []).length === 0" class="detail-empty-action">
              <strong>尚未维护付款结算记录</strong>
              <span>补充结算记录后，可以在项目台账中同步查看付款进度和结算状态。</span>
              <t-button size="small" theme="primary" @click="openSettlementDialog()">新增结算</t-button>
            </div>
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
            <div v-if="(currentProject.variations || []).length === 0" class="detail-empty-action">
              <strong>暂无变更签证记录</strong>
              <span>如项目发生工程量、范围或金额调整，可在这里记录变更签证。</span>
              <t-button size="small" theme="primary" @click="openVariationDialog()">新增签证</t-button>
            </div>
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
              <div v-if="(currentProject.logs || []).length === 0" class="detail-empty-action">
                <strong>暂无操作记录</strong>
                <span>保存项目信息、上传资料、发起审计或维护结算后，会自动形成操作记录。</span>
              </div>
            </div>
          </div>
        </template>
      </section>
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
      v-model:visible="confirmState.visible"
      :header="confirmState.title"
      :confirm-btn="{ content: confirmState.confirmText, theme: confirmState.danger ? 'danger' : 'primary', loading: confirmState.loading }"
      :cancel-btn="{ content: confirmState.cancelText }"
      width="520px"
      @confirm="confirmPrimaryAction"
      @cancel="closeConfirm"
      @close="closeConfirm"
    >
      <p class="confirm-message">{{ confirmState.message }}</p>
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
          <t-input v-model="variationForm.variationStatus" placeholder="例如：待确认、已确认、需更正" />
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
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageHeader from '@/components/PageHeader.vue'
import StatePanel from '@/components/StatePanel.vue'
import { MessagePlugin } from '@/ui/message'
import { formatWan } from '@/utils/format'
import { friendlyErrorMessage } from '@/utils/errors'
import type { ProjectDocumentCategory, ProjectFile, ProjectFilters, ProjectMeta, ProjectRecord, ProjectSettlement, ProjectSummary, ProjectVariation, WorkItem } from '@/types'
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
  fetchWorkItems,
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
type BuiltInProjectView = 'all' | 'risk' | 'audit'
type ProjectGroupBy = 'none' | 'status' | 'owner' | 'audit'
type ProjectFilterChip = {
  key: string
  label: string
  value: string
}
type SavedProjectFilterView = {
  id: string
  name: string
  filters: ProjectFilters
}

const SAVED_PROJECT_FILTERS_KEY = 'project-management-saved-filters'

const baseTableColumns = [
  { colKey: 'select', title: '选择', width: 64, fixed: 'left' },
  { colKey: 'project', title: '项目', width: 320, fixed: 'left' },
  { colKey: 'status', title: '状态', width: 170 },
  { colKey: 'docs', title: '资料', width: 110 },
  { colKey: 'amount', title: '金额', width: 140 },
  { colKey: 'audit', title: '审计联动', width: 170 },
  { colKey: 'actions', title: '操作', width: 160, fixed: 'right' },
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

const projectGroupOptions = [
  { label: '不分组', value: 'none' },
  { label: '按项目状态', value: 'status' },
  { label: '按负责人', value: 'owner' },
  { label: '按审计联动', value: 'audit' },
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
  onlyAuditLinked: false,
  onlyRisk: false,
  onlyUpcomingDue: false,
  onlyMonthlyNew: false,
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
const batchAuditing = ref(false)
const error = ref('')
const columnSettingsVisible = ref(false)
const selectedProjectIds = ref<string[]>([])
const activeSavedView = ref<BuiltInProjectView>('all')
const activeCustomFilterId = ref('')
const savedFilterViews = ref<SavedProjectFilterView[]>([])
const groupBy = ref<ProjectGroupBy>('none')
const visibleProjectColumnKeys = ref(['select', 'project', 'status', 'docs', 'amount', 'audit', 'actions'])
const workItems = ref<WorkItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const activeTab = ref<DetailTab>('overview')
const activeSummaryKey = ref('')
const canDelete = true

const projectDialog = reactive({ visible: false, mode: 'create' as 'create' | 'edit', saving: false })
const confirmState = reactive({
  visible: false,
  title: '',
  message: '',
  confirmText: '确认',
  cancelText: '取消',
  danger: false,
  loading: false,
  onConfirm: null as null | (() => void | Promise<void>),
})
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
const tableColumns = computed(() => baseTableColumns.filter((column) => visibleProjectColumnKeys.value.includes(String(column.colKey))))
const configurableColumns = computed(() => baseTableColumns.filter((column) => !['select', 'project', 'actions'].includes(String(column.colKey))))
const displayRecords = computed(() => records.value)
const activeFilterChips = computed<ProjectFilterChip[]>(() => {
  const chips: ProjectFilterChip[] = []
  if (filters.keyword) chips.push({ key: 'keyword', label: '关键词', value: filters.keyword })
  if (filters.projectStatus) chips.push({ key: 'projectStatus', label: '项目状态', value: projectStatusLabel(filters.projectStatus) })
  if (filters.settlementStatus) chips.push({ key: 'settlementStatus', label: '结算状态', value: settlementStatusLabel(filters.settlementStatus) })
  if (filters.managerName) chips.push({ key: 'managerName', label: '负责人', value: filters.managerName })
  if (filters.onlyMissingDocuments) chips.push({ key: 'onlyMissingDocuments', label: '资料状态', value: '仅看资料不齐' })
  if (filters.onlyAuditLinked) chips.push({ key: 'onlyAuditLinked', label: '审计联动', value: '已进入审计流程' })
  if (filters.onlyRisk) chips.push({ key: 'onlyRisk', label: '风险范围', value: '风险优先' })
  if (filters.onlyUpcomingDue) chips.push({ key: 'onlyUpcomingDue', label: '计划时间', value: '7 天内到期' })
  if (filters.onlyMonthlyNew) chips.push({ key: 'onlyMonthlyNew', label: '创建时间', value: '本月新增' })
  if (filters.sort && filters.sort !== 'updatedAt') {
    chips.push({ key: 'sort', label: '排序', value: sortOptions.find((item) => item.value === filters.sort)?.label || filters.sort })
  }
  return chips
})
const groupedDisplayRecords = computed(() => {
  if (groupBy.value === 'none') {
    return [{ key: 'all', label: '全部项目', hint: '当前筛选结果', records: displayRecords.value }]
  }
  const groups = new Map<string, ProjectRecord[]>()
  for (const record of displayRecords.value) {
    const key = projectGroupKey(record)
    groups.set(key, [...(groups.get(key) || []), record])
  }
  return Array.from(groups.entries())
    .map(([key, groupRecords]) => ({
      key,
      label: projectGroupLabel(key),
      hint: projectGroupHint(key, groupRecords),
      records: groupRecords,
    }))
    .sort((a, b) => {
      if (a.key === 'unassigned') return 1
      if (b.key === 'unassigned') return -1
      return b.records.length - a.records.length || a.label.localeCompare(b.label, 'zh-CN')
    })
})
const selectedRecords = computed(() => displayRecords.value.filter((record) => selectedProjectIds.value.includes(record.id)))
const batchAuditCandidates = computed(() => selectedRecords.value.filter((record) => !record.auditProjectId))
const projectActionHints = computed(() => {
  const project = currentProject.value
  if (!project) return []
  const items: Array<{ label: string; title: string; description: string; level: string; action: () => void }> = []
  if (project.missingRequiredCount > 0) {
    items.push({
      label: '资料补齐',
      title: `仍缺 ${project.missingRequiredCount} 类资料`,
      description: '先补齐关键资料，避免影响审计和结算推进。',
      level: 'warning',
      action: () => { activeTab.value = 'files' },
    })
  }
  if (isProjectOverdue(project)) {
    items.push({
      label: '期限风险',
      title: '计划完成时间已超期',
      description: '建议优先核对责任人、计划时间和当前处理节点。',
      level: 'danger',
      action: () => { activeTab.value = 'overview' },
    })
  }
  items.push(project.auditProjectId
    ? {
        label: '审计联动',
        title: '查看审计进度',
        description: '进入审计看板查看当前阶段、资料状态和操作记录。',
        level: 'primary',
        action: () => goAudit(project.auditProjectId),
      }
    : {
        label: '审计联动',
        title: '发起审计流程',
        description: '发起后会自动带入项目主数据，避免重复录入。',
        level: 'primary',
        action: () => startAudit(project),
      })
  if (!items.some((item) => item.level === 'warning' || item.level === 'danger')) {
    items.unshift({
      label: '项目状态',
      title: '当前项目可正常推进',
      description: '资料、期限和审计联动暂无明显阻塞。',
      level: 'success',
      action: () => { activeTab.value = 'overview' },
    })
  }
  return items.slice(0, 3)
})
const projectTimeline = computed(() => {
  const project = currentProject.value
  if (!project) return []
  return [
    {
      label: '项目建档',
      text: project.createdAt ? `${shortDate(project.createdAt)} 已纳入项目台账` : '已纳入项目台账',
      done: true,
    },
    {
      label: '资料归集',
      text: project.missingRequiredCount > 0 ? `仍需补充 ${project.missingRequiredCount} 类资料` : '关键资料已齐备',
      done: project.missingRequiredCount === 0,
    },
    {
      label: '结算推进',
      text: settlementStatusLabel(project.settlementStatus),
      done: ['approved', 'paid', 'completed'].includes(project.settlementStatus),
    },
    {
      label: '审计联动',
      text: project.auditProjectId ? '已进入审计流程' : '尚未进入审计流程',
      done: Boolean(project.auditProjectId),
    },
  ]
})

const summaryCards = computed(() => [
  { key: 'all', label: '项目总数', value: summary.totalProjects, hint: '全部项目主数据' },
  { key: 'active', label: '进行中', value: summary.activeProjects, hint: '正在推进的项目' },
  { key: 'settlement', label: '结算中', value: summary.settlementProjects, hint: '进入付款结算的项目' },
  { key: 'audit', label: '已联动审计', value: summary.auditLinkedProjects, hint: '已进入审计流程的项目' },
  { key: 'missing', label: '资料不齐', value: summary.missingDocuments, hint: '需要补资料的项目' },
  { key: 'variation', label: '变更签证金额', value: formatWan(summary.variationAmount || 0), hint: '汇总已维护的签证金额' },
])

const recentProjects = computed(() => [...records.value]
  .sort((a, b) => new Date(b.updatedAt || b.createdAt || 0).getTime() - new Date(a.updatedAt || a.createdAt || 0).getTime())
  .slice(0, 5))

const dueSoonProjects = computed(() => records.value.filter((record) => {
  if (!record.plannedEndDate) return false
  const today = new Date()
  const end = new Date(record.plannedEndDate)
  const diffDays = Math.ceil((end.getTime() - today.getTime()) / 86400000)
  return diffDays >= 0 && diffDays <= 7 && record.projectStatus !== 'completed'
}))

const riskProjects = computed(() => records.value.filter((record) => {
  return record.missingRequiredCount > 0 || isProjectOverdue(record) || record.settlementStatus === 'rejected'
}))

const projectWorkItems = computed(() => workItems.value.filter((item) => item.projectId || item.auditProjectId).slice(0, 4))

const ownerDistribution = computed(() => {
  const counts = new Map<string, number>()
  for (const record of records.value) {
    const owner = record.managerName || record.contractorName || '未分配'
    counts.set(owner, (counts.get(owner) || 0) + 1)
  }
  return Array.from(counts.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 6)
})

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

function materialStatusLabel(value: string) {
  const map: Record<string, string> = {
    pending: '待处理',
    not_started: '待处理',
    submitted: '已提交',
    complete: '已确认',
    completed: '已确认',
    confirmed: '已确认',
    missing: '待补充',
    rejected: '需更正',
  }
  return map[value] || value || '未设置'
}

function projectGroupKey(record: ProjectRecord) {
  if (groupBy.value === 'status') return record.projectStatus || 'unassigned'
  if (groupBy.value === 'owner') return record.managerName || record.contractorName || 'unassigned'
  if (groupBy.value === 'audit') return record.auditProjectId ? 'audit-linked' : 'audit-pending'
  return 'all'
}

function projectGroupLabel(key: string) {
  if (groupBy.value === 'status') return projectStatusLabel(key)
  if (groupBy.value === 'owner') return key === 'unassigned' ? '未分配负责人' : key
  if (groupBy.value === 'audit') return key === 'audit-linked' ? '已进入审计流程' : '尚未进入审计流程'
  return '全部项目'
}

function projectGroupHint(key: string, groupRecords: ProjectRecord[]) {
  if (groupBy.value === 'status') {
    const riskCount = groupRecords.filter((record) => record.missingRequiredCount > 0 || isProjectOverdue(record)).length
    return riskCount > 0 ? `${riskCount} 项需优先关注` : '当前状态下暂无明显阻塞'
  }
  if (groupBy.value === 'owner') {
    const linkedCount = groupRecords.filter((record) => record.auditProjectId).length
    return `${linkedCount} 项已进入审计流程`
  }
  if (groupBy.value === 'audit') {
    return key === 'audit-linked' ? '可进入审计看板查看阶段进度' : '可从项目详情发起审计'
  }
  return '当前筛选结果'
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

function shortDate(iso: string) {
  if (!iso) return '暂无更新'
  return new Date(iso).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

function isProjectOverdue(record: ProjectRecord) {
  if (!record.plannedEndDate || record.projectStatus === 'completed') return false
  const today = new Date().toISOString().slice(0, 10)
  return record.plannedEndDate < today
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
  filters.onlyAuditLinked = false
  filters.onlyRisk = false
  filters.onlyUpcomingDue = false
  filters.onlyMonthlyNew = false
  filters.sort = 'updatedAt'
  filters.page = 1
  filters.pageSize = 10
}

function normalizeProjectFilters(value: Partial<ProjectFilters> = {}): ProjectFilters {
  return {
    keyword: value.keyword || '',
    projectStatus: value.projectStatus || '',
    settlementStatus: value.settlementStatus || '',
    managerName: value.managerName || '',
    onlyMissingDocuments: Boolean(value.onlyMissingDocuments),
    onlyAuditLinked: Boolean(value.onlyAuditLinked),
    onlyRisk: Boolean(value.onlyRisk),
    onlyUpcomingDue: Boolean(value.onlyUpcomingDue),
    onlyMonthlyNew: Boolean(value.onlyMonthlyNew),
    sort: value.sort || 'updatedAt',
    page: Number(value.page || 1),
    pageSize: Number(value.pageSize || 10),
  }
}

function assignProjectFilters(value: Partial<ProjectFilters>) {
  Object.assign(filters, normalizeProjectFilters(value))
}

function snapshotProjectFilters(): ProjectFilters {
  return normalizeProjectFilters({
    ...filters,
    page: 1,
  })
}

function loadSavedFilterViews() {
  try {
    const raw = window.localStorage.getItem(SAVED_PROJECT_FILTERS_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw) as Array<Partial<SavedProjectFilterView>>
    savedFilterViews.value = parsed
      .filter((item) => item.id && item.name && item.filters)
      .slice(0, 8)
      .map((item) => ({
        id: String(item.id),
        name: String(item.name).slice(0, 20),
        filters: normalizeProjectFilters(item.filters || {}),
      }))
  } catch {
    savedFilterViews.value = []
  }
}

function persistSavedFilterViews() {
  window.localStorage.setItem(SAVED_PROJECT_FILTERS_KEY, JSON.stringify(savedFilterViews.value.slice(0, 8)))
}

function saveCurrentFilterView() {
  const name = window.prompt('为当前筛选方案命名，例如：本周待处理项目')
  const trimmed = name?.trim()
  if (!trimmed) return
  const id = `filter-${Date.now()}`
  const view = {
    id,
    name: trimmed.slice(0, 20),
    filters: snapshotProjectFilters(),
  }
  savedFilterViews.value = [view, ...savedFilterViews.value.filter((item) => item.name !== view.name)].slice(0, 8)
  persistSavedFilterViews()
  activeSavedView.value = 'all'
  activeCustomFilterId.value = id
  MessagePlugin.success('筛选方案已保存')
}

function applySavedFilterView(view: SavedProjectFilterView) {
  activeSavedView.value = 'all'
  activeCustomFilterId.value = view.id
  activeSummaryKey.value = 'custom'
  selectedProjectIds.value = []
  assignProjectFilters({ ...view.filters, page: 1 })
  loadRecords()
}

function openConfirm(options: {
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  danger?: boolean
  onConfirm: () => void | Promise<void>
}) {
  confirmState.visible = true
  confirmState.title = options.title
  confirmState.message = options.message
  confirmState.confirmText = options.confirmText || '确认'
  confirmState.cancelText = options.cancelText || '取消'
  confirmState.danger = Boolean(options.danger)
  confirmState.loading = false
  confirmState.onConfirm = options.onConfirm
}

function closeConfirm() {
  if (confirmState.loading) return
  confirmState.visible = false
  confirmState.onConfirm = null
}

async function confirmPrimaryAction() {
  const action = confirmState.onConfirm
  if (!action) {
    closeConfirm()
    return
  }
  confirmState.loading = true
  try {
    await action()
    confirmState.visible = false
    confirmState.onConfirm = null
  } finally {
    confirmState.loading = false
  }
}

function deleteSavedFilterView(view: SavedProjectFilterView) {
  openConfirm({
    title: '删除筛选方案？',
    message: `删除「${view.name}」后，不会影响项目数据，只会移除这个快捷筛选入口。`,
    confirmText: '删除方案',
    danger: true,
    onConfirm: () => {
      savedFilterViews.value = savedFilterViews.value.filter((item) => item.id !== view.id)
      if (activeCustomFilterId.value === view.id) activeCustomFilterId.value = ''
      persistSavedFilterViews()
      MessagePlugin.success('筛选方案已删除')
    },
  })
}

async function openProjectFromRoute() {
  const targetId = String(route.query.projectId || '')
  if (!targetId) return false
  const targetRecord = records.value.find((item) => item.id === targetId)
  await loadCurrentProject(targetRecord?.id || targetId)
  activeTab.value = 'overview'
  return true
}

function applyRouteFilters() {
  const query = route.query
  const view = String(query.view || '').trim()
  const projectStatus = String(query.projectStatus || '').trim()
  const sort = String(query.sort || '').trim()
  const managerName = String(query.managerName || '').trim()
  const onlyMissingDocuments = String(query.onlyMissingDocuments || '').trim()
  const onlyMonthlyNew = String(query.onlyMonthlyNew || '').trim()

  if (view === 'risk') {
    activeSummaryKey.value = 'risk'
    activeSavedView.value = 'risk'
    activeCustomFilterId.value = ''
    filters.onlyRisk = true
    filters.sort = 'plannedEndDate'
  } else if (view === 'audit') {
    activeSummaryKey.value = 'audit'
    activeSavedView.value = 'audit'
    activeCustomFilterId.value = ''
    filters.onlyAuditLinked = true
  } else if (view === 'due') {
    activeSummaryKey.value = 'due'
    activeSavedView.value = 'all'
    activeCustomFilterId.value = ''
    filters.onlyUpcomingDue = true
    filters.sort = 'plannedEndDate'
  }

  if (projectStatus) {
    filters.projectStatus = projectStatus
    activeSummaryKey.value = projectStatus
  }
  if (managerName) {
    filters.managerName = managerName
    activeSummaryKey.value = 'owner'
  }
  if (onlyMissingDocuments === '1' || onlyMissingDocuments === 'true') {
    filters.onlyMissingDocuments = true
    activeSummaryKey.value = 'missing'
  }
  if (onlyMonthlyNew === '1' || onlyMonthlyNew === 'true') {
    filters.onlyMonthlyNew = true
    activeSummaryKey.value = 'monthly'
    activeSavedView.value = 'all'
    activeCustomFilterId.value = ''
  }
  if (sort) filters.sort = sort
  filters.page = 1
}

function applySummaryFilter(key: string) {
  activeSummaryKey.value = key
  activeSavedView.value = 'all'
  activeCustomFilterId.value = ''
  selectedProjectIds.value = []
  filters.projectStatus = ''
  filters.settlementStatus = ''
  filters.onlyMissingDocuments = false
  filters.onlyAuditLinked = false
  filters.onlyRisk = false
  filters.onlyUpcomingDue = false
  filters.onlyMonthlyNew = false
  if (key === 'active') filters.projectStatus = 'active'
  else if (key === 'settlement') filters.settlementStatus = 'pending'
  else if (key === 'audit') filters.onlyAuditLinked = true
  else if (key === 'missing') filters.onlyMissingDocuments = true
  filters.page = 1
  loadRecords()
}

function applyToolbarFilters() {
  activeSavedView.value = 'all'
  activeCustomFilterId.value = ''
  activeSummaryKey.value = filters.onlyMissingDocuments ? 'missing' : ''
  selectedProjectIds.value = []
  filters.onlyAuditLinked = false
  filters.onlyRisk = false
  filters.onlyUpcomingDue = false
  filters.onlyMonthlyNew = false
  filters.page = 1
  loadRecords()
}

function clearActiveFilterChip(key: string) {
  activeSavedView.value = 'all'
  activeCustomFilterId.value = ''
  activeSummaryKey.value = ''
  selectedProjectIds.value = []
  if (key === 'keyword') filters.keyword = ''
  if (key === 'projectStatus') filters.projectStatus = ''
  if (key === 'settlementStatus') filters.settlementStatus = ''
  if (key === 'managerName') filters.managerName = ''
  if (key === 'onlyMissingDocuments') filters.onlyMissingDocuments = false
  if (key === 'onlyAuditLinked') filters.onlyAuditLinked = false
  if (key === 'onlyRisk') filters.onlyRisk = false
  if (key === 'onlyUpcomingDue') filters.onlyUpcomingDue = false
  if (key === 'onlyMonthlyNew') filters.onlyMonthlyNew = false
  if (key === 'sort') filters.sort = 'updatedAt'
  filters.page = 1
  loadRecords()
}

function applyDashboardAction(action: 'risk' | 'due' | 'missing') {
  activeSummaryKey.value = action
  activeSavedView.value = action === 'risk' ? 'risk' : 'all'
  activeCustomFilterId.value = ''
  selectedProjectIds.value = []
  filters.projectStatus = ''
  filters.settlementStatus = ''
  filters.managerName = ''
  filters.onlyMissingDocuments = action === 'missing'
  filters.onlyAuditLinked = false
  filters.onlyRisk = action === 'risk'
  filters.onlyUpcomingDue = action === 'due'
  filters.onlyMonthlyNew = false
  filters.sort = action === 'due' ? 'plannedEndDate' : 'updatedAt'
  filters.page = 1
  loadRecords()
}

function applySavedProjectView(view: BuiltInProjectView) {
  activeSavedView.value = view
  activeCustomFilterId.value = ''
  activeSummaryKey.value = view
  selectedProjectIds.value = []
  filters.keyword = ''
  filters.projectStatus = ''
  filters.settlementStatus = ''
  filters.managerName = ''
  filters.onlyMissingDocuments = false
  filters.onlyAuditLinked = view === 'audit'
  filters.onlyRisk = view === 'risk'
  filters.onlyUpcomingDue = false
  filters.onlyMonthlyNew = false
  filters.sort = view === 'risk' ? 'plannedEndDate' : 'updatedAt'
  filters.page = 1
  if (view === 'audit') {
    MessagePlugin.success('已切换到已进审计项目视图')
  }
  loadRecords()
}

function toggleProjectColumn(key: string) {
  if (['select', 'project', 'actions'].includes(key)) return
  if (visibleProjectColumnKeys.value.includes(key)) {
    visibleProjectColumnKeys.value = visibleProjectColumnKeys.value.filter((item) => item !== key)
  } else {
    const order = baseTableColumns.map((column) => String(column.colKey))
    visibleProjectColumnKeys.value = [...visibleProjectColumnKeys.value, key].sort((a, b) => order.indexOf(a) - order.indexOf(b))
  }
}

function toggleProjectSelection(id: string) {
  selectedProjectIds.value = selectedProjectIds.value.includes(id)
    ? selectedProjectIds.value.filter((item) => item !== id)
    : [...selectedProjectIds.value, id]
}

function selectCurrentPage() {
  selectedProjectIds.value = Array.from(new Set([...selectedProjectIds.value, ...displayRecords.value.map((record) => record.id)]))
  MessagePlugin.success(`已选择当前显示的 ${displayRecords.value.length} 个项目`)
}

function clearProjectSelection() {
  selectedProjectIds.value = []
}

function isEditableTarget(target: EventTarget | null) {
  const element = target as HTMLElement | null
  if (!element) return false
  const tag = element.tagName.toLowerCase()
  return tag === 'input' || tag === 'textarea' || tag === 'select' || element.isContentEditable
}

function focusProjectKeywordInput() {
  const input = document.querySelector<HTMLInputElement>('.project-keyword-input input')
  input?.focus()
  input?.select()
}

function handleProjectKeyboard(event: KeyboardEvent) {
  const shouldFocusSearch = event.key === '/' || ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k')
  if (shouldFocusSearch && !isEditableTarget(event.target)) {
    event.preventDefault()
    focusProjectKeywordInput()
    return
  }
  if (event.key !== 'Escape') return
  if (columnSettingsVisible.value) {
    columnSettingsVisible.value = false
    return
  }
  if (selectedProjectIds.value.length) {
    selectedProjectIds.value = []
    MessagePlugin.success('已清空选择')
  }
}

function batchMarkFocus() {
  if (!selectedRecords.value.length) {
    MessagePlugin.warning('请先选择需要处理的项目')
    return
  }
  MessagePlugin.success(`已将 ${selectedRecords.value.length} 个项目加入本次关注`)
}

async function batchStartAudit() {
  if (!selectedRecords.value.length) {
    MessagePlugin.warning('请先选择需要发起审计的项目')
    return
  }
  const candidates = batchAuditCandidates.value
  const skipped = selectedRecords.value.length - candidates.length
  if (!candidates.length) {
    MessagePlugin.warning('所选项目均已进入审计流程，无需重复发起')
    return
  }
  const message = skipped
    ? `确认将 ${candidates.length} 个项目发起审计流程？另有 ${skipped} 个已进入审计流程，将自动跳过。`
    : `确认将 ${candidates.length} 个项目发起审计流程？系统会自动带入项目主数据。`
  openConfirm({
    title: '批量发起审计？',
    message,
    confirmText: '发起审计',
    onConfirm: async () => {
      await runBatchStartAudit(candidates)
    },
  })
}

async function runBatchStartAudit(candidates: ProjectRecord[]) {
  batchAuditing.value = true
  try {
    for (const record of candidates) {
      await startProjectAudit(record.id)
    }
    MessagePlugin.success(`已发起 ${candidates.length} 个项目的审计流程`)
    clearProjectSelection()
    await loadSummary()
    await loadRecords()
    if (currentProject.value) await loadCurrentProject(currentProject.value.id)
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '批量发起审计失败，请稍后重试或联系管理员'))
  } finally {
    batchAuditing.value = false
  }
}

function filterByOwner(owner: string) {
  filters.managerName = owner === '未分配' ? '' : owner
  filters.projectStatus = ''
  filters.settlementStatus = ''
  filters.onlyMissingDocuments = false
  filters.onlyAuditLinked = false
  filters.onlyRisk = false
  filters.onlyUpcomingDue = false
  filters.onlyMonthlyNew = false
  filters.page = 1
  activeSummaryKey.value = 'owner'
  activeSavedView.value = 'all'
  activeCustomFilterId.value = ''
  selectedProjectIds.value = []
  loadRecords()
}

async function openProjectWorkItem(item: WorkItem) {
  if (item.projectId) {
    const local = records.value.find((record) => record.id === item.projectId)
    if (local) {
      await selectProject(local)
    } else {
      await loadCurrentProject(item.projectId)
      activeTab.value = 'overview'
    }
    MessagePlugin.success('已定位到待处理项目')
    return
  }
  if (item.auditProjectId) {
    router.push({ path: '/audit', query: { projectId: item.auditProjectId } })
  }
}

function resetFilters() {
  activeSummaryKey.value = ''
  activeSavedView.value = 'all'
  activeCustomFilterId.value = ''
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

async function loadWorkItems() {
  try {
    workItems.value = await fetchWorkItems(40)
  } catch {
    workItems.value = []
  }
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
    selectedProjectIds.value = selectedProjectIds.value.filter((id) => displayRecords.value.some((item) => item.id === id))
    total.value = result.total
    page.value = result.page
    pageSize.value = result.pageSize
    if (!currentProject.value || !records.value.find((item) => item.id === currentProject.value?.id)) {
      if (await openProjectFromRoute()) {
        return
      }
      if (records.value[0]) {
        await loadCurrentProject(records.value[0].id)
      } else {
        currentProject.value = null
      }
    }
  } catch (err) {
    error.value = friendlyErrorMessage(err, '项目列表加载失败，请稍后重试或联系管理员')
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
    currentProject.value = null
    MessagePlugin.error(friendlyErrorMessage(err, '项目详情加载失败，请稍后重试或联系管理员'))
  } finally {
    detailLoading.value = false
  }
}

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadMeta(), loadSummary(), loadWorkItems()])
    applyRouteFilters()
    await loadRecords()
  } catch (err) {
    error.value = friendlyErrorMessage(err, '数据加载失败，请稍后重试或联系管理员')
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
    MessagePlugin.error(friendlyErrorMessage(err, '项目保存失败，请稍后重试或联系管理员'))
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
  openConfirm({
    title: '发起审计流程？',
    message: `将「${record.projectName}」发起审计流程，系统会自动带入项目名称、编号、负责人和金额等主数据。`,
    confirmText: '发起审计',
    onConfirm: async () => {
      await runStartAudit(record)
    },
  })
}

async function runStartAudit(record: ProjectRecord) {
  auditStarting.value = true
  try {
    const auditProject = await startProjectAudit(record.id)
    MessagePlugin.success('已发起审计流程')
    await loadSummary()
    await loadRecords()
    await loadCurrentProject(record.id)
    goAudit(auditProject.id)
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '发起审计失败，请稍后重试或联系管理员'))
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
    MessagePlugin.error(friendlyErrorMessage(err, '资料上传失败，请检查文件后重试'))
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
    MessagePlugin.error(friendlyErrorMessage(err, '结算保存失败，请稍后重试或联系管理员'))
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
    MessagePlugin.error(friendlyErrorMessage(err, '签证保存失败，请稍后重试或联系管理员'))
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
    MessagePlugin.error(friendlyErrorMessage(err, '资料名称更新失败，请稍后重试'))
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
    MessagePlugin.error(friendlyErrorMessage(err, '预览失败，请下载后查看'))
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
    MessagePlugin.error(friendlyErrorMessage(err, '下载失败，请稍后重试'))
  }
}

async function confirmDeleteProject(record: ProjectRecord) {
  openConfirm({
    title: '删除项目？',
    message: `删除「${record.projectName}」后，该项目将不再出现在项目台账中。请确认已不需要继续跟踪。`,
    confirmText: '删除项目',
    danger: true,
    onConfirm: async () => {
      await runDeleteProject(record)
    },
  })
}

async function runDeleteProject(record: ProjectRecord) {
  try {
    await deleteProjectRecord(record.id)
    MessagePlugin.success('项目已删除')
    await loadAll()
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '项目删除失败，请稍后重试或联系管理员'))
  }
}

async function confirmDeleteFile(file: ProjectFile) {
  openConfirm({
    title: '删除资料？',
    message: `删除「${file.displayName}」后，该资料将不再出现在当前项目资料中心。`,
    confirmText: '删除资料',
    danger: true,
    onConfirm: async () => {
      await runDeleteFile(file)
    },
  })
}

async function runDeleteFile(file: ProjectFile) {
  try {
    await deleteProjectFile(file.id)
    MessagePlugin.success('资料已删除')
    if (currentProject.value) await loadCurrentProject(currentProject.value.id)
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '资料删除失败，请稍后重试'))
  }
}

function goAudit(id: string) {
  router.push({ path: '/audit', query: { projectId: id } })
}

onMounted(() => {
  loadSavedFilterViews()
  window.addEventListener('keydown', handleProjectKeyboard)
  loadAll()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleProjectKeyboard)
})

watch(
  () => route.query.projectId,
  async (projectId, previousProjectId) => {
    if (!projectId || projectId === previousProjectId) return
    await openProjectFromRoute()
  },
)
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

.project-dashboard {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(260px, 0.8fr) minmax(280px, 0.9fr);
  gap: var(--space-3);
}

.dashboard-panel {
  min-width: 0;
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}

.dashboard-panel--hero {
  background: linear-gradient(135deg, var(--color-brand-50), var(--bg-surface) 58%);
  border-color: var(--color-brand-200);
}

.dashboard-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.dashboard-panel__head h3 {
  margin: 0;
  font-size: var(--text-lg);
}

.dashboard-panel__head p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.focus-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-2);
}

.focus-metrics button,
.owner-list button,
.recent-list button {
  border: 1px solid var(--border-color);
  background: color-mix(in srgb, var(--bg-surface) 86%, transparent);
  cursor: pointer;
  text-align: left;
}

.focus-metrics button {
  display: grid;
  gap: 4px;
  padding: var(--space-3);
}

.focus-metrics span,
.focus-metrics em,
.owner-list span,
.recent-list span,
.quiet-empty {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
}

.focus-metrics strong {
  font-size: var(--text-2xl);
}

.owner-list,
.recent-list {
  display: grid;
  gap: 8px;
}

.owner-list button,
.recent-list button {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-2);
  align-items: center;
  padding: 9px 10px;
}

.recent-list button {
  grid-template-columns: minmax(0, 1fr);
}

.recent-list strong,
.recent-list span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-work-items {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}

.project-work-items__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.project-work-items__head h3 {
  margin: 4px 0;
  font-size: var(--text-lg);
}

.project-work-items__head p {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.project-work-list {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
}

.project-work-card {
  position: relative;
  display: grid;
  gap: 5px;
  min-width: 0;
  padding: var(--space-3);
  text-align: left;
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
  border-left: 3px solid var(--color-brand-500);
  cursor: pointer;
}

.project-work-card[data-level='danger'] {
  border-left-color: var(--color-danger);
}

.project-work-card[data-level='warning'] {
  border-left-color: var(--color-warning);
}

.project-work-card span,
.project-work-card em {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
}

.project-work-card strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-sm);
}

.project-work-card b {
  color: var(--color-brand-600);
  font-size: var(--text-xs);
}

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

.active-filter-strip {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding: 0 var(--space-1);
}

.active-filter-strip > span {
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.active-filter-strip button {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 28px;
  padding: 4px 9px;
  color: var(--text-secondary);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  cursor: pointer;
  font-size: var(--text-xs);
}

.active-filter-strip button:hover,
.active-filter-strip button:focus-visible {
  color: var(--color-brand-600);
  border-color: var(--color-brand-300);
  outline: none;
}

.active-filter-strip b {
  color: var(--text-tertiary);
  font-size: var(--text-sm);
  line-height: 1;
}

.active-filter-strip__clear {
  color: var(--color-brand-600) !important;
  border-color: transparent !important;
  background: transparent !important;
}

.page-alert {
  border-radius: var(--radius-md);
}

.recoverable-alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}

.recoverable-alert > div {
  display: grid;
  gap: 2px;
}

.recoverable-alert strong {
  color: var(--text-primary);
  font-size: var(--text-sm);
}

.recoverable-alert span,
.confirm-message {
  color: var(--text-secondary);
  font-size: var(--text-sm);
  line-height: 1.7;
}

.confirm-message {
  margin: 0;
}

.workspace {
  display: grid;
  grid-template-columns: 1fr;
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

.list-utility-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin: var(--space-4) 0 var(--space-3);
  padding: var(--space-2);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
}

.saved-views,
.custom-views,
.table-tools {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.saved-views button {
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 6px 10px;
  font-size: var(--text-xs);
}

.saved-views button.active {
  color: var(--color-brand-600);
  background: var(--bg-surface);
  border-color: var(--color-brand-300);
}

.custom-views {
  flex: 1 1 260px;
}

.custom-view-chip {
  display: inline-flex;
  align-items: center;
  overflow: hidden;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
}

.custom-view-chip.active {
  border-color: var(--color-brand-300);
  box-shadow: 0 0 0 2px var(--color-brand-50);
}

.custom-view-chip button {
  min-height: 28px;
  padding: 5px 8px;
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: var(--text-xs);
}

.custom-view-chip button:first-child {
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.custom-view-chip button:last-child {
  color: var(--text-tertiary);
  border-left: 1px solid var(--border-color);
}

.custom-view-chip.active button:first-child,
.custom-view-chip button:hover,
.custom-view-chip button:focus-visible {
  color: var(--color-brand-600);
  outline: none;
}

.table-tools span {
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.column-settings-panel {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
  padding: var(--space-3);
  background: var(--bg-surface);
  border: 1px dashed var(--border-color);
}

.column-settings-panel label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.view-empty-state {
  margin-top: var(--space-3);
}

.project-table-groups {
  display: grid;
  gap: var(--space-4);
}

.project-table-groups--plain {
  gap: 0;
}

.project-table-group {
  min-width: 0;
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
}

.project-table-groups--plain .project-table-group {
  border: 0;
}

.project-table-group__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--bg-muted);
  border-bottom: 1px solid var(--border-color);
}

.project-table-group__head div {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.project-table-group__head strong {
  color: var(--text-primary);
  font-size: var(--text-sm);
}

.project-table-group__head span,
.project-table-group__head em {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
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
  position: static;
}

.detail-metrics {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-2);
  margin: var(--space-4) 0;
}

.project-detail-brief {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.project-detail-brief article {
  display: grid;
  gap: 4px;
  padding: var(--space-3);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
}

.project-detail-brief span,
.project-detail-brief em {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
}

.project-detail-brief strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-md);
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

.next-action-panel {
  display: grid;
  gap: var(--space-3);
  margin-top: var(--space-4);
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
}

.next-action-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}

.next-action-list button {
  display: grid;
  gap: 5px;
  min-width: 0;
  padding: var(--space-3);
  text-align: left;
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
  border-left: 3px solid var(--color-brand-500);
  cursor: pointer;
}

.next-action-list button[data-level='danger'] { border-left-color: var(--color-danger); }
.next-action-list button[data-level='warning'] { border-left-color: var(--color-warning); }
.next-action-list button[data-level='success'] { border-left-color: var(--color-success); }

.next-action-list button:hover,
.next-action-list button:focus-visible {
  border-color: var(--color-brand-300);
  box-shadow: var(--shadow-elevated);
  outline: none;
}

.next-action-list span,
.next-action-list em {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
}

.next-action-list strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-sm);
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

.stage-pill {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 4px 8px;
  margin-bottom: 8px;
  color: var(--color-brand-600);
  background: var(--color-brand-50);
  border: 1px solid var(--color-brand-200);
  font-size: var(--text-xs);
}

.mini-label {
  color: var(--color-brand-600);
  font-size: var(--text-xs);
}

.project-timeline-card {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
}

.project-timeline {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
}

.project-timeline article {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  min-width: 0;
}

.project-timeline article > span {
  width: 10px;
  height: 10px;
  margin-top: 4px;
  border-radius: 999px;
  background: var(--text-tertiary);
}

.project-timeline article.done > span {
  background: var(--color-success);
}

.project-timeline strong {
  display: block;
  font-size: var(--text-sm);
}

.project-timeline p {
  margin: 3px 0 0;
  color: var(--text-secondary);
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

.inline-empty-action {
  display: grid;
  gap: 3px;
  min-height: 42px;
  padding: 7px 9px;
  text-align: left;
  background: var(--bg-surface);
  border: 1px dashed var(--border-color);
  color: var(--text-secondary);
  cursor: pointer;
}

.inline-empty-action:hover,
.inline-empty-action:focus-visible {
  border-color: var(--color-brand-300);
  color: var(--color-brand-600);
  outline: none;
}

.inline-empty-action strong {
  color: var(--text-primary);
  font-size: var(--text-xs);
}

.inline-empty-action span {
  color: inherit;
  font-size: var(--text-xs);
}

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

.detail-empty-action {
  display: grid;
  gap: 8px;
  justify-items: start;
  padding: var(--space-4);
  color: var(--text-secondary);
  background: var(--bg-muted);
  border: 1px dashed var(--border-color);
}

.detail-empty-action strong {
  color: var(--text-primary);
  font-size: var(--text-sm);
}

.detail-empty-action span {
  max-width: 680px;
  font-size: var(--text-xs);
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
  .project-dashboard { grid-template-columns: 1fr; }
  .project-work-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .toolbar { grid-template-columns: 1fr 1fr 1fr 1fr; }
  .workspace { grid-template-columns: 1fr; }
  .detail-panel { position: static; }
}

@media (max-width: 760px) {
  .summary-grid,
  .document-grid,
  .detail-metrics,
  .project-detail-brief,
  .project-timeline,
  .next-action-list,
  .info-grid,
  .dialog-grid { grid-template-columns: 1fr; }
  .dialog-span-2,
  .dialog-hint { grid-column: span 1; }
  .toolbar {
    grid-template-columns: 1fr;
  }
  .pager,
  .link-box,
  .list-utility-bar,
  .project-work-items__head,
  .panel-head,
  .detail-head {
    align-items: stretch;
    flex-direction: column;
  }
  .project-work-list { grid-template-columns: 1fr; }
}
</style>

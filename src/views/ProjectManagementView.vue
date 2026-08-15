<template>
  <div class="project-management">
    <PageHeader
      :title="activeWorkspaceViewMeta.label"
      :description="activeWorkspaceViewMeta.description"
    >
      <template #meta>
        <span class="view-path">项目管理 / {{ activeWorkspaceViewMeta.section }}</span>
        <ATag variant="light" theme="primary">{{ displayRecords.length }} 个项目</ATag>
      </template>
      <template #actions>
        <AButton variant="outline" :loading="loading" @click="loadAll">
          <template #icon><AIcon name="refresh" /></template>
          刷新
        </AButton>
        <AButton v-if="authStore.isEditor" theme="primary" @click="openProjectForm()">
          <template #icon><AIcon name="add" /></template>
          新建项目
        </AButton>
      </template>
    </PageHeader>

    <section class="toolbar view-toolbar" :class="{ 'view-toolbar--ledger': activeWorkspaceView === 'ledger' }">
      <div v-if="activeWorkspaceView === 'ledger'" class="ledger-command-row">
        <AInput v-model="filters.keyword" class="project-keyword-input" clearable placeholder="搜索项目名称、编号、施工单位、负责人" @keyup.enter="applyToolbarFilters">
          <template #prefix-icon><AIcon name="search" /></template>
        </AInput>
        <button
          type="button"
          class="ledger-filter-trigger"
          :class="{ active: advancedFiltersVisible || advancedFilterCount > 0 }"
          :aria-expanded="advancedFiltersVisible"
          @click="advancedFiltersVisible = !advancedFiltersVisible"
        >
          <AIcon name="filter" />
          <span>筛选</span>
          <b v-if="advancedFilterCount">{{ advancedFilterCount }}</b>
        </button>
        <div class="ledger-sort-control">
          <AIcon name="sort" />
          <ASelect v-model="filters.sort" :options="sortOptions" placeholder="排序" @change="applyToolbarFilters" />
        </div>
        <AButton theme="primary" @click="applyToolbarFilters">查询</AButton>
      </div>

      <div v-else class="view-toolbar__filters">
        <AInput v-model="filters.keyword" class="project-keyword-input" clearable placeholder="搜索项目名称、编号、施工单位、负责人" @keyup.enter="applyToolbarFilters">
          <template #prefix-icon><AIcon name="search" /></template>
        </AInput>
        <ASelect v-model="filters.projectStatus" clearable placeholder="项目状态" :options="projectStatusOptions" @change="applyToolbarFilters" />
        <ASelect v-model="filters.settlementStatus" clearable placeholder="结算状态" :options="settlementStatusOptions" @change="applyToolbarFilters" />
        <AInput v-model="filters.managerName" clearable placeholder="负责人" @keyup.enter="applyToolbarFilters" />
        <ASelect v-model="filters.sort" :options="sortOptions" placeholder="排序" @change="applyToolbarFilters" />
        <AButton theme="primary" @click="applyToolbarFilters">查询</AButton>
        <AButton variant="outline" @click="resetFilters">重置</AButton>
        <AButton size="small" variant="text" @click="saveCurrentFilterView">保存视图</AButton>
      </div>

      <div v-if="activeWorkspaceView === 'ledger' && advancedFiltersVisible" class="ledger-advanced-filters">
        <label>
          <span>项目状态</span>
          <ASelect v-model="filters.projectStatus" clearable placeholder="全部状态" :options="projectStatusOptions" />
        </label>
        <label>
          <span>结算状态</span>
          <ASelect v-model="filters.settlementStatus" clearable placeholder="全部状态" :options="settlementStatusOptions" />
        </label>
        <label>
          <span>项目经理</span>
          <AInput v-model="filters.managerName" clearable placeholder="输入姓名" @keyup.enter="applyToolbarFilters" />
        </label>
        <button type="button" class="ledger-clear-filters" :disabled="advancedFilterCount === 0" @click="resetFilters">清除筛选</button>
      </div>

      <div v-if="activeWorkspaceView === 'ledger'" class="view-toolbar__utilities" :class="{ 'is-selection-mode': selectedRecords.length > 0 }">
        <template v-if="selectedRecords.length">
          <div class="ledger-selection-context" role="status">
            <span class="ledger-selection-context__count"><AIcon name="task" />已选 <strong>{{ selectedRecords.length }}</strong> 项</span>
            <button type="button" @click="selectCurrentPage">选择当前页</button>
            <button type="button" @click="batchMarkFocus">标记关注</button>
            <button v-if="authStore.isEditor" type="button" class="primary" :disabled="batchAuditing" @click="batchStartAudit">{{ batchAuditing ? '正在发起审计' : '发起审计' }}</button>
            <button type="button" @click="clearProjectSelection">清空选择</button>
          </div>
        </template>
        <template v-else>
          <div class="saved-views" aria-label="快捷筛选">
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
          <div class="ledger-view-actions">
            <div class="ledger-group-control">
              <AIcon name="list" />
              <ASelect v-model="groupBy" :options="projectGroupOptions" size="small" />
            </div>
            <button type="button" class="ledger-save-view" @click="saveCurrentFilterView"><AIcon name="save" />保存当前视图</button>
          </div>
        </template>
      </div>
    </section>

    <section v-if="savedFilterViews.length && activeWorkspaceView !== 'ledger'" class="personal-view-strip" aria-label="我的视图">
      <span>我的视图</span>
      <button v-for="view in savedFilterViews" :key="view.id" type="button" :class="{ active: activeCustomFilterId === view.id }" @click="applySavedFilterView(view)">{{ view.name }}</button>
    </section>

    <section v-if="showProjectEmptyOnboarding" class="project-empty-onboarding">
      <div>
        <span class="mini-label">开始使用</span>
        <h3>项目库还没有项目</h3>
        <p>先建立项目主档案，再到资料中心补充资料，并按需从项目主档案发起审计流程。</p>
      </div>
      <AButton v-if="authStore.isEditor" type="primary" @click="openProjectForm()">手工创建第一个项目</AButton>
    </section>

    <section v-if="activeFilterChips.length && activeWorkspaceView !== 'ledger'" class="active-filter-strip" aria-label="已应用筛选">
      <span>已应用筛选</span>
      <button v-for="chip in activeFilterChips" :key="chip.key" type="button" @click="clearActiveFilterChip(chip.key)">
        {{ chip.label }}：{{ chip.value }}
        <b aria-hidden="true">×</b>
      </button>
      <button type="button" class="active-filter-strip__clear" @click="resetFilters">清除全部</button>
    </section>

    <AAlert v-if="error" theme="error" :close="false" class="page-alert">
      <template #message>
        <div class="recoverable-alert">
          <div>
            <strong>数据加载失败</strong>
            <span>{{ error }}</span>
          </div>
          <AButton size="small" variant="outline" :loading="loading" @click="loadAll">重新加载</AButton>
        </div>
      </template>
    </AAlert>

    <StatePanel
      v-if="loading && records.length === 0"
      state="loading"
      title="正在加载项目台账"
      description="系统正在整理项目主数据、资料和结算基础信息。"
    />

    <StatePanel
      v-else-if="!loading && records.length === 0 && !showProjectEmptyOnboarding"
      state="empty"
      title="未找到符合条件的项目"
      description="请调整筛选条件，或清除筛选后重新查看项目台账。"
    >
      <template #actions>
        <AButton variant="outline" @click="resetFilters">清除筛选</AButton>
        <AButton v-if="authStore.isEditor" theme="primary" @click="openProjectForm()">手工创建项目</AButton>
      </template>
    </StatePanel>

    <section v-else class="workspace">
      <div v-if="activeWorkspaceView === 'work'" class="workspace-panel work-queue">
        <div class="surface-heading">
          <div><strong>需要我处理</strong><span>按风险和到期时间排序，直接进入原项目详情继续处理。</span></div>
          <em>{{ workQueueItems.length }} 项</em>
        </div>
        <button v-for="item in workQueueItems" :key="item.id" type="button" class="work-queue-row" :data-level="item.level" @click="selectProject(item.project)">
          <span class="work-queue-row__level">{{ item.levelLabel }}</span>
          <div><strong>{{ item.title }}</strong><span>{{ item.project.projectName }} · {{ item.description }}</span></div>
          <span>{{ item.project.managerName || '未分配负责人' }}</span>
          <time>{{ item.dueText }}</time>
          <em>{{ item.actionLabel }}</em>
        </button>
      </div>

      <div v-else-if="activeWorkspaceView === 'lifecycle'" class="workspace-panel lifecycle-board-wrap">
        <div class="surface-heading">
          <div><strong>项目生命周期</strong><span>按业务阶段分组，点击项目继续使用原详情弹窗。</span></div>
          <em>{{ displayRecords.length }} 个项目</em>
        </div>
        <div class="lifecycle-board">
          <section v-for="column in lifecycleColumns" :key="column.key" class="lifecycle-column">
            <header><span :data-tone="column.tone" /><strong>{{ column.label }}</strong><em>{{ column.records.length }}</em></header>
            <div class="lifecycle-column__body">
              <button v-for="project in column.records" :key="project.id" type="button" class="lifecycle-card" @click="selectProject(project)">
                <strong>{{ project.projectName }}</strong>
                <span>{{ projectStatusLabel(project.projectStatus) }} · {{ project.managerName || '未分配负责人' }}</span>
                <div><em :class="{ warning: project.missingRequiredCount > 0 }">{{ project.missingRequiredCount > 0 ? `缺 ${project.missingRequiredCount} 类资料` : '资料齐全' }}</em><time>{{ shortDate(project.plannedEndDate) }}</time></div>
                <p>{{ nextActionForProject(project).label }}</p>
              </button>
              <span v-if="column.records.length === 0" class="lifecycle-column__empty">暂无项目</span>
            </div>
          </section>
        </div>
      </div>

      <div v-else-if="activeWorkspaceView === 'exceptions'" class="workspace-panel exception-workspace">
        <div class="surface-heading">
          <div><strong>异常项目</strong><span>只保留异常原因、责任人和下一步动作。</span></div>
          <em>{{ displayRecords.length }} 个项目</em>
        </div>
        <div class="exception-grid">
          <button v-for="project in displayRecords" :key="project.id" type="button" class="exception-card" @click="selectProject(project)">
            <div><ATag variant="light" theme="danger">{{ exceptionReason(project) }}</ATag><span>{{ projectStatusLabel(project.projectStatus) }}</span></div>
            <strong>{{ project.projectName }}</strong>
            <p>{{ exceptionDescription(project) }}</p>
            <footer><span>{{ project.managerName || '未分配负责人' }}</span><em>{{ nextActionForProject(project).label }}</em></footer>
          </button>
        </div>
      </div>

      <div v-else class="ledger-panel">
        <div class="panel-head">
          <div>
            <h3>{{ activeWorkspaceViewMeta.tableTitle }}</h3>
            <p>{{ activeWorkspaceViewMeta.tableHint }}</p>
          </div>
          <div class="panel-head__side">
            <div v-if="activeWorkspaceView === 'ledger'" class="ledger-layout-switch" role="group" aria-label="项目台账排版方式">
              <button type="button" :class="{ active: ledgerLayout === 'info' }" @click="ledgerLayout = 'info'">信息表</button>
              <button type="button" :class="{ active: ledgerLayout === 'compact' }" @click="ledgerLayout = 'compact'">紧凑表</button>
              <button type="button" :class="{ active: ledgerLayout === 'cards' }" @click="ledgerLayout = 'cards'">项目卡片</button>
            </div>
            <div class="panel-head__meta">
              <span>当前显示 {{ displayRecords.length }} 条 / 共 {{ total }} 条</span>
              <span>第 {{ page }} / {{ totalPages }} 页</span>
            </div>
          </div>
        </div>

        <div v-if="activeWorkspaceView !== 'ledger'" class="list-utility-bar">
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
            <AButton size="small" variant="outline" :disabled="displayRecords.length === 0" @click="selectCurrentPage">选择当前页</AButton>
            <AButton size="small" variant="outline" :disabled="selectedRecords.length === 0" @click="batchMarkFocus">标记关注</AButton>
            <AButton
              v-if="authStore.isEditor"
              size="small"
              theme="primary"
              variant="outline"
              :loading="batchAuditing"
              :disabled="selectedRecords.length === 0"
              @click="batchStartAudit"
            >
              批量发起审计
            </AButton>
            <AButton size="small" variant="text" :disabled="selectedRecords.length === 0" @click="clearProjectSelection">清空选择</AButton>
            <AButton size="small" variant="outline" @click="saveCurrentFilterView">保存筛选</AButton>
            <ASelect v-model="groupBy" :options="projectGroupOptions" size="small" style="width: 138px" />
            <AButton size="small" variant="outline" @click="columnSettingsVisible = !columnSettingsVisible">列显示</AButton>
          </div>
        </div>

        <div v-if="columnSettingsVisible && activeWorkspaceView !== 'ledger'" class="column-settings-panel">
          <ACheckbox
            v-for="column in configurableColumns"
            :key="column.colKey"
            :model-value="visibleProjectColumnKeys.includes(String(column.colKey))"
            @change="toggleProjectColumn(String(column.colKey))"
          >
            {{ column.title }}
          </ACheckbox>
        </div>

        <StatePanel
          v-if="displayRecords.length === 0"
          class="view-empty-state"
          state="empty"
          title="当前筛选下暂无项目"
          description="可以调整筛选条件，或切换到全部项目查看完整台账。"
        />

        <div v-else-if="activeWorkspaceView === 'ledger' && ledgerLayout === 'cards'" class="project-card-groups">
          <section v-for="group in groupedDisplayRecords" :key="group.key" class="project-card-group">
            <header v-if="groupBy !== 'none'" class="project-table-group__head">
              <div><strong>{{ group.label }}</strong><span>{{ group.hint }}</span></div>
              <em>{{ group.records.length }} 项</em>
            </header>
            <div class="ledger-card-grid">
              <button v-for="project in group.records" :key="project.id" type="button" class="ledger-project-card" @click="selectProject(project)">
                <header>
                  <div><span>{{ project.projectCode }}</span><strong>{{ project.projectName }}</strong></div>
                  <ATag variant="light" :theme="statusTheme(project.projectStatus)">{{ projectStatusLabel(project.projectStatus) }}</ATag>
                </header>
                <dl>
                  <div><dt>施工单位</dt><dd>{{ project.constructionUnit || '未填写' }}</dd></div>
                  <div><dt>项目经理</dt><dd>{{ project.managerName || '未分配' }}</dd></div>
                  <div><dt>当前进度</dt><dd>{{ projectStatusLabel(project.projectStatus) }}</dd></div>
                  <div><dt>资料状态</dt><dd :class="{ warning: project.missingRequiredCount > 0 }">{{ project.missingRequiredCount > 0 ? `缺 ${project.missingRequiredCount} 类（${project.documentCompletion}%）` : `资料完整（${project.documentCompletion}%）` }}</dd></div>
                </dl>
                <div class="ledger-project-card__amount">
                  <span>合同金额</span>
                  <MoneyDisplay :value="project.contractAmount || project.submittedAmount || 0" mode="compact" />
                </div>
                <footer>
                  <span :class="{ paid: hasPayment(project) }">{{ hasPayment(project) ? `已付款 ${formatWan(project.paidAmount)}` : '未付款' }}</span>
                  <em>查看详情</em>
                </footer>
              </button>
            </div>
          </section>
        </div>

        <div v-else class="project-table-groups" :class="{ 'project-table-groups--plain': groupBy === 'none', 'project-table-groups--compact': activeWorkspaceView === 'ledger' && ledgerLayout === 'compact' }">
          <section v-for="group in groupedDisplayRecords" :key="group.key" class="project-table-group">
            <header v-if="groupBy !== 'none'" class="project-table-group__head">
              <div>
                <strong>{{ group.label }}</strong>
                <span>{{ group.hint }}</span>
              </div>
              <em>{{ group.records.length }} 项</em>
            </header>
            <ATable
              :data="group.records"
              :columns="tableColumns"
              :loading="loading"
              :table-layout="'fixed'"
              :horizontal-scroll-affixed-bottom="true"
              bordered
              hover
              @row-contextmenu="openProjectContextMenu"
            >
              <template #select="{ row }">
                <ACheckbox
                  :model-value="selectedProjectIds.includes(row.id)"
                  aria-label="选择项目"
                  @change="toggleProjectSelection(row.id)"
                />
              </template>
              <template #project="{ row }">
                <button class="project-link" type="button" @click="selectProject(row)">
                  <strong>{{ row.projectName }}</strong>
                  <span>{{ ledgerLayout === 'compact' && activeWorkspaceView === 'ledger' ? `${row.projectCode} · ${row.constructionUnit || row.ownerUnit || '未填写施工单位'}` : row.projectCode }}</span>
                </button>
              </template>
              <template #constructionUnit="{ row }">
                <div class="construction-unit-cell">
                  <strong>{{ row.constructionUnit || '未填写' }}</strong>
                  <span>{{ row.ownerUnit ? `建设单位：${row.ownerUnit}` : '建设单位未填写' }}</span>
                </div>
              </template>
              <template #stage="{ row }">
                <div class="status-stack">
                  <ATag variant="light" :theme="statusTheme(row.projectStatus)">{{ projectStatusLabel(row.projectStatus) }}</ATag>
                  <span>{{ shortDate(row.plannedEndDate) }} 前</span>
                </div>
              </template>
              <template #owner="{ row }">
                <div class="owner-table-cell">
                  <span>{{ ownerInitial(row) }}</span>
                  <div><strong>{{ row.managerName || '未分配' }}</strong><em>{{ row.companyRole || '项目负责人' }}</em></div>
                </div>
              </template>
              <template #status="{ row }">
                <div class="status-stack">
                  <ATag variant="light" :theme="statusTheme(row.projectStatus)">{{ projectStatusLabel(row.projectStatus) }}</ATag>
                  <ATag variant="light" :theme="settlementTheme(row.settlementStatus)">{{ settlementStatusLabel(row.settlementStatus) }}</ATag>
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
                  <MoneyDisplay :value="row.contractAmount || row.submittedAmount || 0" mode="compact" />
                  <span v-if="activeWorkspaceView === 'ledger' && ledgerLayout === 'compact'" class="amount-payment-hint">{{ hasPayment(row) ? `已付款 · ${paymentRatio(row)}%` : '未付款' }}</span>
                </div>
              </template>
              <template #payment="{ row }">
                <div class="payment-cell">
                  <ATag variant="light" :theme="hasPayment(row) ? 'success' : 'default'">{{ hasPayment(row) ? '已有付款' : '尚未付款' }}</ATag>
                  <strong v-if="hasPayment(row)">{{ formatWan(row.paidAmount) }}</strong>
                  <span>{{ hasPayment(row) ? `合同付款比例 ${paymentRatio(row)}%` : '暂无付款记录' }}</span>
                </div>
              </template>
              <template #auditStage="{ row }">
                <div class="audit-cell">
                  <strong>{{ auditStageLabel(row.auditStage) }}</strong>
                  <span>{{ row.auditProjectId ? '已进入审计流程' : '尚未发起审计' }}</span>
                </div>
              </template>
              <template #settlement="{ row }">
                <div class="status-stack">
                  <ATag variant="light" :theme="settlementTheme(row.settlementStatus)">{{ settlementStatusLabel(row.settlementStatus) }}</ATag>
                  <span>已付 {{ paymentRatio(row) }}%</span>
                </div>
              </template>
              <template #next="{ row }">
                <div class="next-action-cell">
                  <strong>{{ nextActionForProject(row).label }}</strong>
                  <span>{{ nextActionForProject(row).hint }}</span>
                </div>
              </template>
              <template #updated="{ row }">
                <div class="updated-cell">
                  <strong>{{ shortDate(row.updatedAt) }}</strong>
                  <span>{{ isProjectOverdue(row) ? '计划已逾期' : '最近更新' }}</span>
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
                  <button v-if="authStore.isEditor" type="button" @click="openProjectForm(row)">编辑</button>
                  <button v-if="canDelete" type="button" @click="confirmDeleteProject(row)">删除</button>
                </div>
              </template>
            </ATable>
          </section>
        </div>

        <div v-if="displayRecords.length > 0" class="pager">
          <span>当前显示 {{ displayRecords.length }} 条 / 共 {{ total }} 条，第 {{ page }} 页</span>
          <ASelect v-model="filters.pageSize" :options="pageSizeOptions" style="width: 120px" @change="loadRecords" />
          <AButton variant="outline" :disabled="page <= 1" @click="changePage(page - 1)">上一页</AButton>
          <AButton variant="outline" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</AButton>
        </div>
      </div>

      <AModal
        v-model:visible="detailDialogVisible"
        header="项目详情"
        :confirm-btn="null"
        width="1120px"
        modal-class="project-detail-modal"
        destroy-on-close
      >
      <section class="detail-panel detail-panel--dialog" aria-label="项目详情">
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
            <ProjectLifecycleStatus
              ref="lifecycleStatusRef"
              :project-id="currentProject.id"
              :can-advance="authStore.isEditor"
              @advance="openLifecycleTransition"
            />
            <div class="detail-head__actions">
              <AButton v-if="authStore.isEditor" size="small" variant="outline" @click="openProjectForm(currentProject)">编辑</AButton>
              <AButton
                v-if="currentProject.auditProjectId"
                size="small"
                variant="outline"
                @click="goAudit(currentProject.auditProjectId)"
              >
                查看审计进度
              </AButton>
              <AButton
                v-else-if="authStore.isEditor"
                size="small"
                variant="outline"
                :loading="auditStarting"
                @click="startAudit(currentProject)"
              >
                发起审计
              </AButton>
              <AButton v-if="authStore.isEditor" size="small" theme="primary" @click="openFileDialog()">上传资料</AButton>
            </div>
          </div>

          <div v-if="filePreview.visible" class="inline-preview-shell" aria-label="资料预览">
            <div class="inline-preview-shell__head">
              <div>
                <span class="mini-label">资料预览</span>
                <strong>{{ repairedFileName(filePreview.name) }}</strong>
              </div>
              <button type="button" class="icon-text-button" @click="closeFilePreview">关闭预览</button>
            </div>
            <div class="inline-preview-frame">
              <img v-if="filePreview.kind === 'image'" :src="filePreview.url" :alt="filePreview.name" />
              <iframe v-else-if="filePreview.kind === 'frame'" :src="filePreview.url" :title="filePreview.name" />
              <pre v-else-if="filePreview.kind === 'text'">{{ filePreview.text }}</pre>
              <div v-else class="preview-unavailable">
                <strong>当前格式暂不支持在线预览</strong>
                <span>可先下载后使用本机应用查看。</span>
              </div>
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
              <MoneyDisplay :value="currentProject.contractAmount || 0" mode="compact" />
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

          <div class="business-flow-panel" aria-label="项目业务闭环">
            <div class="section-head">
              <strong>项目业务闭环</strong>
              <span>基于当前项目真实数据展示，不生成模拟节点</span>
            </div>
            <div class="business-flow-list">
              <button
                v-for="step in projectLifecycleSteps"
                :key="step.key"
                type="button"
                :data-state="step.state"
                @click="handleLifecycleAction(step.key)"
              >
                <i aria-hidden="true" />
                <div>
                  <strong>{{ step.label }}</strong>
                  <span>{{ step.description }}</span>
                </div>
                <em>{{ step.status }}</em>
              </button>
            </div>
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
            <button
              v-for="tab in tabs"
              :id="detailTabId(tab.value)"
              :key="tab.value"
              type="button"
              role="tab"
              :aria-selected="activeTab === tab.value"
              :aria-controls="detailTabPanelId(tab.value)"
              :tabindex="activeTab === tab.value ? 0 : -1"
              :class="{ active: activeTab === tab.value }"
              @click="selectDetailTab(tab.value)"
              @keydown="handleDetailTabKeydown($event, tab.value)"
            >
              {{ tab.label }}
            </button>
          </div>

          <div v-if="activeTab === 'overview'" :id="detailTabPanelId('overview')" class="detail-section" role="tabpanel" :aria-labelledby="detailTabId('overview')" tabindex="0">
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
              <AButton
                v-if="currentProject.auditProjectId || authStore.isEditor"
                :variant="currentProject.auditProjectId ? 'outline' : undefined"
                :theme="currentProject.auditProjectId ? 'default' : 'primary'"
                :loading="auditStarting"
                @click="currentProject.auditProjectId ? goAudit(currentProject.auditProjectId) : startAudit(currentProject)"
              >
                {{ currentProject.auditProjectId ? '查看审计进度' : '发起审计' }}
              </AButton>
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
              <article v-for="category in visibleDocumentCategories" :key="category.categoryKey" class="doc-card">
                <div class="doc-card__head">
                  <div>
                    <strong>{{ category.categoryName }}</strong>
                    <span>{{ category.description }}</span>
                  </div>
                  <div class="doc-card__tools">
                    <ATag variant="light" :theme="categoryIsRequiredNow(category) ? 'primary' : 'default'">{{ categoryRequirementLabel(category) }}</ATag>
                    <ASelect
                      v-if="authStore.isAdmin"
                      class="doc-stage-select"
                      size="small"
                      :model-value="categoryRequiredFromStage(category)"
                      :options="projectStatusOptions"
                      :disabled="categorySavingKey === category.categoryKey"
                      @change="updateCategoryRequiredFromStage(category, $event)"
                    />
                    <button
                      v-if="authStore.isAdmin"
                      type="button"
                      class="doc-required-toggle"
                      :disabled="categorySavingKey === category.categoryKey"
                      @click="toggleCategoryRequired(category)"
                    >
                      {{ category.required ? '设为按需' : '设为必填' }}
                    </button>
                  </div>
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
                      <span>{{ repairedFileName(file.displayName) }}</span>
                      <small>V{{ file.versionNo }}</small>
                    </button>
                    <button
                      v-if="authStore.isEditor && filesByCategory(category.categoryKey).length === 0"
                      type="button"
                      class="inline-empty-action"
                      @click="openFileDialog(category)"
                    >
                      <strong>{{ categoryIsRequiredNow(category) ? '必填资料待补充' : categoryIsAvailableNow(category) ? '暂无归档资料' : '当前阶段暂不要求' }}</strong>
                      <span>点击上传{{ category.categoryName }}</span>
                    </button>
                    <div
                      v-else-if="filesByCategory(category.categoryKey).length === 0"
                      class="inline-empty-action"
                    >
                      <strong>{{ categoryIsRequiredNow(category) ? '必填资料待补充' : categoryIsAvailableNow(category) ? '暂无归档资料' : '当前阶段暂不要求' }}</strong>
                      <span>{{ categoryIsRequiredNow(category) ? '请联系项目维护人员补充资料' : category.description }}</span>
                    </div>
                  </div>
                  <div class="doc-actions">
                    <AButton v-if="authStore.isEditor" size="small" variant="outline" @click="openFileDialog(category)">上传资料</AButton>
                    <span>{{ filesByCategory(category.categoryKey).length ? `${filesByCategory(category.categoryKey).length} 份资料` : categoryIsRequiredNow(category) ? '待补充' : '非当前必填' }}</span>
                  </div>
                </div>
              </article>
            </div>
          </div>

          <div v-else-if="activeTab === 'files'" :id="detailTabPanelId('files')" class="detail-section" role="tabpanel" :aria-labelledby="detailTabId('files')" tabindex="0">
            <div class="section-head">
              <strong>资料列表</strong>
              <div class="detail-head__actions">
                <AButton size="small" variant="outline" :loading="projectArchiveDownloading" @click="downloadProjectArchive()">下载全部资料</AButton>
                <AButton v-if="authStore.isEditor" size="small" theme="primary" @click="openFileDialog()">上传资料</AButton>
              </div>
            </div>
            <ATable :data="currentProject.files || []" :columns="fileColumns" bordered hover>
              <template #name="{ row }">
                <div class="file-cell">
                  <strong>{{ row.displayName }}</strong>
                  <span>{{ repairedFileName(row.originalName) }} · V{{ row.versionNo }}</span>
                </div>
              </template>
              <template #category="{ row }">
                <ATag variant="light">{{ row.categoryName }}</ATag>
              </template>
          <template #size="{ row }">{{ formatSize(row.fileSize) }}</template>
          <template #uploadedAt="{ row }">{{ formatDate(row.uploadedAt) }}</template>
          <template #actions="{ row }">
            <div class="action-cell">
                  <button :disabled="!row.canPreview" type="button" @click="previewFile(row)">预览</button>
                  <button type="button" @click="downloadFile(row)">下载</button>
                  <button v-if="authStore.isEditor" type="button" @click="openRenameDialog(row)">重命名</button>
                  <button v-if="canDelete" type="button" @click="confirmDeleteFile(row)">删除</button>
                </div>
              </template>
            </ATable>
            <div v-if="(currentProject.files || []).length === 0" class="detail-empty-action">
              <strong>当前项目还没有上传资料</strong>
              <span>建议先上传合同、招投标、过程资料或结算资料，后续审计会直接引用这些文件。</span>
              <AButton v-if="authStore.isEditor" size="small" theme="primary" @click="openFileDialog()">上传资料</AButton>
            </div>
          </div>

          <div v-else-if="activeTab === 'settlements'" :id="detailTabPanelId('settlements')" class="detail-section" role="tabpanel" :aria-labelledby="detailTabId('settlements')" tabindex="0">
            <div class="section-head">
              <strong>付款结算</strong>
              <AButton v-if="authStore.isEditor" size="small" theme="primary" @click="openSettlementDialog()">新增结算</AButton>
            </div>
            <ATable :data="currentProject.settlements || []" :columns="settlementColumns" bordered hover>
              <template #name="{ row }">
                <div class="file-cell">
                  <strong>{{ row.settlementName }}</strong>
                  <span>{{ settlementTypeLabel(row.settlementType) }}</span>
                </div>
              </template>
              <template #status="{ row }">
                <ATag variant="light" :theme="settlementTheme(row.settlementStatus)">{{ settlementStatusLabel(row.settlementStatus) }}</ATag>
              </template>
              <template #amount="{ row }"><MoneyDisplay :value="row.approvedAmount || row.applyAmount || 0" mode="compact" /></template>
              <template #actions="{ row }">
                <div class="action-cell">
                  <button v-if="authStore.isEditor" type="button" @click="openSettlementDialog(row)">编辑</button>
                </div>
              </template>
            </ATable>
            <div v-if="(currentProject.settlements || []).length === 0" class="detail-empty-action">
              <strong>尚未维护付款结算记录</strong>
              <span>补充结算记录后，可以在项目台账中同步查看付款进度和结算状态。</span>
              <AButton v-if="authStore.isEditor" size="small" theme="primary" @click="openSettlementDialog()">新增结算</AButton>
            </div>
          </div>

          <div v-else-if="activeTab === 'variations'" :id="detailTabPanelId('variations')" class="detail-section" role="tabpanel" :aria-labelledby="detailTabId('variations')" tabindex="0">
            <div class="section-head">
              <strong>变更签证</strong>
              <AButton v-if="authStore.isEditor" size="small" theme="primary" @click="openVariationDialog()">新增签证</AButton>
            </div>
            <ATable :data="currentProject.variations || []" :columns="variationColumns" bordered hover>
              <template #name="{ row }">
                <div class="file-cell">
                  <strong>{{ row.variationName }}</strong>
                  <span>{{ variationTypeLabel(row.variationType) }}</span>
                </div>
              </template>
              <template #status="{ row }">
                <ATag variant="light" :theme="statusTheme(row.variationStatus)">{{ variationStatusLabel(row.variationStatus) }}</ATag>
              </template>
              <template #amount="{ row }"><MoneyDisplay :value="row.amount || 0" mode="compact" /></template>
              <template #actions="{ row }">
                <div class="action-cell">
                  <button v-if="authStore.isEditor" type="button" @click="openVariationDialog(row)">编辑</button>
                </div>
              </template>
            </ATable>
            <div v-if="(currentProject.variations || []).length === 0" class="detail-empty-action">
              <strong>暂无变更签证记录</strong>
              <span>如项目发生工程量、范围或金额调整，可在这里记录变更签证。</span>
              <AButton v-if="authStore.isEditor" size="small" theme="primary" @click="openVariationDialog()">新增签证</AButton>
            </div>
          </div>

          <div v-else :id="detailTabPanelId('logs')" class="detail-section" role="tabpanel" :aria-labelledby="detailTabId('logs')" tabindex="0">
            <div class="section-head">
              <strong>操作记录</strong>
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
      </AModal>

      <ProjectStageTransitionModal
        v-model:visible="lifecycleTransitionVisible"
        :project-id="currentProject?.id || ''"
        :snapshot="lifecycleTransitionSnapshot"
        @transitioned="handleLifecycleTransitioned"
        @refresh="refreshLifecycleDetail"
      />
    </section>

    <AModal
      :visible="projectDialog.visible"
      :mask-closable="false"
      :esc-to-close="false"
      :width="projectDialog.mode === 'create' ? 'min(1480px, calc(100vw - 48px))' : 920"
      unmount-on-close
      modal-class="project-form-modal"
      @confirm="projectDialog.mode === 'create' ? handleProjectWizardConfirm() : saveProject()"
      @cancel="requestCloseProjectDialog"
    >
      <template #title>
        <div class="project-form-modal__titlebar">
          <strong>{{ projectDialog.mode === 'create' ? '新建项目向导' : '编辑项目' }}</strong>
          <div class="project-form-modal__title-actions">
            <AButton
              v-if="projectDialog.mode === 'create'"
              size="small"
              variant="outline"
              :disabled="projectDialog.saving"
              @click="saveManualProjectDraft"
            >
              保存草稿
            </AButton>
            <AButton size="small" variant="outline" :disabled="projectDialog.saving" @click="requestCloseProjectDialog">取消</AButton>
            <AButton
              size="small"
              theme="primary"
              :loading="projectDialog.saving"
              @click="projectDialog.mode === 'create' ? handleProjectWizardConfirm() : saveProject()"
            >
              {{ projectDialog.mode === 'create' ? projectWizardConfirmText : '保存修改' }}
            </AButton>
          </div>
        </div>
      </template>

      <div
        v-if="projectDialog.mode === 'create'"
        class="project-create-shell"
        :class="{ 'project-create-shell--preview-collapsed': manualPdfPreviewCollapsed }"
      >
        <section class="project-create-shell__form">
          <div class="project-create-wizard">
        <nav class="wizard-stepper" aria-label="新建项目步骤">
          <button
            v-for="(step, index) in projectWizardSteps"
            :key="step.key"
            type="button"
            class="wizard-stepper__item"
            :class="{ 'is-active': projectWizardStepIndex === index, 'is-done': projectWizardStepIndex > index }"
            @click="jumpProjectWizardStep(index)"
          >
            <span>{{ index + 1 }}</span>
            <strong>{{ step.title }}</strong>
          </button>
        </nav>

        <AForm ref="projectFormRef" :model="projectForm" layout="vertical" class="arco-project-form">
          <section v-if="projectWizardStepKey === 'base'" class="wizard-panel">
            <div class="wizard-panel__header">
              <span class="mini-label">基础信息</span>
              <h3>先建立项目主档案</h3>
              <p>项目编号由系统按合同日期、施工单位核心字号和序号生成。施工单位可搜索选择，也可直接输入新单位并沉淀到字典。</p>
            </div>
            <div class="dialog-grid">
              <AFormItem
                field="projectCode"
                label="项目编号"
                help="保存时由系统生成，不允许人工填写。"
              >
                <AInput :model-value="projectCodePreview" readonly placeholder="填写合同日期和施工单位后自动预览" />
              </AFormItem>
              <AFormItem
                field="contractDate"
                label="工程合同签订日期"
                required
                :validate-status="projectFormErrors.contractDate ? 'error' : undefined"
                :help="projectFormErrors.contractDate"
              >
                <ADatePicker v-model="projectForm.contractDate" data-project-field="contractDate" allow-clear placeholder="请选择合同签订日期" @change="clearProjectFieldError('contractDate')" />
              </AFormItem>
              <AFormItem
                field="projectName"
                label="项目名称"
                required
                :validate-status="projectFormErrors.projectName ? 'error' : undefined"
                :help="projectFormErrors.projectName"
              >
                <AInput v-model="projectForm.projectName" data-project-field="projectName" placeholder="请输入项目名称" allow-clear @input="clearProjectFieldError('projectName')" />
              </AFormItem>
              <AFormItem
                field="constructionUnit"
                label="施工单位"
                required
                :validate-status="projectFormErrors.constructionUnit ? 'error' : undefined"
                :help="projectFormErrors.constructionUnit || '如江苏XX建设工程有限公司，编号会优先取核心字号 XX。'"
              >
                <ASelect
                  v-model="projectForm.constructionUnit"
                  data-project-field="constructionUnit"
                  placeholder="搜索或输入施工单位"
                  :options="dictionarySelectOptions('construction_unit')"
                  allow-clear
                  allow-search
                  allow-create
                  @change="handleProjectDictionaryChange('constructionUnit')"
                />
              </AFormItem>
              <AFormItem
                field="ownerUnit"
                label="建设单位"
                required
                :validate-status="projectFormErrors.ownerUnit ? 'error' : undefined"
                :help="projectFormErrors.ownerUnit"
              >
                <ASelect
                  v-model="projectForm.ownerUnit"
                  data-project-field="ownerUnit"
                  placeholder="搜索或输入建设单位"
                  :options="dictionarySelectOptions('owner_unit')"
                  allow-clear
                  allow-search
                  allow-create
                  @change="handleProjectDictionaryChange('ownerUnit')"
                />
              </AFormItem>
              <AFormItem field="contractorName" label="施工联系人/负责人">
                <ASelect
                  v-model="projectForm.contractorName"
                  data-project-field="contractorName"
                  placeholder="搜索或输入负责人姓名"
                  :options="dictionarySelectOptions('contractor_name')"
                  allow-clear
                  allow-search
                  allow-create
                  @change="handleProjectDictionaryChange('contractorName')"
                />
              </AFormItem>
              <AFormItem
                field="contractorContact"
                label="联系电话"
                :validate-status="projectFormErrors.contractorContact ? 'error' : undefined"
                :help="projectFormErrors.contractorContact"
              >
                <AInput v-model="projectForm.contractorContact" data-project-field="contractorContact" placeholder="请输入联系电话" allow-clear @input="clearProjectFieldError('contractorContact')" />
              </AFormItem>
              <AFormItem field="managerName" label="项目负责人">
                <ASelect
                  v-model="projectForm.managerName"
                  data-project-field="managerName"
                  placeholder="搜索或输入项目负责人"
                  :options="dictionarySelectOptions('manager_name')"
                  allow-clear
                  allow-search
                  allow-create
                  @change="handleProjectDictionaryChange('managerName')"
                />
              </AFormItem>
              <AFormItem field="companyRole" label="我方角色">
                <ASelect
                  v-model="projectForm.companyRole"
                  data-project-field="companyRole"
                  placeholder="搜索或输入我方角色"
                  :options="dictionarySelectOptions('company_role')"
                  allow-clear
                  allow-search
                  allow-create
                  @change="handleProjectDictionaryChange('companyRole')"
                />
              </AFormItem>
              <AFormItem field="projectType" label="项目类型">
                <AInput v-model="projectCreationFlow.projectType" placeholder="如：学校维修、道路改造、市政配套" allow-clear />
              </AFormItem>
              <AFormItem field="projectLocation" label="项目地点">
                <AInput v-model="projectCreationFlow.projectLocation" placeholder="请输入项目所在区域或详细地点" allow-clear />
              </AFormItem>
              <AFormItem
                field="contractAmount"
                label="合同金额"
                required
                :validate-status="projectFormErrors.contractAmount ? 'error' : undefined"
                :help="projectFormErrors.contractAmount"
              >
                <AInputNumber v-model="projectForm.contractAmount" :min="0" :precision="2" hide-button @change="clearProjectFieldError('contractAmount')" />
              </AFormItem>
              <AFormItem
                class="dialog-span-2"
                field="paymentTerms"
                label="付款条款"
                required
                :validate-status="projectFormErrors.paymentTerms ? 'error' : undefined"
                :help="projectFormErrors.paymentTerms"
              >
                <ATextarea
                  v-model="projectForm.paymentTerms"
                  data-project-field="paymentTerms"
                  :auto-size="{ minRows: 3, maxRows: 6 }"
                  placeholder="请对照合同逐条填写付款节点，每行一条"
                  allow-clear
                  @input="clearProjectFieldError('paymentTerms')"
                />
              </AFormItem>
              <AFormItem
                field="paidAmount"
                label="已付款金额"
                :validate-status="projectFormErrors.paidAmount ? 'error' : undefined"
                :help="projectFormErrors.paidAmount"
              >
                <AInputNumber v-model="projectForm.paidAmount" :min="0" :precision="2" hide-button @change="clearProjectFieldError('paidAmount')" />
              </AFormItem>
            </div>
          </section>

          <section v-else-if="projectWizardStepKey === 'stage'" class="wizard-panel">
            <div class="wizard-panel__header">
              <span class="mini-label">项目阶段</span>
              <h3>新建项目从已中标开始</h3>
              <p>普通新建项目固定为“已中标”；历史项目请通过专用初始化流程录入。</p>
            </div>
            <div class="dialog-grid wizard-money-grid">
              <AFormItem field="projectStatus" label="初始项目状态">
                <AInput model-value="已中标" readonly />
              </AFormItem>
              <AFormItem field="settlementStatus" label="结算状态">
                <ASelect v-model="projectForm.settlementStatus" :options="settlementStatusOptions" placeholder="请选择结算状态" />
              </AFormItem>
              <AFormItem field="plannedStartDate" label="计划开始日期">
                <ADatePicker v-model="projectForm.plannedStartDate" data-project-field="plannedStartDate" allow-clear placeholder="请选择计划开始日期" @change="clearProjectFieldError('plannedStartDate')" />
              </AFormItem>
              <AFormItem
                field="plannedEndDate"
                label="计划完成日期"
                :validate-status="projectFormErrors.plannedEndDate ? 'error' : undefined"
                :help="projectFormErrors.plannedEndDate"
              >
                <ADatePicker v-model="projectForm.plannedEndDate" data-project-field="plannedEndDate" allow-clear placeholder="请选择计划完成日期" @change="clearProjectFieldError('plannedEndDate')" />
              </AFormItem>
            </div>
          </section>

          <section v-else-if="projectWizardStepKey === 'materials'" class="wizard-panel">
            <div class="wizard-panel__header">
              <span class="mini-label">资料目录</span>
              <h3>系统将初始化项目资料节点</h3>
              <p>创建后无需手动建目录，员工只需进入项目详情按节点上传资料。</p>
            </div>
            <div class="material-directory-grid">
              <article v-for="item in projectInitialDirectories" :key="item.key" class="material-directory-card">
                <span>{{ item.required ? '必填' : '按需' }}</span>
                <strong>{{ item.label }}</strong>
                <em>{{ item.hint }}</em>
              </article>
            </div>
            <AAlert type="info" show-icon>创建完成后，系统会根据当前阶段自动生成待办，例如补充合同资料、上传竣工验收证明、提交一审材料或完善二审资料。</AAlert>
          </section>

          <section v-else class="wizard-panel">
            <div class="wizard-panel__header">
              <span class="mini-label">确认生成</span>
              <h3>请确认项目创建信息</h3>
              <p>确认后系统将创建项目主档案、资料节点和待办事项；审计联动需在项目详情中单独发起。</p>
            </div>
            <div class="wizard-review">
              <article>
                <h4>基础信息</h4>
                <dl>
                  <dt>项目编号</dt><dd>{{ projectCodePreview }}</dd>
                  <dt>项目名称</dt><dd>{{ projectForm.projectName || '未填写' }}</dd>
                  <dt>施工单位</dt><dd>{{ projectForm.constructionUnit || '未填写' }}</dd>
                  <dt>建设单位</dt><dd>{{ projectForm.ownerUnit || '未填写' }}</dd>
                  <dt>合同日期</dt><dd>{{ projectForm.contractDate || '未选择' }}</dd>
                </dl>
              </article>
              <article>
                <h4>业务状态</h4>
                <dl>
                  <dt>项目状态</dt><dd>{{ projectStatusLabel(projectForm.projectStatus) }}</dd>
                  <dt>结算状态</dt><dd>{{ settlementStatusLabel(projectForm.settlementStatus) }}</dd>
                  <dt>合同金额</dt><dd><MoneyDisplay :value="projectForm.contractAmount" mode="full" /></dd>
                  <dt>已付款金额</dt><dd><MoneyDisplay :value="projectForm.paidAmount" mode="full" /></dd>
                </dl>
              </article>
              <article>
                <h4>资料目录</h4>
                <div class="review-tags">
                  <ATag v-for="item in projectInitialDirectories" :key="item.key">{{ item.label }}</ATag>
                </div>
              </article>
            </div>
          </section>
        </AForm>

            <div class="wizard-footer-extra">
              <AButton v-if="projectWizardStepIndex > 0" variant="outline" @click="prevProjectWizardStep">上一步</AButton>
              <span>第 {{ projectWizardStepIndex + 1 }} / {{ projectWizardSteps.length }} 步</span>
            </div>
          </div>
        </section>

        <aside
          class="project-create-shell__preview"
        >
          <ContractPdfPreview
            :document="manualContractDocument"
            :max-file-size-mb="uploadLimitMb"
            :page="manualPdfPage"
            :scale="manualPdfScale"
            :collapsed="manualPdfPreviewCollapsed"
            @uploaded="handleContractPdfUploaded"
            @update:page="handleContractPdfPage"
            @update:scale="handleContractPdfScale"
            @update:collapsed="handleContractPdfCollapsed"
            @uploading="manualPdfUploading = $event"
            @error="MessagePlugin.error($event)"
          />
        </aside>
      </div>

      <AForm v-else ref="projectFormRef" :model="projectForm" layout="vertical" class="arco-project-form">
        <div class="dialog-grid">
          <AFormItem
            field="projectCode"
            label="项目编号"
            help="系统编号不可人工修改。"
          >
            <AInput :model-value="projectCodePreview" readonly placeholder="填写合同日期和施工单位后自动预览" />
          </AFormItem>
          <AFormItem
            field="contractDate"
            label="工程合同签订日期"
            :validate-status="projectFormErrors.contractDate ? 'error' : undefined"
            :help="projectFormErrors.contractDate"
          >
            <ADatePicker v-model="projectForm.contractDate" data-project-field="contractDate" allow-clear placeholder="请选择合同签订日期" @change="clearProjectFieldError('contractDate')" />
          </AFormItem>
          <AFormItem
            v-for="field in projectFieldsLeft"
            :key="field.key"
            :field="field.key"
            :label="field.label"
            :required="field.required"
            :validate-status="projectFormErrors[field.key] ? 'error' : undefined"
            :help="projectFormErrors[field.key]"
          >
            <ASelect
              v-if="projectDictionaryField(field.key)"
              v-model="projectForm[field.key]"
              :data-project-field="field.key"
              :placeholder="field.placeholder"
              :options="dictionarySelectOptions(projectDictionaryField(field.key))"
              allow-clear
              allow-search
              allow-create
              @change="handleProjectDictionaryChange(field.key)"
            />
            <AInput
              v-else
              v-model="projectForm[field.key]"
              :data-project-field="field.key"
              :placeholder="field.placeholder"
              allow-clear
              @input="clearProjectFieldError(field.key)"
            />
          </AFormItem>
          <AFormItem
            v-for="field in projectFieldsRight"
            :key="field.key"
            :field="field.key"
            :label="field.label"
            :required="field.required"
            :validate-status="projectFormErrors[field.key] ? 'error' : undefined"
            :help="projectFormErrors[field.key]"
          >
            <ASelect
              v-if="projectDictionaryField(field.key)"
              v-model="projectForm[field.key]"
              :data-project-field="field.key"
              :placeholder="field.placeholder"
              :options="dictionarySelectOptions(projectDictionaryField(field.key))"
              allow-clear
              allow-search
              allow-create
              @change="handleProjectDictionaryChange(field.key)"
            />
            <AInput
              v-else
              v-model="projectForm[field.key]"
              :data-project-field="field.key"
              :placeholder="field.placeholder"
              allow-clear
              @input="clearProjectFieldError(field.key)"
            />
          </AFormItem>
          <AFormItem field="projectStatus" label="项目状态">
            <AInput :model-value="projectStatusLabel(projectForm.projectStatus)" readonly />
          </AFormItem>
          <AFormItem field="settlementStatus" label="结算状态">
            <ASelect v-model="projectForm.settlementStatus" :options="settlementStatusOptions" />
          </AFormItem>
          <AFormItem
            field="contractAmount"
            label="合同金额"
            :validate-status="projectFormErrors.contractAmount ? 'error' : undefined"
            :help="projectFormErrors.contractAmount"
          >
            <AInputNumber v-model="projectForm.contractAmount" :min="0" :precision="2" hide-button @change="clearProjectFieldError('contractAmount')" />
          </AFormItem>
          <AFormItem
            field="submittedAmount"
            label="送审金额"
            :validate-status="projectFormErrors.submittedAmount ? 'error' : undefined"
            :help="projectFormErrors.submittedAmount"
          >
            <AInputNumber v-model="projectForm.submittedAmount" :min="0" :precision="2" hide-button @change="clearProjectFieldError('submittedAmount')" />
          </AFormItem>
          <AFormItem
            field="paidAmount"
            label="已付款金额"
            :validate-status="projectFormErrors.paidAmount ? 'error' : undefined"
            :help="projectFormErrors.paidAmount"
          >
            <AInputNumber v-model="projectForm.paidAmount" :min="0" :precision="2" hide-button @change="clearProjectFieldError('paidAmount')" />
          </AFormItem>
          <AFormItem field="plannedStartDate" label="计划开始日期">
            <ADatePicker v-model="projectForm.plannedStartDate" data-project-field="plannedStartDate" allow-clear placeholder="请选择计划开始日期" @change="clearProjectFieldError('plannedStartDate')" />
          </AFormItem>
          <AFormItem
            field="plannedEndDate"
            label="计划完成日期"
            :validate-status="projectFormErrors.plannedEndDate ? 'error' : undefined"
            :help="projectFormErrors.plannedEndDate"
          >
            <ADatePicker v-model="projectForm.plannedEndDate" data-project-field="plannedEndDate" allow-clear placeholder="请选择计划完成日期" @change="clearProjectFieldError('plannedEndDate')" />
          </AFormItem>
          <AFormItem v-if="projectDialog.mode === 'edit' && projectForm.auditProjectId" field="auditProjectId" label="审计联动">
            <AInput v-model="projectForm.auditProjectId" readonly placeholder="保存项目后可从详情中发起审计" />
          </AFormItem>
          <AFormItem class="dialog-span-2" field="paymentTerms" label="付款条款">
            <ATextarea v-model="projectForm.paymentTerms" :auto-size="{ minRows: 3, maxRows: 6 }" placeholder="如：按节点完成后支付 80%，结算定案后支付尾款" allow-clear />
          </AFormItem>
          <AFormItem class="dialog-span-2" field="description" label="项目说明">
            <ATextarea v-model="projectForm.description" :auto-size="{ minRows: 3, maxRows: 6 }" placeholder="项目背景、当前资料状态、需要提醒的事项" allow-clear />
          </AFormItem>
        </div>
      </AForm>

    </AModal>

    <AModal
      :visible="filterViewDialog.visible"
      title="保存筛选方案"
      ok-text="保存方案"
      cancel-text="取消"
      :width="480"
      :mask-closable="false"
      @ok="confirmSaveFilterView"
      @cancel="closeFilterViewDialog"
    >
      <AForm :model="filterViewDialog" layout="vertical" class="filter-view-form">
        <AFormItem
          label="方案名称"
          field="filterViewName"
          required
          :validate-status="filterViewDialog.error ? 'error' : undefined"
          :help="filterViewDialog.error || '用于快速回到当前筛选条件，最多保存 8 个方案。'"
        >
          <AInput
            v-model="filterViewDialog.name"
            placeholder="例如：本周待处理项目"
            :max-length="20"
            allow-clear
            show-word-limit
            @input="filterViewDialog.error = ''"
          />
        </AFormItem>
      </AForm>
    </AModal>

    <AModal
      v-model:visible="fileDialog.visible"
      header="上传资料"
      :confirm-btn="{ content: '开始上传', loading: fileDialog.saving }"
      width="620px"
      @confirm="saveFile"
      @cancel="closeFileDialog"
      @close="closeFileDialog"
    >
      <AForm :model="fileDialog" layout="vertical" class="file-upload-form">
        <AFormItem field="categoryKey" label="资料分类">
          <ASelect
            v-model="fileDialog.categoryKey"
            :options="categoryOptions"
            placeholder="请选择资料分类"
          />
        </AFormItem>
        <AFormItem field="displayName" label="资料名称">
          <AInput v-model="fileDialog.displayName" placeholder="请输入便于识别的资料名称" />
        </AFormItem>
        <AFormItem field="file" label="文件">
          <input ref="fileInputRef" type="file" class="native-file" @change="onFilePicked" />
        </AFormItem>
        <div v-if="fileDialog.file" class="upload-preview-card">
          <div class="upload-preview-card__head">
            <div>
              <strong>{{ fileDialog.file.name }}</strong>
              <span>{{ uploadPreviewMeta }}</span>
            </div>
            <button type="button" @click="clearPickedFile">移除</button>
          </div>
          <div class="upload-preview-window">
            <img v-if="uploadPreview.kind === 'image'" :src="uploadPreview.url" :alt="fileDialog.file.name" />
            <iframe v-else-if="uploadPreview.kind === 'frame'" :src="uploadPreview.url" :title="fileDialog.file.name" />
            <pre v-else-if="uploadPreview.kind === 'text'">{{ uploadPreview.text }}</pre>
            <div v-else>
              <strong>{{ uploadPreviewTitle }}</strong>
              <span>点击“开始上传”后系统会保存文件并作为资料版本归档。</span>
            </div>
          </div>
          <div v-if="fileDialog.saving || fileDialog.progress > 0" class="upload-progress" aria-label="上传进度">
            <span :style="{ width: `${fileDialog.progress}%` }" />
            <em>{{ fileDialog.progress }}%</em>
          </div>
        </div>
        <p class="dialog-hint">同一项目、同一分类、同一资料名称再次上传时会自动作为新版本处理。</p>
      </AForm>
    </AModal>

    <AModal
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
    </AModal>

    <AModal
      v-model:visible="settlementDialog.visible"
      :header="settlementDialog.mode === 'create' ? '新增结算' : '编辑结算'"
      :confirm-btn="{ content: '保存结算', loading: settlementDialog.saving }"
      width="700px"
      @confirm="saveSettlement"
    >
      <AForm :model="settlementForm" layout="vertical" class="dialog-grid modal-business-form">
        <AFormItem class="dialog-span-2" field="settlementName" label="结算名称">
          <AInput v-model="settlementForm.settlementName" placeholder="如：一期竣工结算" />
        </AFormItem>
        <AFormItem field="settlementStatus" label="付款状态">
          <ASelect v-model="settlementForm.settlementStatus" :options="settlementStatusOptions" placeholder="请选择付款状态" />
        </AFormItem>
        <AFormItem field="settlementType" label="结算事项">
          <ASelect v-model="settlementForm.settlementType" :options="settlementTypeOptions" placeholder="请选择结算事项" />
        </AFormItem>
        <AFormItem field="applyAmount" label="申报金额">
          <AInputNumber v-model="settlementForm.applyAmount" :min="0" :precision="2" />
        </AFormItem>
        <AFormItem field="approvedAmount" label="核定金额">
          <AInputNumber v-model="settlementForm.approvedAmount" :min="0" :precision="2" />
        </AFormItem>
        <AFormItem field="paidAmount" label="已付款金额">
          <AInputNumber v-model="settlementForm.paidAmount" :min="0" :precision="2" />
        </AFormItem>
        <AFormItem field="applyDate" label="申报日期">
          <AInput v-model="settlementForm.applyDate" placeholder="YYYY-MM-DD" />
        </AFormItem>
        <AFormItem field="expectedPayDate" label="预计付款日期">
          <AInput v-model="settlementForm.expectedPayDate" placeholder="YYYY-MM-DD" />
        </AFormItem>
        <AFormItem field="paidDate" label="实际付款日期">
          <AInput v-model="settlementForm.paidDate" placeholder="YYYY-MM-DD" />
        </AFormItem>
        <AFormItem class="dialog-span-2" field="remark" label="备注">
          <ATextarea v-model="settlementForm.remark" :auto-size="{ minRows: 3, maxRows: 5 }" />
        </AFormItem>
      </AForm>
    </AModal>

    <AModal
      v-model:visible="variationDialog.visible"
      :header="variationDialog.mode === 'create' ? '新增变更签证' : '编辑变更签证'"
      :confirm-btn="{ content: '保存签证', loading: variationDialog.saving }"
      width="700px"
      @confirm="saveVariation"
    >
      <AForm :model="variationForm" layout="vertical" class="dialog-grid modal-business-form">
        <AFormItem class="dialog-span-2" field="variationName" label="签证名称">
          <AInput v-model="variationForm.variationName" placeholder="如：设计变更签证 01" />
        </AFormItem>
        <AFormItem field="variationStatus" label="确认状态">
          <ASelect v-model="variationForm.variationStatus" :options="variationStatusOptions" placeholder="请选择确认状态" />
        </AFormItem>
        <AFormItem field="variationType" label="签证事项">
          <ASelect v-model="variationForm.variationType" :options="variationTypeOptions" placeholder="请选择签证事项" />
        </AFormItem>
        <AFormItem field="amount" label="金额">
          <AInputNumber v-model="variationForm.amount" :min="0" :precision="2" />
        </AFormItem>
        <AFormItem field="occurredDate" label="发生日期">
          <AInput v-model="variationForm.occurredDate" placeholder="YYYY-MM-DD" />
        </AFormItem>
        <AFormItem field="approvedDate" label="确认日期">
          <AInput v-model="variationForm.approvedDate" placeholder="YYYY-MM-DD" />
        </AFormItem>
        <AFormItem class="dialog-span-2" field="remark" label="备注">
          <ATextarea v-model="variationForm.remark" :auto-size="{ minRows: 3, maxRows: 5 }" />
        </AFormItem>
      </AForm>
    </AModal>

    <AModal
      v-model:visible="renameDialog.visible"
      header="重命名资料"
      :confirm-btn="{ content: '保存名称', loading: renameDialog.saving }"
      width="520px"
      @confirm="saveRename"
    >
      <div class="dialog-grid dialog-grid--single">
        <label>
          <span>新的资料名称</span>
          <AInput v-model="renameDialog.displayName" placeholder="请输入新的资料名称" />
        </label>
      </div>
    </AModal>

    <ObjectContextMenu
      v-model:visible="projectContextMenu.visible"
      :x="projectContextMenu.x"
      :y="projectContextMenu.y"
      :items="projectContextMenuItems"
      @select="handleProjectContextAction"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { TableData } from '@arco-design/web-vue'
import PageHeader from '@/components/PageHeader.vue'
import StatePanel from '@/components/StatePanel.vue'
import MoneyDisplay from '@/components/MoneyDisplay.vue'
import ContractPdfPreview from '@/components/project/ContractPdfPreview.vue'
import ProjectLifecycleStatus from '@/components/project/ProjectLifecycleStatus.vue'
import ProjectStageTransitionModal from '@/components/project/ProjectStageTransitionModal.vue'
  import ObjectContextMenu, { type ObjectContextMenuItem } from '@/components/workspace/ObjectContextMenu.vue'
import { MessagePlugin } from '@/ui/message'
import type { AppFormInstance } from '@/ui/arcoAppComponents'
import { amountToChineseUpper, formatWan } from '@/utils/format'
import { friendlyErrorMessage } from '@/utils/errors'
import { buildProjectMutationPayload } from '@/utils/projectMutationPayload'
import {
  buildManualContractValues,
  buildManualProjectValues,
  newManualProjectIntakeKey,
} from '@/utils/manualProjectIntake'
import { settleLifecycleRefresh } from '@/utils/projectLifecycleRefresh'
import {
  createManualDocumentMetadataLoader,
  useManualProjectIntakeDraft,
  type ManualProjectIntakeDraftSnapshot,
} from '@/composables/useManualProjectIntakeDraft'
import {
  auditStartEligibilityMessage,
  formatAuditStartSkippedSummary,
  getAuditStartEligibility,
  partitionAuditStartCandidates,
} from '@/utils/auditEligibility'
import { useAuthStore } from '@/store/auth'
import {
  businessColor,
  businessLabel,
  auditStageOptions as auditStageDict,
  materialStatusOptions as materialStatusDict,
  projectStatusOptions as projectStatusDict,
  settlementStatusOptions as settlementStatusDict,
  variationStatusOptions as variationStatusDict,
} from '@/utils/businessDictionaries'
import type { ProjectDocumentCategory, ProjectFile, ProjectFilters, ProjectMeta, ProjectRecord, ProjectSettlement, ProjectSummary, ProjectVariation, WorkItem } from '@/types'
import type { DocumentVersionMetadata, ProjectIntakeDraft } from '@/types/documentReview'
import type { ProjectLifecycleSnapshot } from '@/types/projectLifecycle'
import {
  confirmManualProjectIntake,
} from '@/api/documentReview'
import {
  createProjectDictionaryOption,
  deleteProjectFile,
  deleteProjectRecord,
  fetchProjectFileDownloadBlob,
  fetchProjectFilesArchiveBlob,
  fetchProjectFilePreviewBlob,
  fetchProjectMeta,
  fetchProjectRecord,
  fetchProjectRecords,
  fetchProjectSummary,
  fetchWorkItems,
  saveProjectSettlement,
  saveProjectVariation,
  startProjectAudit,
  updateProjectDocumentCategory,
  updateProjectRecord,
  updateProjectSettlement,
  updateProjectVariation,
  uploadProjectFile,
  renameProjectFile,
} from '@/api/projects'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
type DetailTab = 'overview' | 'files' | 'settlements' | 'variations' | 'logs'
type BuiltInProjectView = 'all' | 'risk' | 'audit'
type ProjectGroupBy = 'none' | 'status' | 'owner' | 'audit'
type ProjectWorkspaceView = 'work' | 'ledger' | 'lifecycle' | 'documents' | 'audit' | 'settlement' | 'exceptions'
type LedgerLayout = 'info' | 'compact' | 'cards'
type ProjectWizardStepKey = 'base' | 'stage' | 'materials' | 'confirm'
type ProjectLifecycleStepKey = 'base' | 'documents' | 'audit' | 'settlement' | 'archive'
type ProjectLifecycleStep = {
  key: ProjectLifecycleStepKey
  label: string
  status: string
  description: string
  state: 'complete' | 'active' | 'warning' | 'pending'
}
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
const PROJECT_WORKSPACE_STATE_KEY = 'project-management-workspace-state-v1'
const LEDGER_LAYOUT_KEY = 'project-management-ledger-layout-v1'

const baseTableColumns = [
  { colKey: 'select', title: '选择', width: 52, fixed: 'left' as const },
  { colKey: 'project', title: '项目名称 / 编号', width: 250, fixed: 'left' as const },
  { colKey: 'constructionUnit', title: '施工单位', width: 170 },
  { colKey: 'stage', title: '当前阶段', width: 120 },
  { colKey: 'owner', title: '项目经理', width: 110 },
  { colKey: 'docs', title: '资料完整度', width: 110 },
  { colKey: 'amount', title: '合同金额（小写 / 中文大写）', width: 190 },
  { colKey: 'payment', title: '付款情况', width: 130 },
  { colKey: 'auditStage', title: '审计进度', width: 160 },
  { colKey: 'settlement', title: '结算状态', width: 180 },
  { colKey: 'next', title: '下一步动作', width: 210 },
  { colKey: 'updated', title: '最近更新', width: 120 },
  { colKey: 'actions', title: '操作', width: 88, fixed: 'right' as const },
]

const viewColumnKeys: Record<Exclude<ProjectWorkspaceView, 'work' | 'lifecycle' | 'exceptions'>, string[]> = {
  ledger: ['select', 'project', 'constructionUnit', 'owner', 'stage', 'docs', 'amount', 'payment', 'actions'],
  documents: ['select', 'project', 'stage', 'owner', 'docs', 'next', 'actions'],
  audit: ['select', 'project', 'stage', 'auditStage', 'owner', 'docs', 'next', 'actions'],
  settlement: ['select', 'project', 'stage', 'owner', 'amount', 'settlement', 'next', 'actions'],
}

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

const settlementTypeOptions = [
  { label: '进度款结算', value: 'progress' },
  { label: '竣工结算', value: 'final' },
  { label: '补充结算', value: 'supplement' },
  { label: '其他结算', value: 'other' },
]

const variationStatusOptions = variationStatusDict.map(({ label, value }) => ({ label, value }))

const variationTypeOptions = [
  { label: '设计变更', value: 'change' },
  { label: '现场签证', value: 'visa' },
  { label: '工程量调整', value: 'quantity_adjustment' },
  { label: '价格调整', value: 'price_adjustment' },
  { label: '其他事项', value: 'other' },
]

const projectGroupOptions = [
  { label: '不分组', value: 'none' },
  { label: '按项目状态', value: 'status' },
  { label: '按负责人', value: 'owner' },
  { label: '按审计联动', value: 'audit' },
]

const defaultProjectStatuses = projectStatusDict.map(({ label, value }) => ({ label, value }))

const defaultSettlementStatuses = settlementStatusDict.map(({ label, value }) => ({ label, value }))

const tabs: Array<{ label: string; value: DetailTab }> = [
  { label: '概览', value: 'overview' },
  { label: '资料', value: 'files' },
  { label: '结算', value: 'settlements' },
  { label: '签证', value: 'variations' },
  { label: '日志', value: 'logs' },
]

function detailTabId(tab: DetailTab) {
  return `project-detail-tab-${tab}`
}

function detailTabPanelId(tab: DetailTab) {
  return `project-detail-panel-${tab}`
}

function selectDetailTab(tab: DetailTab, focusTab = false) {
  activeTab.value = tab
  if (!focusTab) return
  nextTick(() => document.getElementById(detailTabId(tab))?.focus())
}

function handleLifecycleAction(key: ProjectLifecycleStepKey) {
  const project = currentProject.value
  if (!project) return
  if (key === 'documents') {
    selectDetailTab('files', true)
    return
  }
  if (key === 'audit') {
    if (project.auditProjectId) goAudit(project.auditProjectId)
    else startAudit(project)
    return
  }
  if (key === 'settlement') {
    selectDetailTab('settlements', true)
    return
  }
  if (key === 'archive') {
    selectDetailTab('logs', true)
    return
  }
  selectDetailTab('overview', true)
}

function handleDetailTabKeydown(event: KeyboardEvent, tab: DetailTab) {
  const currentIndex = tabs.findIndex((item) => item.value === tab)
  if (currentIndex < 0) return
  let nextIndex = currentIndex
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') nextIndex = (currentIndex + 1) % tabs.length
  else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') nextIndex = (currentIndex - 1 + tabs.length) % tabs.length
  else if (event.key === 'Home') nextIndex = 0
  else if (event.key === 'End') nextIndex = tabs.length - 1
  else return
  event.preventDefault()
  selectDetailTab(tabs[nextIndex].value, true)
}

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
  dictionaryOptions: {},
  auditStages: [],
  uploadSettings: { maxFileSizeMb: 100 },
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
const detailDialogVisible = ref(false)
const lifecycleStatusRef = ref<InstanceType<typeof ProjectLifecycleStatus> | null>(null)
const lifecycleTransitionVisible = ref(false)
const lifecycleTransitionSnapshot = ref<ProjectLifecycleSnapshot | null>(null)
const auditStarting = ref(false)
const batchAuditing = ref(false)
const projectArchiveDownloading = ref(false)
const error = ref('')
const columnSettingsVisible = ref(false)
const advancedFiltersVisible = ref(false)
const selectedProjectIds = ref<string[]>([])
const activeSavedView = ref<BuiltInProjectView>('all')
const activeCustomFilterId = ref('')
const savedFilterViews = ref<SavedProjectFilterView[]>([])
const groupBy = ref<ProjectGroupBy>('none')
const ledgerLayout = ref<LedgerLayout>('info')
const visibleProjectColumnKeys = ref(baseTableColumns.map((column) => String(column.colKey)))
const workItems = ref<WorkItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const activeTab = ref<DetailTab>('overview')
const activeSummaryKey = ref('')
const canDelete = computed(() => authStore.isAdmin)
const categorySavingKey = ref('')

function requireEditorAccess(action: string) {
  if (authStore.isEditor) return true
  MessagePlugin.warning(`当前账号无${action}权限`)
  return false
}

function requireAdminAccess(action: string) {
  if (authStore.isAdmin) return true
  MessagePlugin.warning(`仅管理员可${action}`)
  return false
}

const projectDialog = reactive({ visible: false, mode: 'create' as 'create' | 'edit', saving: false, initialSnapshot: '' })
const filterViewDialog = reactive({ visible: false, name: '', error: '' })
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
  progress: 0,
  projectId: '',
  categoryKey: '',
  displayName: '',
  file: null as File | null,
})
const uploadPreview = reactive({
  kind: 'none' as 'none' | 'image' | 'frame' | 'text',
  url: '',
  text: '',
})
const filePreview = reactive({
  visible: false,
  loading: false,
  kind: 'none' as 'none' | 'image' | 'frame' | 'text',
  url: '',
  text: '',
  name: '',
})
const settlementDialog = reactive({ visible: false, mode: 'create' as 'create' | 'edit', saving: false, id: '' })
const variationDialog = reactive({ visible: false, mode: 'create' as 'create' | 'edit', saving: false, id: '' })
const renameDialog = reactive({ visible: false, saving: false, id: '', displayName: '' })
const projectContextMenu = reactive({
  visible: false,
  x: 0,
  y: 0,
  record: null as ProjectRecord | null,
})
const fileInputRef = ref<HTMLInputElement | null>(null)
const projectFormRef = ref<AppFormInstance | null>(null)
const projectWizardStepIndex = ref(0)

const projectForm = reactive({
  id: '',
  projectCode: '',
  projectName: '',
  contractDate: '',
  constructionUnit: '',
  contractorName: '',
  contractorContact: '',
  ownerUnit: '',
  companyRole: '工程咨询',
  managerName: '',
  projectStatus: 'awarded',
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
type ProjectTextFormKey = 'projectName' | 'constructionUnit' | 'ownerUnit' | 'contractorName' | 'contractorContact' | 'managerName' | 'companyRole'
type ProjectDictionaryGroup = 'construction_unit' | 'owner_unit' | 'contractor_name' | 'manager_name' | 'company_role'
type ProjectFormErrors = Partial<Record<ProjectFormKey, string>>
const projectFormErrors = reactive<ProjectFormErrors>({})

const projectCreationFlow = reactive({
  projectType: '',
  projectLocation: '',
})

type ManualContractDocumentRef = {
  documentId: string
  versionId: string
  name: string
  mimeType: string
  fileSize: number
}

const manualContractDocument = ref<ManualContractDocumentRef | null>(null)
const manualPdfPage = ref(1)
const manualPdfScale = ref(1)
const manualPdfPreviewCollapsed = ref(false)
const manualPdfUploading = ref(false)
const manualProjectIdempotencyKey = ref('')
const restoringManualDraft = ref(false)
const manualDocumentMetadataLoader = createManualDocumentMetadataLoader()
let manualIntakeRouteGeneration = 0

function beginManualIntakeRoute(versionId: string) {
  const token = ++manualIntakeRouteGeneration
  return {
    isCurrent: () => (
      token === manualIntakeRouteGeneration
      && String(route.query.intakeDocumentVersionId || '').trim() === versionId
      && projectDialog.visible
      && projectDialog.mode === 'create'
    ),
  }
}

const {
  drafts: manualDrafts,
  activeDraft,
  loadDrafts,
  resumeDraft,
  scheduleSave,
  flushSave,
  attachDocument,
  completeAndReset,
} = useManualProjectIntakeDraft({
  snapshot: manualProjectDraftSnapshot,
  restore: restoreManualProjectDraftSnapshot,
  onError: (message) => MessagePlugin.error(message),
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

const projectFieldsLeft: Array<{ key: ProjectTextFormKey; label: string; placeholder: string; required: boolean }> = [
  { key: 'projectName', label: '项目名称', placeholder: '请输入项目名称', required: true },
  { key: 'constructionUnit', label: '施工单位', placeholder: '搜索或输入施工单位', required: true },
  { key: 'ownerUnit', label: '建设单位', placeholder: '搜索或输入建设单位', required: false },
]

const projectFieldsRight: Array<{ key: ProjectTextFormKey; label: string; placeholder: string; required: boolean }> = [
  { key: 'contractorName', label: '施工联系人/负责人', placeholder: '搜索或输入负责人姓名', required: false },
  { key: 'contractorContact', label: '联系电话', placeholder: '请输入联系电话', required: false },
  { key: 'managerName', label: '项目负责人', placeholder: '搜索或输入项目负责人', required: false },
  { key: 'companyRole', label: '我方角色', placeholder: '搜索或输入我方角色', required: false },
]

const categoryOptions = computed(() => meta.categories.map((item) => ({ label: item.categoryName, value: item.categoryKey })))
const uploadPreviewMeta = computed(() => fileDialog.file ? `${formatSize(fileDialog.file.size)} · ${fileDialog.file.type || fileExtension(fileDialog.file.name) || '未知格式'}` : '')
const uploadPreviewTitle = computed(() => {
  if (!fileDialog.file) return ''
  const ext = fileExtension(fileDialog.file.name)
  if (['.doc', '.docx'].includes(ext)) return 'Word 文档已选择'
  if (['.xls', '.xlsx', '.csv'].includes(ext)) return 'Excel 表格已选择'
  return '文件已选择'
})
const projectStatusOptions = computed(() => meta.projectStatuses.length ? meta.projectStatuses : defaultProjectStatuses)
const documentStageDefaults: Record<string, string> = {
  contract: 'contract_signed',
  drawing: 'under_construction',
  settlement_book: 'pending_submission',
  visa_change: 'pending_submission',
  first_audit: 'first_audit',
  second_audit: 'second_audit',
  payment: 'conclusion',
  other: 'archived',
}
const lifecycleStageRank = new Map(defaultProjectStatuses.map((item, index) => [item.value, index]))
const visibleDocumentCategories = computed(() => meta.categories.filter((category) => (
  authStore.isAdmin
  || filesByCategory(category.categoryKey).length > 0
  || categoryIsAvailableNow(category)
)))
const settlementStatusOptions = computed(() => meta.settlementStatuses.length ? meta.settlementStatuses : defaultSettlementStatuses)
const projectCodePreview = computed(() => projectForm.projectCode || buildProjectCodePreview(projectForm.contractDate, projectForm.constructionUnit))
const projectWizardSteps = computed(() => {
  const steps: Array<{ key: ProjectWizardStepKey; title: string }> = [
    { key: 'base', title: '基础信息' },
    { key: 'stage', title: '项目阶段' },
  ]
  steps.push({ key: 'materials', title: '资料目录' }, { key: 'confirm', title: '确认生成' })
  return steps
})
const projectWizardStepKey = computed<ProjectWizardStepKey>(() => projectWizardSteps.value[projectWizardStepIndex.value]?.key || 'base')
const projectWizardConfirmText = computed(() => projectWizardStepIndex.value >= projectWizardSteps.value.length - 1 ? '生成项目' : '下一步')
const projectInitialDirectories = computed(() => {
  const base = [
    { key: 'bid_notice', label: '中标通知书', required: ['awarded', 'contract_signed', 'under_construction', 'completed_acceptance', 'pending_submission', 'first_audit', 'second_audit', 'conclusion', 'archived'].includes(projectForm.projectStatus), hint: '用于确认项目来源与中标事实' },
    { key: 'contract_file', label: '合同文件', required: ['contract_signed', 'under_construction', 'completed_acceptance', 'pending_submission', 'first_audit', 'second_audit', 'conclusion', 'archived'].includes(projectForm.projectStatus), hint: '合同、补充协议、合同清单等' },
    { key: 'completion_acceptance', label: '竣工验收证明', required: ['completed_acceptance', 'pending_submission', 'first_audit', 'second_audit', 'conclusion', 'archived'].includes(projectForm.projectStatus), hint: '进入结算和审计前的重要节点资料' },
    { key: 'settlement_book', label: '竣工结算书', required: ['pending_submission', 'first_audit', 'second_audit', 'conclusion', 'archived'].includes(projectForm.projectStatus), hint: '用于报审、核价和后续定案' },
    { key: 'variation', label: '变更签证', required: false, hint: '涉及变更、签证、洽商时按需补充' },
  ]
  return base
})
const activeWorkspaceView = computed<ProjectWorkspaceView>(() => {
  const view = String(route.query.view || 'work')
  if (view === 'risk') return 'exceptions'
  if (['work', 'ledger', 'lifecycle', 'documents', 'audit', 'settlement', 'exceptions'].includes(view)) return view as ProjectWorkspaceView
  return 'ledger'
})
const workspaceViewMeta: Record<ProjectWorkspaceView, { label: string; section: string; description: string; tableTitle: string; tableHint: string }> = {
  work: { label: '我的工作', section: '工作视图', description: '集中查看需要我处理的到期事项、资料缺口和异常项目。', tableTitle: '需要我处理', tableHint: '按风险和到期时间排序。' },
  ledger: { label: '项目台账', section: '工作视图', description: '在同一张项目主表中筛选、分组和配置字段。', tableTitle: '项目主数据表', tableHint: '点击项目名称进入原项目详情，继续处理资料、审计和结算。' },
  lifecycle: { label: '生命周期看板', section: '工作视图', description: '按建档签约、施工验收、报审、审计定案和归档查看项目。', tableTitle: '项目生命周期', tableHint: '按业务阶段分组。' },
  documents: { label: '资料缺口', section: '专项视角', description: '聚焦仍缺关键资料的项目，明确负责人和补齐动作。', tableTitle: '待补资料项目', tableHint: '仅显示资料不齐的项目，并突出缺口与下一步动作。' },
  audit: { label: '审计进度', section: '专项视角', description: '查看已进入审计流程的项目、当前审计阶段和资料准备情况。', tableTitle: '审计项目跟进表', tableHint: '审计阶段已全部转换为中文业务名称。' },
  settlement: { label: '结算跟进', section: '专项视角', description: '集中查看合同金额、付款比例、结算状态和下一办理条件。', tableTitle: '结算跟进表', tableHint: '未结清项目优先展示。' },
  exceptions: { label: '异常项目', section: '专项视角', description: '聚焦计划逾期、关键资料缺失或付款未结清的项目。', tableTitle: '异常项目', tableHint: '按风险优先级排列。' },
}
const activeWorkspaceViewMeta = computed(() => workspaceViewMeta[activeWorkspaceView.value])
const tableWorkspaceView = computed(() => ['ledger', 'documents', 'audit', 'settlement'].includes(activeWorkspaceView.value))
const activeViewColumnKeys = computed(() => {
  if (activeWorkspaceView.value === 'ledger' && ledgerLayout.value === 'compact') {
    return ['select', 'project', 'owner', 'stage', 'docs', 'amount', 'actions']
  }
  return tableWorkspaceView.value
    ? viewColumnKeys[activeWorkspaceView.value as keyof typeof viewColumnKeys]
    : viewColumnKeys.ledger
})
const tableColumns = computed(() => baseTableColumns.filter((column) => {
  const key = String(column.colKey)
  if (!activeViewColumnKeys.value.includes(key)) return false
  if (activeWorkspaceView.value === 'ledger') return true
  return visibleProjectColumnKeys.value.includes(key)
}))
const configurableColumns = computed(() => baseTableColumns.filter((column) => (
  activeViewColumnKeys.value.includes(String(column.colKey))
  && !['select', 'project', 'actions'].includes(String(column.colKey))
)))
const displayRecords = computed(() => {
  const keyword = filters.keyword.trim().toLowerCase()
  let next = records.value.filter((record) => {
    if (keyword && ![record.projectName, record.projectCode, record.constructionUnit, record.ownerUnit, record.managerName].some((value) => String(value || '').toLowerCase().includes(keyword))) return false
    if (filters.projectStatus && record.projectStatus !== filters.projectStatus) return false
    if (filters.settlementStatus && record.settlementStatus !== filters.settlementStatus) return false
    if (filters.managerName && !String(record.managerName || '').includes(filters.managerName)) return false
    if (activeWorkspaceView.value === 'documents' && record.missingRequiredCount <= 0) return false
    if (activeWorkspaceView.value === 'audit' && !record.auditProjectId && ['not_linked', ''].includes(record.auditStage || '')) return false
    if (activeWorkspaceView.value === 'settlement' && record.settlementStatus === 'settled') return false
    if (activeWorkspaceView.value === 'exceptions' && !isProjectRisk(record)) return false
    return true
  })
  if (activeWorkspaceView.value === 'exceptions') next = [...next].sort((a, b) => exceptionScore(b) - exceptionScore(a))
  if (activeWorkspaceView.value === 'settlement') next = [...next].sort((a, b) => paymentRatio(a) - paymentRatio(b))
  return next
})
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
const advancedFilterCount = computed(() => [
  filters.projectStatus,
  filters.settlementStatus,
  filters.managerName,
].filter(Boolean).length)

const projectContextMenuItems = computed<ObjectContextMenuItem[]>(() => {
  const record = projectContextMenu.record
  if (!record) return []
  const items: ObjectContextMenuItem[] = [
    { key: 'view', label: '查看项目详情', icon: 'eye', shortcut: 'Enter' },
  ]
  if (authStore.isEditor) {
    items.push(
      { key: 'edit', label: '编辑项目', icon: 'edit-1' },
      { key: 'upload', label: '上传项目资料', icon: 'upload' },
    )
  }
  if (record.auditProjectId) {
    items.push({ key: 'audit', label: '查看审计进度', icon: 'view-module' })
  } else if (authStore.isEditor) {
    items.push({ key: 'start-audit', label: '发起审计', icon: 'play-circle' })
  }
  items.push(
    { key: 'divider-1', divider: true },
    {
      key: selectedProjectIds.value.includes(record.id) ? 'unselect' : 'select',
      label: selectedProjectIds.value.includes(record.id) ? '取消选择' : '加入批量选择',
      icon: 'check',
    },
  )
  if (canDelete.value) {
    items.push({ key: 'delete', label: '删除项目', icon: 'close', danger: true })
  }
  return items
})
const showProjectEmptyOnboarding = computed(() => !loading.value && total.value === 0 && activeFilterChips.value.length === 0)
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
const batchAuditEligibility = computed(() => partitionAuditStartCandidates(selectedRecords.value))
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
  if (project.auditProjectId) {
    items.push({
      label: '审计联动',
      title: '查看审计进度',
      description: '进入审计看板查看当前阶段、资料状态和操作记录。',
      level: 'primary',
      action: () => goAudit(project.auditProjectId),
    })
  } else if (authStore.isEditor) {
    items.push({
      label: '审计联动',
      title: '发起审计流程',
      description: '发起后会自动带入项目主数据，避免重复录入。',
      level: 'primary',
      action: () => startAudit(project),
    })
  }
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
      done: ['partially_paid', 'settled'].includes(project.settlementStatus),
    },
    {
      label: '审计联动',
      text: project.auditProjectId ? '已进入审计流程' : '尚未进入审计流程',
      done: Boolean(project.auditProjectId),
    },
  ]
})
const projectLifecycleSteps = computed<ProjectLifecycleStep[]>(() => {
  const project = currentProject.value
  if (!project) return []
  const documentReady = Number(project.missingRequiredCount || 0) === 0
  const hasFiles = Boolean(project.files?.length)
  const hasSettlements = Boolean(project.settlements?.length)
  const isSettled = project.settlementStatus === 'settled'
  const isArchived = project.projectStatus === 'archived'
  return [
    {
      key: 'base',
      label: '项目建档',
      status: project.projectCode || '待确认',
      description: `${projectStatusLabel(project.projectStatus)} · ${project.managerName || '未分配负责人'}`,
      state: 'complete',
    },
    {
      key: 'documents',
      label: '资料归集',
      status: documentReady ? '资料齐备' : `缺 ${project.missingRequiredCount} 类`,
      description: hasFiles ? `已上传 ${project.files?.length || 0} 份资料` : '尚未上传项目资料',
      state: documentReady ? 'complete' : 'warning',
    },
    {
      key: 'audit',
      label: '审计联动',
      status: project.auditProjectId ? '已进入审计' : '未发起',
      description: project.auditProjectId ? '可查看审计阶段和附件记录' : '需要时可从项目主档案发起审计',
      state: project.auditProjectId ? 'active' : 'pending',
    },
    {
      key: 'settlement',
      label: '结算付款',
      status: settlementStatusLabel(project.settlementStatus),
      description: hasSettlements ? `已维护 ${project.settlements?.length || 0} 条结算记录` : '尚未维护结算记录',
      state: isSettled ? 'complete' : hasSettlements ? 'active' : 'pending',
    },
    {
      key: 'archive',
      label: '归档闭环',
      status: isArchived ? '已归档' : '未归档',
      description: isArchived ? '项目已完成归档闭环' : '归档前请核对资料、审计和结算记录',
      state: isArchived ? 'complete' : 'pending',
    },
  ]
})

const summaryCards = computed(() => [
  { key: 'all', label: '项目总数', value: summary.totalProjects, hint: '全部项目主数据' },
  { key: 'active', label: '施工及审计中', value: summary.activeProjects, hint: '施工、报审、一审、二审推进中' },
  { key: 'settlement', label: '付款未清', value: summary.settlementProjects, hint: '已付款但部分未结清' },
  { key: 'audit', label: '已联动审计', value: summary.auditLinkedProjects, hint: '已进入审计流程的项目' },
  { key: 'missing', label: '资料不齐', value: summary.missingDocuments, hint: '需要补资料的项目' },
  { key: 'variation', label: '变更签证金额', value: formatWan(summary.variationAmount || 0), hint: amountToChineseUpper(summary.variationAmount || 0) },
])

const recentProjects = computed(() => [...records.value]
  .sort((a, b) => new Date(b.updatedAt || b.createdAt || 0).getTime() - new Date(a.updatedAt || a.createdAt || 0).getTime())
  .slice(0, 5))

const dueSoonProjects = computed(() => records.value.filter((record) => {
  if (!record.plannedEndDate) return false
  const today = new Date()
  const end = new Date(record.plannedEndDate)
  const diffDays = Math.ceil((end.getTime() - today.getTime()) / 86400000)
  return diffDays >= 0 && diffDays <= 7 && record.projectStatus !== 'archived'
}))

const riskProjects = computed(() => records.value.filter((record) => {
  return record.missingRequiredCount > 0 || isProjectOverdue(record) || record.settlementStatus === 'partially_paid'
}))

const lifecycleColumns = computed(() => [
  { key: 'contract', label: '建档签约', tone: 'blue', statuses: ['awarded', 'contract_signed'] },
  { key: 'construction', label: '施工验收', tone: 'cyan', statuses: ['under_construction', 'completed_acceptance'] },
  { key: 'submission', label: '报审准备', tone: 'amber', statuses: ['pending_submission'] },
  { key: 'audit', label: '审计定案', tone: 'purple', statuses: ['first_audit', 'second_audit', 'conclusion'] },
  { key: 'archive', label: '归档闭环', tone: 'green', statuses: ['archived'] },
].map((column) => ({
  ...column,
  records: displayRecords.value.filter((record) => column.statuses.includes(record.projectStatus)),
})))

const workQueueItems = computed(() => displayRecords.value
  .filter((project) => project.projectStatus !== 'archived')
  .map((project) => {
    const action = nextActionForProject(project)
    const overdue = isProjectOverdue(project)
    const level = overdue ? 'danger' : project.missingRequiredCount > 0 ? 'warning' : 'primary'
    return {
      id: `work-${project.id}`,
      project,
      title: action.label,
      description: action.hint,
      actionLabel: '打开项目',
      level,
      levelLabel: overdue ? '已逾期' : project.missingRequiredCount > 0 ? '缺资料' : '待推进',
      dueText: project.plannedEndDate ? `${shortDate(project.plannedEndDate)} 前` : '未设置期限',
      score: overdue ? 3 : project.missingRequiredCount > 0 ? 2 : 1,
    }
  })
  .sort((a, b) => b.score - a.score || String(a.project.plannedEndDate || '').localeCompare(String(b.project.plannedEndDate || '')))
  .slice(0, 14))

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
  return tagTheme(businessColor(projectStatusDict, status, businessColor(variationStatusDict, status, 'orange')))
}

function settlementTheme(status: string) {
  return tagTheme(businessColor(settlementStatusDict, status, 'gray'))
}

function tagTheme(color: string) {
  if (color === 'green') return 'success'
  if (color === 'red') return 'danger'
  if (color === 'orange') return 'warning'
  if (color === 'arcoblue') return 'primary'
  return 'default'
}

function projectStatusLabel(value: string) {
  return projectStatusOptions.value.find((item) => item.value === value)?.label || businessLabel(projectStatusDict, value)
}

function settlementStatusLabel(value: string) {
  return settlementStatusOptions.value.find((item) => item.value === value)?.label || businessLabel(settlementStatusDict, value)
}

function auditStageLabel(value: string) {
  if (!value || value === 'not_linked') return '未进入审计'
  return meta.auditStages.find((item) => item.value === value)?.label || businessLabel(auditStageDict, value, '待确认审计阶段')
}

function ownerInitial(record: ProjectRecord) {
  return String(record.managerName || '待').trim().slice(0, 1)
}

function paymentRatio(record: ProjectRecord) {
  const base = Number(record.contractAmount || record.submittedAmount || 0)
  if (!base) return 0
  return Math.min(100, Math.max(0, Math.round(Number(record.paidAmount || 0) / base * 100)))
}

function hasPayment(record: ProjectRecord) {
  return Number(record.paidAmount || 0) > 0
}

function isProjectRisk(record: ProjectRecord) {
  return record.missingRequiredCount > 0 || isProjectOverdue(record) || record.settlementStatus === 'partially_paid'
}

function exceptionScore(record: ProjectRecord) {
  return (isProjectOverdue(record) ? 4 : 0) + Math.min(3, Number(record.missingRequiredCount || 0)) + (record.settlementStatus === 'partially_paid' ? 2 : 0)
}

function exceptionReason(record: ProjectRecord) {
  if (isProjectOverdue(record)) return '计划逾期'
  if (record.missingRequiredCount > 0) return '关键资料缺失'
  if (record.settlementStatus === 'partially_paid') return '付款未结清'
  return '需要关注'
}

function exceptionDescription(record: ProjectRecord) {
  const items: string[] = []
  if (isProjectOverdue(record)) items.push(`计划完成日期为 ${shortDate(record.plannedEndDate)}`)
  if (record.missingRequiredCount > 0) items.push(`仍缺 ${record.missingRequiredCount} 类必需资料`)
  if (record.settlementStatus === 'partially_paid') items.push(`当前${settlementStatusLabel(record.settlementStatus)}`)
  return items.join('；') || '建议核对项目当前状态。'
}

function nextActionForProject(record: ProjectRecord) {
  if (isProjectOverdue(record)) return { label: '更新计划并确认责任人', hint: `原计划 ${shortDate(record.plannedEndDate)} 完成` }
  if (record.missingRequiredCount > 0) return { label: '补齐关键资料', hint: `仍缺 ${record.missingRequiredCount} 类，当前完整度 ${record.documentCompletion}%` }
  if (record.settlementStatus === 'partially_paid') return { label: '核对未结清款项', hint: `当前付款比例 ${paymentRatio(record)}%` }
  if (record.auditProjectId) return { label: '跟进审计进度', hint: `当前为${auditStageLabel(record.auditStage)}` }
  if (['completed_acceptance', 'pending_submission'].includes(record.projectStatus)) return { label: '准备并发起报审', hint: '资料齐备后进入审计流程' }
  if (record.projectStatus === 'conclusion') return { label: '办理结算与归档', hint: '核对定案金额和结算条件' }
  return { label: '推进下一业务阶段', hint: projectStatusHint(record.projectStatus) }
}

function variationStatusLabel(value: string) {
  return businessLabel(variationStatusDict, value, '未设置')
}

function settlementTypeLabel(value: string) {
  return settlementTypeOptions.find((item) => item.value === value)?.label || value || '未设置'
}

function variationTypeLabel(value: string) {
  return variationTypeOptions.find((item) => item.value === value)?.label || value || '未设置'
}

function materialStatusLabel(value: string) {
  return businessLabel(materialStatusDict, value, '未设置')
}

function projectStatusHint(value: string) {
  const hints: Record<string, string> = {
    awarded: '已确定中标，待签订正式合同',
    contract_signed: '合同已签，项目主数据应完整',
    under_construction: '现场施工中，关注进度和变更签证',
    completed_acceptance: '已竣工验收，准备结算资料',
    pending_submission: '准备送审，需要补齐报审资料',
    first_audit: '一审处理中，关注资料往来',
    second_audit: '二审处理中，关注核定差异',
    conclusion: '已形成定案结论，进入结清或归档',
    archived: '资料归档，项目闭环',
  }
  return hints[value] || '按当前业务阶段管理项目'
}

function resetProjectCreationFlow() {
  Object.assign(projectCreationFlow, {
    projectType: '',
    projectLocation: '',
  })
  projectWizardStepIndex.value = 0
}

function manualProjectDraftSnapshot(): ManualProjectIntakeDraftSnapshot {
  const paymentTerms = projectForm.paymentTerms
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
  const contractAmount = Number(projectForm.contractAmount || 0)
  const submittedAmount = Number(projectForm.submittedAmount || 0)
  const paidAmount = Number(projectForm.paidAmount || 0)
  return {
    values: {
      'project.name': projectForm.projectName.trim(),
      'party.owner': projectForm.ownerUnit.trim(),
      'party.contractor': projectForm.constructionUnit.trim(),
      'contract.amount': Number.isFinite(contractAmount) ? Math.round(contractAmount * 100) : 0,
      'contract.signed_date': projectForm.contractDate,
      'project.manager': projectForm.managerName.trim(),
      'contract.start_date': projectForm.plannedStartDate,
      'contract.end_date': projectForm.plannedEndDate,
      'contract.payment_terms': paymentTerms,
    },
    projectValues: {
      contractorName: projectForm.contractorName.trim(),
      contractorContact: projectForm.contractorContact.trim(),
      companyRole: projectForm.companyRole.trim(),
      settlementStatus: projectForm.settlementStatus,
      submittedAmount: Number.isFinite(submittedAmount) && submittedAmount >= 0 ? submittedAmount : 0,
      paidAmount: Number.isFinite(paidAmount) && paidAmount >= 0 ? paidAmount : 0,
      paymentTerms: projectForm.paymentTerms,
      plannedStartDate: projectForm.plannedStartDate,
      plannedEndDate: projectForm.plannedEndDate,
      description: appendProjectCreationNotes(projectForm.description),
    },
    uiState: {
      wizardStep: projectWizardStepIndex.value,
      pdfPage: manualPdfPage.value,
      pdfScale: manualPdfScale.value,
      previewCollapsed: manualPdfPreviewCollapsed.value,
    },
    documentId: manualContractDocument.value?.documentId || '',
    documentVersionId: manualContractDocument.value?.versionId || '',
  }
}

function restoreManualProjectDraftSnapshot(snapshot: ManualProjectIntakeDraftSnapshot) {
  restoringManualDraft.value = true
  fillProjectForm(null)
  resetProjectCreationFlow()
  const amountFen = Number(snapshot.values['contract.amount'] || 0)
  Object.assign(projectForm, {
    projectName: String(snapshot.values['project.name'] || ''),
    ownerUnit: String(snapshot.values['party.owner'] || ''),
    constructionUnit: String(snapshot.values['party.contractor'] || ''),
    contractAmount: Number.isFinite(amountFen) ? amountFen / 100 : 0,
    contractDate: String(snapshot.values['contract.signed_date'] || ''),
    managerName: String(snapshot.values['project.manager'] || ''),
    plannedStartDate: String(snapshot.values['contract.start_date'] || snapshot.projectValues.plannedStartDate || ''),
    plannedEndDate: String(snapshot.values['contract.end_date'] || snapshot.projectValues.plannedEndDate || ''),
    paymentTerms: Array.isArray(snapshot.values['contract.payment_terms'])
      ? snapshot.values['contract.payment_terms'].join('\n')
      : String(snapshot.projectValues.paymentTerms || ''),
    contractorName: String(snapshot.projectValues.contractorName || ''),
    contractorContact: String(snapshot.projectValues.contractorContact || ''),
    companyRole: String(snapshot.projectValues.companyRole || '工程咨询'),
    settlementStatus: String(snapshot.projectValues.settlementStatus || 'not_started'),
    submittedAmount: Number(snapshot.projectValues.submittedAmount || 0),
    paidAmount: Number(snapshot.projectValues.paidAmount || 0),
    description: String(snapshot.projectValues.description || ''),
  })
  projectWizardStepIndex.value = Math.min(
    Math.max(0, Number(snapshot.uiState.wizardStep || 0)),
    projectWizardSteps.value.length - 1,
  )
  manualPdfPage.value = Math.max(1, Number(snapshot.uiState.pdfPage || 1))
  manualPdfScale.value = Math.min(2.5, Math.max(0.5, Number(snapshot.uiState.pdfScale || 1)))
  manualPdfPreviewCollapsed.value = Boolean(snapshot.uiState.previewCollapsed)
  manualContractDocument.value = null
  void nextTick(() => {
    restoringManualDraft.value = false
    projectDialog.initialSnapshot = projectFormSnapshot()
  })
}

function manualDocumentRef(metadata: DocumentVersionMetadata): ManualContractDocumentRef {
  return {
    documentId: metadata.documentId,
    versionId: metadata.id,
    name: metadata.name,
    mimeType: metadata.mimeType,
    fileSize: metadata.fileSize,
  }
}

async function loadManualDocumentMetadata(
  versionId: string,
  isCurrent: () => boolean,
  publish: (metadata: DocumentVersionMetadata) => void = (metadata) => {
    manualContractDocument.value = manualDocumentRef(metadata)
  },
) {
  try {
    return await manualDocumentMetadataLoader.load(versionId, isCurrent, publish)
  } catch (error) {
    MessagePlugin.error(friendlyErrorMessage(error, '合同原文信息加载失败，请稍后重试。'))
    return false
  }
}

async function resumeManualDraft(
  draft: ProjectIntakeDraft,
  isCurrent: () => boolean = () => true,
) {
  if (!isCurrent()) return false
  const switched = await resumeDraft(draft, isCurrent)
  if (!switched || !isCurrent()) return false
  manualProjectIdempotencyKey.value = newManualProjectIntakeKey()
  if (draft.documentVersionId) {
    const draftId = draft.id
    const versionId = draft.documentVersionId
    const published = await loadManualDocumentMetadata(
      versionId,
      () => (
        isCurrent()
        && activeDraft.value?.id === draftId
        && activeDraft.value.documentVersionId === versionId
      ),
    )
    if (!published || !isCurrent()) return false
  }
  return isCurrent()
}

function resetManualProjectIntake() {
  manualDocumentMetadataLoader.invalidate()
  completeAndReset()
  manualContractDocument.value = null
  manualPdfPage.value = 1
  manualPdfScale.value = 1
  manualPdfPreviewCollapsed.value = false
  manualPdfUploading.value = false
  manualProjectIdempotencyKey.value = newManualProjectIntakeKey()
}

async function handleContractPdfUploaded(document: ManualContractDocumentRef) {
  manualDocumentMetadataLoader.invalidate()
  manualContractDocument.value = document
  manualPdfPage.value = 1
  await attachDocument(document.documentId, document.versionId)
}

function handleContractPdfPage(page: number) {
  manualPdfPage.value = page
  scheduleSave()
}

function handleContractPdfScale(scale: number) {
  manualPdfScale.value = scale
  scheduleSave()
}

function handleContractPdfCollapsed(collapsed: boolean) {
  manualPdfPreviewCollapsed.value = collapsed
  scheduleSave()
}

function appendProjectCreationNotes(description: string) {
  const notes = [
    projectCreationFlow.projectType ? `项目类型：${projectCreationFlow.projectType}` : '',
    projectCreationFlow.projectLocation ? `项目地点：${projectCreationFlow.projectLocation}` : '',
  ].filter(Boolean)
  if (!notes.length) return description
  const existing = String(description || '').trim()
  return [existing, notes.join('\n')].filter(Boolean).join('\n')
}

function validateProjectWizardStep() {
  const key = projectWizardStepKey.value
  resetProjectFormErrors()
  if (key === 'base') {
    if (!projectForm.projectName.trim()) projectFormErrors.projectName = '请填写项目名称，便于后续资料、结算和审计流转。'
    if (!projectForm.contractDate) projectFormErrors.contractDate = '请选择工程合同签订日期，系统将据此生成项目编号。'
    if (!projectForm.constructionUnit.trim()) projectFormErrors.constructionUnit = '请填写施工单位，系统将取核心字号生成项目编号。'
    if (!projectForm.ownerUnit.trim()) projectFormErrors.ownerUnit = '请填写建设单位。'
    if (Number(projectForm.contractAmount || 0) <= 0) projectFormErrors.contractAmount = '合同金额必须大于零。'
    if (!projectForm.paymentTerms.trim()) projectFormErrors.paymentTerms = '请对照合同填写付款条款。'
    if (projectForm.contractorContact.trim() && !/^[\d\s\-+()]{6,20}$/.test(projectForm.contractorContact.trim())) {
      projectFormErrors.contractorContact = '联系电话格式不正确，请填写手机号或固定电话。'
    }
    if (Number(projectForm.contractAmount || 0) > 0 && Number(projectForm.paidAmount || 0) > Number(projectForm.contractAmount || 0)) {
      projectFormErrors.paidAmount = '已付款金额不能大于合同金额，请核对付款记录。'
    }
  }
  if (key === 'stage' && projectForm.plannedStartDate && projectForm.plannedEndDate && projectForm.plannedStartDate > projectForm.plannedEndDate) {
    projectFormErrors.plannedEndDate = '计划完成日期不能早于计划开始日期。'
  }
  const firstErrorKey = Object.keys(projectFormErrors)[0] as ProjectFormKey | undefined
  if (firstErrorKey) {
    focusProjectField(firstErrorKey)
    return false
  }
  return true
}

function jumpProjectWizardStep(index: number) {
  if (index <= projectWizardStepIndex.value) {
    projectWizardStepIndex.value = index
  }
}

function prevProjectWizardStep() {
  if (projectWizardStepIndex.value > 0) projectWizardStepIndex.value -= 1
}

async function saveManualProjectDraft() {
  if (projectDialog.mode !== 'create' || projectDialog.saving) return
  if (!requireEditorAccess('保存项目草稿')) return
  projectDialog.saving = true
  try {
    if (!await flushSave()) return
    closeProjectDialog(true)
    MessagePlugin.success('草稿已保存，下次打开新建项目将自动恢复')
  } catch (error) {
    MessagePlugin.error(friendlyErrorMessage(error, '项目草稿保存失败，请稍后重试。'))
  } finally {
    projectDialog.saving = false
  }
}

async function handleProjectWizardConfirm() {
  if (!validateProjectWizardStep()) {
    MessagePlugin.error('请先完善当前步骤中的提示项')
    return
  }
  if (projectWizardStepIndex.value < projectWizardSteps.value.length - 1) {
    projectWizardStepIndex.value += 1
    return
  }
  await confirmManualProject()
}

async function confirmManualProject() {
  if (!requireEditorAccess('创建项目')) return
  if (!validateProjectForm()) {
    MessagePlugin.error('请先完善项目表单中的提示项')
    return
  }
  if (!manualContractDocument.value) {
    MessagePlugin.error('请先上传施工合同 PDF，再生成项目。')
    return
  }
  projectDialog.saving = true
  try {
    if (!await flushSave()) throw new Error('项目草稿保存失败，请处理提示后重试。')
    if (!activeDraft.value) throw new Error('项目草稿尚未保存，请稍后重试。')
    if (!manualProjectIdempotencyKey.value) {
      manualProjectIdempotencyKey.value = newManualProjectIntakeKey()
    }
    const result = await confirmManualProjectIntake(manualContractDocument.value.versionId, {
      idempotencyKey: manualProjectIdempotencyKey.value,
      formTemplateVersion: 'manual-project-wizard.v1',
      draftId: activeDraft.value.id,
      expectedDraftRevision: activeDraft.value.revision,
      contractValues: buildManualContractValues(projectForm),
      projectValues: buildManualProjectValues(projectForm, projectCreationFlow),
    })
    completeAndReset()
    closeProjectDialog(true)
    await Promise.all([loadSummary(), loadWorkItems(), loadRecords()])
    const created = records.value.find((record) => record.id === result.projectId)
    if (created) await selectProject(created)
    else {
      const projectId = result.projectId || result.project.id
      await router.push({
        path: '/project-management',
        query: { projectId, projectName: result.project.projectName },
      })
      detailDialogVisible.value = true
      await loadCurrentProject(projectId)
      activeTab.value = 'overview'
    }
    MessagePlugin.success('项目已生成')
  } catch (error) {
    MessagePlugin.error(friendlyErrorMessage(error, '项目生成失败，已保留当前表单和合同，可直接重试。'))
  } finally {
    projectDialog.saving = false
  }
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

const uploadLimitMb = computed(() => {
  const size = Number(meta.uploadSettings?.maxFileSizeMb || 100)
  return Math.max(1, size)
})

function validateUploadFileSize(file: File) {
  const limitBytes = uploadLimitMb.value * 1024 * 1024
  if (file.size <= limitBytes) return true
  MessagePlugin.error(`当前文件 ${formatSize(file.size)}，超过单文件上传上限 ${uploadLimitMb.value}MB。请压缩文件后重新上传，或联系管理员在后台调整最大上传大小。`)
  return false
}

function repairedFileName(value: string) {
  if (!value) return ''
  try {
    const repaired = decodeURIComponent(escape(value))
    return repaired || value
  } catch {
    return value
  }
}

function fileExtension(name: string) {
  const match = name.toLowerCase().match(/\.[^.]+$/)
  return match?.[0] || ''
}

function filePreviewKind(mimeType: string, fileName: string): 'none' | 'image' | 'frame' | 'text' {
  const ext = fileExtension(fileName)
  if (mimeType.startsWith('image/')) return 'image'
  if (mimeType === 'application/pdf' || ext === '.pdf') return 'frame'
  if (mimeType.startsWith('text/') || ['.txt', '.csv', '.json', '.md', '.log'].includes(ext)) return 'text'
  return 'none'
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
  if (!record.plannedEndDate || record.projectStatus === 'archived') return false
  const today = new Date().toISOString().slice(0, 10)
  return record.plannedEndDate < today
}

function filesByCategory(categoryKey: string) {
  return (currentProject.value?.files || []).filter((file) => file.categoryKey === categoryKey)
}

const projectDictionaryFieldMap: Partial<Record<ProjectTextFormKey, ProjectDictionaryGroup>> = {
  constructionUnit: 'construction_unit',
  ownerUnit: 'owner_unit',
  contractorName: 'contractor_name',
  managerName: 'manager_name',
  companyRole: 'company_role',
}

function projectDictionaryField(key: ProjectTextFormKey) {
  return projectDictionaryFieldMap[key]
}

function dictionarySelectOptions(groupKey?: ProjectDictionaryGroup) {
  if (!groupKey) return []
  return meta.dictionaryOptions?.[groupKey] || []
}

function localCompanyCoreName(value: string) {
  let name = String(value || '').replace(/[\s（）()·,，.。-]+/g, '')
  name = name.replace(/^江苏省?/, '')
  const suffixes = ['建设工程有限公司', '建筑工程有限公司', '工程建设有限公司', '建设有限公司', '工程有限公司', '有限公司', '有限责任公司', '股份有限公司', '集团有限公司', '公司']
  let changed = true
  while (changed && name) {
    changed = false
    const suffix = suffixes.find((item) => name.endsWith(item) && name.length > item.length)
    if (suffix) {
      name = name.slice(0, -suffix.length)
      changed = true
    }
  }
  return name || value
}

function localPinyinInitials(value: string) {
  const ascii = localCompanyCoreName(value).match(/[a-zA-Z0-9]/g)
  if (ascii?.length) return ascii.join('').toUpperCase().slice(0, 8)
  return '自动'
}

function buildProjectCodePreview(contractDate: string, constructionUnit: string) {
  const datePart = String(contractDate || '').replace(/\D/g, '').slice(0, 8) || 'YYYYMMDD'
  const unitPart = constructionUnit ? localPinyinInitials(constructionUnit) : '单位'
  return `${datePart}-${unitPart}-001`
}

async function handleProjectDictionaryChange(key: ProjectTextFormKey) {
  clearProjectFieldError(key)
  const groupKey = projectDictionaryField(key)
  const value = String(projectForm[key] || '').trim()
  if (!groupKey || !value) return
  if (dictionarySelectOptions(groupKey).some((item) => item.value === value || item.label === value)) return
  try {
    const option = await createProjectDictionaryOption(groupKey, value)
    meta.dictionaryOptions = {
      ...(meta.dictionaryOptions || {}),
      [groupKey]: [...dictionarySelectOptions(groupKey), option],
    }
  } catch (err) {
    MessagePlugin.warning(friendlyErrorMessage(err, '新选项暂未保存，项目保存时会再次尝试沉淀到字典。'))
  }
}

function fillProjectForm(record?: ProjectRecord | null) {
  Object.assign(projectForm, {
    id: record?.id || '',
    projectCode: record?.projectCode || '',
    projectName: record?.projectName || '',
    contractDate: record?.contractDate || '',
    constructionUnit: record?.constructionUnit || '',
    contractorName: record?.contractorName || '',
    contractorContact: record?.contractorContact || '',
    ownerUnit: record?.ownerUnit || '',
    companyRole: record?.companyRole || '工程咨询',
    managerName: record?.managerName || '',
    projectStatus: record?.projectStatus || 'awarded',
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

function projectFormSnapshot() {
  return JSON.stringify({
    projectCode: projectForm.projectCode,
    projectName: projectForm.projectName,
    contractDate: projectForm.contractDate,
    constructionUnit: projectForm.constructionUnit,
    contractorName: projectForm.contractorName,
    contractorContact: projectForm.contractorContact,
    ownerUnit: projectForm.ownerUnit,
    companyRole: projectForm.companyRole,
    managerName: projectForm.managerName,
    projectStatus: projectForm.projectStatus,
    settlementStatus: projectForm.settlementStatus,
    auditStage: projectForm.auditStage,
    contractAmount: Number(projectForm.contractAmount || 0),
    submittedAmount: Number(projectForm.submittedAmount || 0),
    paidAmount: Number(projectForm.paidAmount || 0),
    paymentTerms: projectForm.paymentTerms,
    plannedStartDate: projectForm.plannedStartDate,
    plannedEndDate: projectForm.plannedEndDate,
    description: projectForm.description,
    auditProjectId: projectForm.auditProjectId,
    creationFlow: { ...projectCreationFlow },
    wizardStep: projectWizardStepIndex.value,
  })
}

function resetProjectFormErrors() {
  Object.keys(projectFormErrors).forEach((key) => {
    delete projectFormErrors[key as ProjectFormKey]
  })
}

function clearProjectFieldError(key: ProjectFormKey) {
  if (projectFormErrors[key]) delete projectFormErrors[key]
}

function focusProjectField(key: ProjectFormKey) {
  nextTick(() => {
    const field = document.querySelector<HTMLElement>(`[data-project-field="${key}"] input, [data-project-field="${key}"] textarea, [data-project-field="${key}"]`)
    field?.focus()
  })
}

function validateProjectForm() {
  resetProjectFormErrors()
  if (!projectForm.projectName.trim()) {
    projectFormErrors.projectName = '请填写项目名称，便于后续资料、结算和审计流转。'
  }
  if (!projectForm.contractDate) {
    projectFormErrors.contractDate = '请选择工程合同签订日期，系统将据此生成项目编号。'
  }
  if (!projectForm.constructionUnit.trim()) {
    projectFormErrors.constructionUnit = '请填写施工单位，系统将取核心字号生成项目编号。'
  }
  if (projectForm.contractorContact.trim() && !/^[\d\s\-+()]{6,20}$/.test(projectForm.contractorContact.trim())) {
    projectFormErrors.contractorContact = '联系电话格式不正确，请填写手机号或固定电话。'
  }
  const contractAmount = Number(projectForm.contractAmount || 0)
  const submittedAmount = Number(projectForm.submittedAmount || 0)
  const paidAmount = Number(projectForm.paidAmount || 0)
  if (projectDialog.mode === 'create') {
    if (!projectForm.ownerUnit.trim()) {
      projectFormErrors.ownerUnit = '请填写建设单位。'
    }
    if (contractAmount <= 0) {
      projectFormErrors.contractAmount = '合同金额必须大于零。'
    }
    if (!projectForm.paymentTerms.trim()) {
      projectFormErrors.paymentTerms = '请对照合同填写付款条款。'
    }
  }
  if (contractAmount > 0 && submittedAmount > contractAmount) {
    projectFormErrors.submittedAmount = '送审金额不能大于合同金额，请核对金额口径。'
  }
  if (contractAmount > 0 && paidAmount > contractAmount) {
    projectFormErrors.paidAmount = '已付款金额不能大于合同金额，请核对付款记录。'
  }
  if (projectForm.plannedStartDate && projectForm.plannedEndDate && projectForm.plannedStartDate > projectForm.plannedEndDate) {
    projectFormErrors.plannedEndDate = '计划完成日期不能早于计划开始日期。'
  }
  const firstErrorKey = Object.keys(projectFormErrors)[0] as ProjectFormKey | undefined
  if (firstErrorKey) {
    focusProjectField(firstErrorKey)
    return false
  }
  return true
}

function isProjectFormDirty() {
  return projectDialog.visible && projectFormSnapshot() !== projectDialog.initialSnapshot
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

function saveProjectWorkspaceState() {
  const scrollContainer = document.querySelector<HTMLElement>('.system-content')
  window.sessionStorage.setItem(PROJECT_WORKSPACE_STATE_KEY, JSON.stringify({
    filters: normalizeProjectFilters({ ...filters }),
    activeSavedView: activeSavedView.value,
    activeCustomFilterId: activeCustomFilterId.value,
    activeSummaryKey: activeSummaryKey.value,
    groupBy: groupBy.value,
    visibleProjectColumnKeys: visibleProjectColumnKeys.value,
    scrollTop: scrollContainer?.scrollTop || 0,
  }))
}

function restoreProjectWorkspaceState() {
  try {
    const raw = window.sessionStorage.getItem(PROJECT_WORKSPACE_STATE_KEY)
    if (!raw) return 0
    const parsed = JSON.parse(raw) as {
      filters?: Partial<ProjectFilters>
      activeSavedView?: BuiltInProjectView
      activeCustomFilterId?: string
      activeSummaryKey?: string
      groupBy?: ProjectGroupBy
      visibleProjectColumnKeys?: string[]
      scrollTop?: number
    }
    if (parsed.filters) assignProjectFilters(parsed.filters)
    if (['all', 'risk', 'audit'].includes(String(parsed.activeSavedView))) {
      activeSavedView.value = parsed.activeSavedView as BuiltInProjectView
    }
    activeCustomFilterId.value = String(parsed.activeCustomFilterId || '')
    activeSummaryKey.value = String(parsed.activeSummaryKey || '')
    if (['none', 'status', 'owner', 'audit'].includes(String(parsed.groupBy))) {
      groupBy.value = parsed.groupBy as ProjectGroupBy
    }
    if (Array.isArray(parsed.visibleProjectColumnKeys)) {
      const allowed = new Set(baseTableColumns.map((column) => String(column.colKey)))
      const keys = parsed.visibleProjectColumnKeys.filter((key) => allowed.has(key))
      if (keys.includes('project')) visibleProjectColumnKeys.value = keys
    }
    return Math.max(0, Number(parsed.scrollTop || 0))
  } catch {
    return 0
  }
}

function saveCurrentFilterView() {
  filterViewDialog.name = ''
  filterViewDialog.error = ''
  filterViewDialog.visible = true
}

function closeFilterViewDialog() {
  filterViewDialog.visible = false
  filterViewDialog.error = ''
}

function confirmSaveFilterView() {
  const trimmed = filterViewDialog.name.trim()
  if (!trimmed) {
    filterViewDialog.error = '请填写方案名称，方便下次快速使用。'
    return
  }
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
  closeFilterViewDialog()
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
  detailDialogVisible.value = true
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
  let applied = false

  if (view === 'risk') {
    applied = true
    activeSummaryKey.value = 'risk'
    activeSavedView.value = 'risk'
    activeCustomFilterId.value = ''
    filters.onlyRisk = true
    filters.sort = 'plannedEndDate'
  } else if (view === 'due') {
    applied = true
    activeSummaryKey.value = 'due'
    activeSavedView.value = 'all'
    activeCustomFilterId.value = ''
    filters.onlyUpcomingDue = true
    filters.sort = 'plannedEndDate'
  }

  if (projectStatus) {
    applied = true
    filters.projectStatus = projectStatus
    activeSummaryKey.value = projectStatus
  }
  if (managerName) {
    applied = true
    filters.managerName = managerName
    activeSummaryKey.value = 'owner'
  }
  if (onlyMissingDocuments === '1' || onlyMissingDocuments === 'true') {
    applied = true
    filters.onlyMissingDocuments = true
    activeSummaryKey.value = 'missing'
  }
  if (onlyMonthlyNew === '1' || onlyMonthlyNew === 'true') {
    applied = true
    filters.onlyMonthlyNew = true
    activeSummaryKey.value = 'monthly'
    activeSavedView.value = 'all'
    activeCustomFilterId.value = ''
  }
  if (sort) {
    applied = true
    filters.sort = sort
  }
  if (applied) filters.page = 1
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
  if (key === 'active') filters.projectStatus = 'under_construction'
  else if (key === 'settlement') filters.settlementStatus = 'partially_paid'
  else if (key === 'audit') filters.onlyAuditLinked = true
  else if (key === 'missing') filters.onlyMissingDocuments = true
  filters.page = 1
  loadRecords()
}

function applyToolbarFilters() {
  advancedFiltersVisible.value = false
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

function openProjectContextMenu(record: TableData, event: Event) {
  const pointer = event as MouseEvent
  pointer.preventDefault()
  projectContextMenu.record = record as ProjectRecord
  projectContextMenu.x = pointer.clientX
  projectContextMenu.y = pointer.clientY
  projectContextMenu.visible = true
}

async function handleProjectContextAction(action: string) {
  const record = projectContextMenu.record
  if (!record) return
  if (action === 'view') await selectProject(record)
  if (action === 'edit') openProjectForm(record)
  if (action === 'upload') {
    await loadCurrentProject(record.id)
    if (currentProject.value) openFileDialog()
  }
  if (action === 'audit' && record.auditProjectId) goAudit(record.auditProjectId)
  if (action === 'start-audit') await startAudit(record)
  if (action === 'select' || action === 'unselect') toggleProjectSelection(record.id)
  if (action === 'delete') await confirmDeleteProject(record)
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
  if (!requireEditorAccess('批量发起审计')) return
  if (!selectedRecords.value.length) {
    MessagePlugin.warning('请先选择需要发起审计的项目')
    return
  }
  const { eligible: candidates, skipped } = batchAuditEligibility.value
  const skippedSummary = formatAuditStartSkippedSummary(skipped)
  if (!candidates.length) {
    MessagePlugin.warning(`所选项目均不满足发起审计条件：${skippedSummary}`)
    return
  }
  const message = skipped.length
    ? `确认将 ${candidates.length} 个项目发起审计流程？自动跳过：${skippedSummary}。`
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
    const results = await Promise.all(candidates.map(async (record) => {
      try {
        await startProjectAudit(record.id)
        return { record, error: null }
      } catch (error) {
        return { record, error }
      }
    }))
    const failed = results.filter((result) => result.error)
    const succeeded = results.length - failed.length
    if (succeeded) MessagePlugin.success(`已发起 ${succeeded} 个项目的审计流程`)
    if (failed.length) {
      const failedNames = failed.map(({ record }) => record.projectName || record.projectCode).join('、')
      MessagePlugin.warning(`${failed.length} 个项目未能发起审计：${failedNames}`)
    }
    selectedProjectIds.value = selectedProjectIds.value.filter((id) => failed.some((result) => result.record.id === id))
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
  if (item.actionPath && item.actionPath.startsWith('/audit')) {
    router.push(item.actionPath)
    return
  }
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
  advancedFiltersVisible.value = false
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

async function openProjectForm(
  record?: ProjectRecord | null,
  options: { restoreLatestDraft?: boolean } = {},
) {
  if (!requireEditorAccess(record ? '编辑项目' : '创建项目')) return
  if (!record) {
    projectDialog.mode = 'create'
    projectDialog.saving = false
    resetProjectFormErrors()
    resetProjectCreationFlow()
    resetManualProjectIntake()
    detailDialogVisible.value = false
    currentProject.value = null
    activeTab.value = 'overview'
    fillProjectForm(null)
    projectDialog.initialSnapshot = projectFormSnapshot()
    projectDialog.visible = true
    await loadDrafts()
    if (options.restoreLatestDraft !== false && manualDrafts.value[0]) {
      const restored = await resumeManualDraft(
        manualDrafts.value[0],
        () => projectDialog.visible && projectDialog.mode === 'create',
      )
      if (restored) MessagePlugin.info('已自动恢复最近一次项目草稿')
    }
    return
  }
  projectDialog.mode = 'edit'
  projectDialog.saving = false
  resetProjectFormErrors()
  fillProjectForm(record)
  resetProjectCreationFlow()
  projectDialog.initialSnapshot = projectFormSnapshot()
  projectDialog.visible = true
}

async function openManualIntakeFromRoute() {
  const versionId = String(route.query.intakeDocumentVersionId || '').trim()
  const routeRequest = beginManualIntakeRoute(versionId)
  if (!versionId || !authStore.isEditor) return false
  if (!projectDialog.visible || projectDialog.mode !== 'create') {
    await openProjectForm(null, { restoreLatestDraft: false })
  }
  if (!routeRequest.isCurrent()) return false
  const matchingDraft = manualDrafts.value.find((draft) => draft.documentVersionId === versionId)
  if (matchingDraft) {
    return resumeManualDraft(matchingDraft, routeRequest.isCurrent)
  }
  let routeMetadata: DocumentVersionMetadata | null = null
  const published = await loadManualDocumentMetadata(
    versionId,
    routeRequest.isCurrent,
    (metadata) => {
      routeMetadata = metadata
    },
  )
  if (!published || !routeMetadata || !routeRequest.isCurrent()) return false
  const metadata: DocumentVersionMetadata = routeMetadata
  manualContractDocument.value = manualDocumentRef(metadata)
  const attached = await attachDocument(metadata.documentId, metadata.id)
  if (!routeRequest.isCurrent()) return false
  if (!attached) {
    manualContractDocument.value = null
    return false
  }
  return true
}

function closeProjectDialog(force = false) {
  if (!force && projectDialog.saving) return
  projectDialog.visible = false
  projectDialog.saving = false
  projectDialog.initialSnapshot = ''
  resetProjectFormErrors()
}

function requestCloseProjectDialog() {
  if (projectDialog.saving) return
  if (!isProjectFormDirty()) {
    closeProjectDialog(true)
    return
  }
  openConfirm({
    title: projectDialog.mode === 'create' ? '关闭项目创建窗口？' : '放弃未保存的项目信息？',
    message: projectDialog.mode === 'create'
      ? '当前内容将保存为未完成草稿，下次可以继续填写。'
      : '当前项目表单还有未保存内容。关闭后，本次填写的信息将不会保留。',
    confirmText: projectDialog.mode === 'create' ? '保存草稿并关闭' : '放弃修改',
    cancelText: '继续编辑',
    danger: projectDialog.mode === 'edit',
    onConfirm: async () => {
      if (projectDialog.mode === 'create' && !await flushSave()) return
      closeProjectDialog(true)
    },
  })
}

function openFileDialog(category?: ProjectDocumentCategory | null) {
  if (!requireEditorAccess('上传资料')) return
  if (!currentProject.value) return
  resetUploadPreview()
  fileDialog.projectId = currentProject.value.id
  fileDialog.categoryKey = category?.categoryKey || meta.categories[0]?.categoryKey || ''
  fileDialog.displayName = ''
  fileDialog.file = null
  fileDialog.progress = 0
  fileDialog.visible = true
}

async function onFilePicked(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0] || null
  resetUploadPreview()
  if (file && !validateUploadFileSize(file)) {
    input.value = ''
    fileDialog.file = null
    fileDialog.progress = 0
    return
  }
  fileDialog.file = file
  if (file && !fileDialog.displayName) {
    fileDialog.displayName = file.name.replace(/\.[^.]+$/, '')
  }
  if (file) await prepareUploadPreview(file)
}

function closeFileDialog() {
  if (fileDialog.saving) return
  fileDialog.visible = false
  clearPickedFile()
}

function clearPickedFile() {
  fileDialog.file = null
  fileDialog.progress = 0
  resetUploadPreview()
  if (fileInputRef.value) fileInputRef.value.value = ''
}

function resetUploadPreview() {
  if (uploadPreview.url) URL.revokeObjectURL(uploadPreview.url)
  uploadPreview.kind = 'none'
  uploadPreview.url = ''
  uploadPreview.text = ''
}

async function prepareUploadPreview(file: File) {
  const kind = filePreviewKind(file.type, file.name)
  if (kind === 'image' || kind === 'frame') {
    uploadPreview.kind = kind
    uploadPreview.url = URL.createObjectURL(file)
    return
  }
  if (kind === 'text') {
    uploadPreview.kind = 'text'
    uploadPreview.text = (await file.text()).slice(0, 5000)
    return
  }
  uploadPreview.kind = 'none'
}

function openSettlementDialog(record?: ProjectSettlement | null) {
  if (!requireEditorAccess(record ? '编辑结算' : '新增结算')) return
  if (!currentProject.value) return
  settlementDialog.mode = record ? 'edit' : 'create'
  settlementDialog.id = record?.id || ''
  fillSettlementForm(record || null)
  settlementDialog.visible = true
}

function openVariationDialog(record?: ProjectVariation | null) {
  if (!requireEditorAccess(record ? '编辑签证' : '新增签证')) return
  if (!currentProject.value) return
  variationDialog.mode = record ? 'edit' : 'create'
  variationDialog.id = record?.id || ''
  fillVariationForm(record || null)
  variationDialog.visible = true
}

function openRenameDialog(file: ProjectFile) {
  if (!requireEditorAccess('重命名资料')) return
  renameDialog.id = file.id
  renameDialog.displayName = file.displayName
  renameDialog.visible = true
}

async function toggleCategoryRequired(category: ProjectDocumentCategory) {
  if (!authStore.isAdmin || categorySavingKey.value) return
  categorySavingKey.value = category.categoryKey
  try {
    const updated = await updateProjectDocumentCategory(category.categoryKey, {
      required: !category.required,
      requiredFromStage: categoryRequiredFromStage(category),
    })
    const index = meta.categories.findIndex((item) => item.categoryKey === updated.categoryKey)
    if (index >= 0) meta.categories[index] = updated
    MessagePlugin.success(updated.required ? '已设为必填资料' : '已设为按需资料')
    if (currentProject.value) await loadCurrentProject(currentProject.value.id)
    await Promise.all([loadSummary(), loadRecords()])
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '资料必填设置保存失败，请稍后重试'))
  } finally {
    categorySavingKey.value = ''
  }
}

function categoryRequiredFromStage(category: ProjectDocumentCategory) {
  return category.requiredFromStage || documentStageDefaults[category.categoryKey] || 'awarded'
}

function categoryIsAvailableNow(category: ProjectDocumentCategory) {
  const currentStage = currentProject.value?.projectStatus || ''
  const currentRank = lifecycleStageRank.get(currentStage)
  const requiredRank = lifecycleStageRank.get(categoryRequiredFromStage(category))
  return currentRank !== undefined && requiredRank !== undefined && currentRank >= requiredRank
}

function categoryIsRequiredNow(category: ProjectDocumentCategory) {
  return category.required && categoryIsAvailableNow(category)
}

function categoryRequirementLabel(category: ProjectDocumentCategory) {
  if (!category.required) return '按需'
  if (categoryIsRequiredNow(category)) return '当前必填'
  return `${projectStatusLabel(categoryRequiredFromStage(category))}起必填`
}

async function updateCategoryRequiredFromStage(category: ProjectDocumentCategory, value: unknown) {
  if (!authStore.isAdmin || categorySavingKey.value) return
  const requiredFromStage = String(value || '')
  if (!lifecycleStageRank.has(requiredFromStage)) return
  categorySavingKey.value = category.categoryKey
  try {
    const updated = await updateProjectDocumentCategory(category.categoryKey, {
      required: category.required,
      requiredFromStage,
    })
    const index = meta.categories.findIndex((item) => item.categoryKey === updated.categoryKey)
    if (index >= 0) meta.categories[index] = updated
    MessagePlugin.success(`已调整为${projectStatusLabel(requiredFromStage)}起生效`)
    if (currentProject.value) await loadCurrentProject(currentProject.value.id)
    await Promise.all([loadSummary(), loadRecords()])
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '资料生效阶段保存失败，请稍后重试'))
  } finally {
    categorySavingKey.value = ''
  }
}

async function loadMeta() {
  const value = await fetchProjectMeta()
  meta.categories = value.categories || []
  meta.projectStatuses = value.projectStatuses || []
  meta.settlementStatuses = value.settlementStatuses || []
  meta.dictionaryOptions = value.dictionaryOptions || {}
  meta.auditStages = value.auditStages || []
  meta.uploadSettings = value.uploadSettings || { maxFileSizeMb: 100 }
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
    saveProjectWorkspaceState()
    if (!currentProject.value || !records.value.find((item) => item.id === currentProject.value?.id)) {
      if (await openProjectFromRoute()) {
        return
      }
      currentProject.value = null
      detailDialogVisible.value = false
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

function openLifecycleTransition(snapshot: ProjectLifecycleSnapshot) {
  if (!requireEditorAccess('推进项目阶段')) return
  lifecycleTransitionSnapshot.value = snapshot
  lifecycleTransitionVisible.value = true
}

async function refreshLifecycleDetail() {
  const projectId = currentProject.value?.id
  lifecycleTransitionVisible.value = false
  if (!projectId) return
  const result = await settleLifecycleRefresh({
    snapshot: async () => {
      await nextTick()
      return lifecycleStatusRef.value?.refresh()
    },
    ancillary: [
      () => loadCurrentProject(projectId),
      () => loadSummary(),
      () => loadWorkItems(),
      () => loadRecords(),
    ],
  })
  if (result.snapshot.status === 'rejected') throw result.snapshot.reason
}

async function handleLifecycleTransitioned(_snapshot: ProjectLifecycleSnapshot) {
  await refreshLifecycleDetail()
  MessagePlugin.success('项目阶段已推进')
}

async function loadAll() {
  loading.value = true
  try {
    await Promise.all([loadMeta(), loadSummary(), loadWorkItems()])
    applyRouteFilters()
    await loadRecords()
    showAuditIntentGuide()
  } catch (err) {
    error.value = friendlyErrorMessage(err, '数据加载失败，请稍后重试或联系管理员')
    MessagePlugin.error(error.value)
  } finally {
    loading.value = false
  }
}

function showAuditIntentGuide() {
  if (route.query.intent !== 'start-audit') return
  MessagePlugin.info('请选择项目后点击“发起审计”，系统会自动带入项目主数据')
  router.replace({ path: '/project-management', query: {} })
}

async function selectProject(record: ProjectRecord, fetchDetail = true) {
  const routeProjectId = String(route.query.projectId || '')
  if (routeProjectId !== record.id) {
    await router.push({
      path: '/project-management',
      query: {
        projectId: record.id,
        projectName: record.projectName,
      },
    })
    return
  }
  if (currentProject.value?.id === record.id && !fetchDetail) return
  detailDialogVisible.value = true
  if (!fetchDetail) {
    currentProject.value = record
    activeTab.value = 'overview'
    return
  }
  await loadCurrentProject(record.id)
  activeTab.value = 'overview'
}

function closeProjectDetail() {
  detailDialogVisible.value = false
  currentProject.value = null
  activeTab.value = 'overview'
  closeFilePreview()
  if (route.path === '/project-management' && route.query.projectId) {
    router.push({ path: '/project-management', query: { view: activeWorkspaceView.value } })
  }
}

async function saveProject() {
  if (projectDialog.mode !== 'edit' || !requireEditorAccess('编辑项目')) return
  if (!validateProjectForm()) {
    MessagePlugin.error('请先完善项目表单中的提示项')
    return
  }
  projectDialog.saving = true
  try {
    const payload = {
      ...buildProjectMutationPayload('edit', projectForm),
      contractAmount: Number(projectForm.contractAmount || 0),
      submittedAmount: Number(projectForm.submittedAmount || 0),
      paidAmount: Number(projectForm.paidAmount || 0),
      description: projectForm.description,
    }
    const result = await updateProjectRecord(projectForm.id, payload)
    MessagePlugin.success('项目已保存')
    closeProjectDialog(true)
    await Promise.all([loadSummary(), loadWorkItems(), loadRecords()])
    await selectProject(result)
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '项目保存失败，请稍后重试或联系管理员'))
  } finally {
    projectDialog.saving = false
  }
}

async function startAudit(record: ProjectRecord) {
  if (!requireEditorAccess('发起审计')) return
  if (!record?.id) return
  if (record.auditProjectId) {
    MessagePlugin.warning('该项目已进入审计流程，请直接查看审计进度')
    return
  }
  const eligibility = getAuditStartEligibility(record)
  if (!eligibility.eligible) {
    MessagePlugin.warning(auditStartEligibilityMessage(eligibility.reason))
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
  if (!requireEditorAccess('上传资料')) return
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
  if (!validateUploadFileSize(fileDialog.file)) {
    return
  }
  fileDialog.saving = true
  fileDialog.progress = 1
  try {
    await uploadProjectFile(fileDialog.projectId, {
      categoryKey: fileDialog.categoryKey,
      displayName: fileDialog.displayName,
      file: fileDialog.file,
    }, (percent) => { fileDialog.progress = percent })
    MessagePlugin.success('资料已上传')
    fileDialog.visible = false
    clearPickedFile()
    await loadCurrentProject(fileDialog.projectId)
    await loadRecords()
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '资料上传失败，请检查文件后重试'))
  } finally {
    fileDialog.saving = false
  }
}

async function saveSettlement() {
  if (!requireEditorAccess(settlementDialog.mode === 'edit' ? '编辑结算' : '新增结算')) return
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
  if (!requireEditorAccess(variationDialog.mode === 'edit' ? '编辑签证' : '新增签证')) return
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
  if (!requireEditorAccess('重命名资料')) return
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
    closeFilePreview()
    filePreview.name = repairedFileName(file.originalName || file.displayName)
    filePreview.kind = filePreviewKind(blob.type || file.mimeType, file.originalName || file.displayName)
    if (filePreview.kind === 'text') {
      filePreview.text = (await blob.text()).slice(0, 20000)
    } else if (filePreview.kind === 'image' || filePreview.kind === 'frame') {
      filePreview.url = URL.createObjectURL(blob)
    }
    filePreview.visible = true
    await nextTick()
    document.querySelector<HTMLElement>('.inline-preview-shell')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '预览失败，请下载后查看'))
  }
}

function closeFilePreview() {
  if (filePreview.url) URL.revokeObjectURL(filePreview.url)
  filePreview.visible = false
  filePreview.loading = false
  filePreview.kind = 'none'
  filePreview.url = ''
  filePreview.text = ''
  filePreview.name = ''
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

async function downloadProjectArchive() {
  const project = currentProject.value
  if (!project || projectArchiveDownloading.value) return
  projectArchiveDownloading.value = true
  try {
    const blob = await fetchProjectFilesArchiveBlob(project.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${project.projectName || '项目'}-项目资料.zip`
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 3000)
    MessagePlugin.success('项目资料压缩包已开始下载')
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '项目资料打包下载失败，请稍后重试'))
  } finally {
    projectArchiveDownloading.value = false
  }
}

async function confirmDeleteProject(record: ProjectRecord) {
  if (!requireAdminAccess('删除项目')) return
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
  if (!requireAdminAccess('删除资料')) return
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

function handleSidebarAction(event: Event) {
  const action = (event as CustomEvent<{ action?: string }>).detail?.action
  if (action === 'project:create') openProjectForm()
  if (action === 'project:save-view') saveCurrentFilterView()
}

onMounted(async () => {
  loadSavedFilterViews()
  const savedLedgerLayout = window.localStorage.getItem(LEDGER_LAYOUT_KEY)
  if (savedLedgerLayout === 'info' || savedLedgerLayout === 'compact' || savedLedgerLayout === 'cards') ledgerLayout.value = savedLedgerLayout
  const restoredScrollTop = restoreProjectWorkspaceState()
  window.addEventListener('keydown', handleProjectKeyboard)
  window.addEventListener('jiqing-sidebar-action', handleSidebarAction)
  await loadAll()
  try {
    await openManualIntakeFromRoute()
  } catch (error) {
    MessagePlugin.error(friendlyErrorMessage(error, '合同原文无法接入项目草稿，请稍后重试。'))
  }
  await nextTick()
  const scrollContainer = document.querySelector<HTMLElement>('.system-content')
  if (scrollContainer && restoredScrollTop > 0) scrollContainer.scrollTop = restoredScrollTop
})

onBeforeUnmount(() => {
  if (projectDialog.visible && projectDialog.mode === 'create') void flushSave()
  saveProjectWorkspaceState()
  window.removeEventListener('keydown', handleProjectKeyboard)
  window.removeEventListener('jiqing-sidebar-action', handleSidebarAction)
  closeFilePreview()
  resetUploadPreview()
})

watch(
  () => route.query.projectId,
  async (projectId, previousProjectId) => {
    if (!projectId || projectId === previousProjectId) return
    await openProjectFromRoute()
  },
)

watch(ledgerLayout, (layout) => {
  window.localStorage.setItem(LEDGER_LAYOUT_KEY, layout)
  if (layout === 'cards') columnSettingsVisible.value = false
})

watch(
  () => route.query.intakeDocumentVersionId,
  async (versionId, previousVersionId) => {
    if (versionId === previousVersionId) return
    try {
      await openManualIntakeFromRoute()
    } catch (error) {
      MessagePlugin.error(friendlyErrorMessage(error, '合同原文无法接入项目草稿，请稍后重试。'))
    }
  },
)

watch(
  () => [
    projectDialog.visible,
    projectDialog.mode,
    projectFormSnapshot(),
    manualContractDocument.value?.versionId || '',
    manualPdfPage.value,
    manualPdfScale.value,
    manualPdfPreviewCollapsed.value,
  ] as const,
  ([visible, mode]) => {
    if (!visible || mode !== 'create' || restoringManualDraft.value || projectDialog.saving) return
    scheduleSave()
  },
  { flush: 'post' },
)

watch(detailDialogVisible, (visible) => {
  if (!visible) {
    currentProject.value = null
    activeTab.value = 'overview'
    closeFilePreview()
    if (route.path === '/project-management' && route.query.projectId) {
      router.push({ path: '/project-management', query: { view: activeWorkspaceView.value } })
    }
  }
})
</script>

<style scoped>
.project-management {
  display: grid;
  gap: 12px;
  min-height: 100%;
  padding: 18px 20px 28px;
  background: #f7f9fc;
}

.view-path {
  color: #8793a7;
  font-size: 12px;
}

.personal-view-strip {
  display: flex;
  align-items: center;
  gap: 6px;
  min-height: 34px;
  padding: 0 4px;
  overflow-x: auto;
}

.personal-view-strip > span {
  flex: 0 0 auto;
  color: #8a96a8;
  font-size: 12px;
}

.personal-view-strip button {
  min-height: 28px;
  padding: 0 10px;
  color: #66758d;
  background: #fff;
  border: 1px solid #e1e7f0;
  border-radius: 6px;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
}

.personal-view-strip button.active,
.personal-view-strip button:hover {
  color: #165dff;
  border-color: #b9cdf5;
  background: #f3f7ff;
}

.workspace-panel {
  min-width: 0;
  padding: 18px;
  background: #fff;
  border: 1px solid #e3e9f2;
  border-radius: 10px;
  box-shadow: 0 7px 24px rgba(35, 63, 105, .045);
}

.surface-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
  padding-bottom: 14px;
  border-bottom: 1px solid #edf1f6;
}

.surface-heading > div:first-child {
  display: grid;
  gap: 4px;
}

.surface-heading strong {
  color: #263650;
  font-size: 15px;
}

.surface-heading span,
.surface-heading em {
  color: #8b97a9;
  font-size: 12px;
  font-style: normal;
}

.work-queue {
  display: grid;
}

.work-queue-row {
  position: relative;
  display: grid;
  grid-template-columns: 62px minmax(260px, 1fr) 110px 110px 78px;
  align-items: center;
  gap: 14px;
  min-height: 62px;
  padding: 9px 12px;
  color: #64738a;
  background: #fff;
  border: 0;
  border-bottom: 1px solid #edf1f6;
  cursor: pointer;
  text-align: left;
  font: inherit;
}

.work-queue-row::before {
  content: '';
  position: absolute;
  left: 0;
  top: 14px;
  bottom: 14px;
  width: 3px;
  border-radius: 3px;
  background: #6e9bed;
}

.work-queue-row[data-level='danger']::before { background: #e85b62; }
.work-queue-row[data-level='warning']::before { background: #e5a33c; }
.work-queue-row:hover { background: #f8fbff; }
.work-queue-row > div { display: grid; gap: 4px; min-width: 0; }
.work-queue-row > div strong { overflow: hidden; color: #32415b; font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.work-queue-row > div span, .work-queue-row > span, .work-queue-row time { color: #8793a6; font-size: 11px; }
.work-queue-row > em { color: #165dff; font-size: 12px; font-style: normal; text-align: right; }

.work-queue-row__level {
  justify-self: start;
  padding: 4px 7px;
  color: #596d8c !important;
  background: #eff4fb;
  border-radius: 5px;
}

.work-queue-row[data-level='danger'] .work-queue-row__level { color: #ba5157 !important; background: #fff0f0; }
.work-queue-row[data-level='warning'] .work-queue-row__level { color: #a86f18 !important; background: #fff6e7; }

.lifecycle-board {
  display: grid;
  grid-template-columns: repeat(5, minmax(220px, 1fr));
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 6px;
}

.lifecycle-column {
  min-width: 220px;
  overflow: hidden;
  background: #f7f9fc;
  border: 1px solid #e5eaf2;
  border-radius: 8px;
}

.lifecycle-column > header {
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  padding: 0 11px;
  border-bottom: 1px solid #e8edf4;
}

.lifecycle-column > header > span { width: 7px; height: 7px; border-radius: 50%; background: #5d8ee6; }
.lifecycle-column > header > span[data-tone='cyan'] { background: #37aeb1; }
.lifecycle-column > header > span[data-tone='amber'] { background: #dda13c; }
.lifecycle-column > header > span[data-tone='purple'] { background: #8a6fd0; }
.lifecycle-column > header > span[data-tone='green'] { background: #43a876; }
.lifecycle-column > header strong { color: #45546c; font-size: 12px; }
.lifecycle-column > header em { min-width: 22px; padding: 2px 6px; color: #71819b; background: #e9eef6; border-radius: 10px; font-size: 10px; font-style: normal; text-align: center; }
.lifecycle-column__body { display: grid; gap: 8px; max-height: 620px; padding: 9px; overflow-y: auto; }
.lifecycle-column__empty { padding: 24px 8px; color: #a1abba; font-size: 11px; text-align: center; }

.lifecycle-card {
  display: grid;
  gap: 7px;
  padding: 11px;
  color: #718098;
  background: #fff;
  border: 1px solid #e4eaf2;
  border-radius: 7px;
  box-shadow: 0 3px 10px rgba(38, 63, 102, .035);
  cursor: pointer;
  text-align: left;
  font: inherit;
}

.lifecycle-card:hover { border-color: #b9cdf4; box-shadow: 0 7px 17px rgba(48, 86, 148, .08); }
.lifecycle-card > strong { overflow: hidden; color: #34435c; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.lifecycle-card > span, .lifecycle-card time { font-size: 10px; }
.lifecycle-card > div { display: flex; justify-content: space-between; gap: 8px; }
.lifecycle-card > div em { color: #4b866b; font-size: 10px; font-style: normal; }
.lifecycle-card > div em.warning { color: #b67a1d; }
.lifecycle-card p { margin: 0; padding-top: 7px; color: #426cb6; border-top: 1px solid #eef2f6; font-size: 11px; }

.exception-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.exception-card {
  display: grid;
  gap: 10px;
  min-height: 166px;
  padding: 15px;
  color: #718098;
  background: #fff;
  border: 1px solid #e6eaf1;
  border-top: 3px solid #e36a70;
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  font: inherit;
}

.exception-card:hover { border-color: #e7aeb1; box-shadow: 0 8px 20px rgba(132, 61, 66, .07); }
.exception-card > div, .exception-card footer { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.exception-card > div > span { color: #8d99aa; font-size: 11px; }
.exception-card > strong { color: #34435b; font-size: 14px; }
.exception-card p { margin: 0; color: #77859a; font-size: 12px; line-height: 1.6; }
.exception-card footer { margin-top: auto; padding-top: 9px; border-top: 1px solid #eef1f5; }
.exception-card footer span { font-size: 11px; }
.exception-card footer em { color: #165dff; font-size: 11px; font-style: normal; }

.owner-table-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.owner-table-cell > span {
  width: 26px;
  height: 26px;
  display: grid;
  flex: 0 0 auto;
  place-items: center;
  color: #416ebc;
  background: #eaf1ff;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
}

.owner-table-cell > div,
.updated-cell,
.next-action-cell {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.owner-table-cell strong,
.audit-cell strong,
.updated-cell strong,
.next-action-cell strong { color: #41516b; font-size: 12px; }
.owner-table-cell em,
.updated-cell span,
.next-action-cell span,
.status-stack > span { color: #929dac; font-size: 10px; font-style: normal; }

.ledger-panel {
  border-radius: 10px;
  box-shadow: 0 7px 24px rgba(35, 63, 105, .045);
}

.project-management :deep(.page-header) {
  margin-bottom: 0;
}

.project-management :deep(.page-header__copy) {
  gap: 2px;
}

.project-management :deep(.page-header__description) {
  line-height: 1.45;
}

.project-management :deep(.page-header__meta) {
  margin-top: 2px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: var(--space-2);
}

.project-empty-onboarding {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: 10px var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--color-brand-200);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.project-empty-onboarding h3 {
  margin: 1px 0;
  font-size: var(--text-base);
  line-height: 1.25;
}

.project-empty-onboarding p {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.summary-card {
  text-align: left;
  min-height: 72px;
  padding: 10px 12px;
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
.summary-card strong { display: block; margin: 3px 0 2px; font-size: var(--text-xl); line-height: 1.2; }
.summary-card em { color: var(--text-tertiary); font-size: var(--text-xs); }

.project-dashboard {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(260px, 0.8fr) minmax(280px, 0.9fr);
  gap: var(--space-3);
}

.project-dashboard--secondary {
  margin-top: 0;
  grid-template-columns: minmax(0, 1.15fr) minmax(180px, 0.5fr) minmax(180px, 0.5fr);
  grid-auto-rows: minmax(0, 108px);
  height: 108px;
  overflow: hidden;
  gap: var(--space-2);
}

.dashboard-panel {
  min-width: 0;
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}

.project-dashboard--secondary .dashboard-panel {
  min-height: 0;
  height: 108px;
  overflow: hidden;
  padding: 8px 10px;
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

.project-dashboard--secondary .dashboard-panel__head {
  gap: var(--space-2);
  margin-bottom: 6px;
}

.dashboard-panel__head h3 {
  margin: 0;
  font-size: var(--text-lg);
}

.project-dashboard--secondary .dashboard-panel__head h3 {
  font-size: var(--text-sm);
  line-height: 1.25;
}

.dashboard-panel__head p {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.project-dashboard--secondary .dashboard-panel__head p {
  display: none;
}

.focus-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-2);
}

.project-dashboard--secondary .focus-metrics {
  gap: 6px;
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

.project-dashboard--secondary .focus-metrics button {
  gap: 2px;
  padding: 6px 8px;
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

.project-dashboard--secondary .focus-metrics strong {
  font-size: var(--text-base);
  line-height: 1.1;
}

.owner-list,
.recent-list {
  display: grid;
  gap: 8px;
}

.project-dashboard--secondary .owner-list,
.project-dashboard--secondary .recent-list {
  gap: 4px;
  max-height: 30px;
  overflow: hidden;
}

.owner-list button,
.recent-list button {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: var(--space-2);
  align-items: center;
  padding: 9px 10px;
}

.project-dashboard--secondary .owner-list button,
.project-dashboard--secondary .recent-list button {
  padding: 4px 8px;
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

.project-work-items--secondary {
  margin-top: 0;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-2);
  min-height: 58px;
  max-height: 72px;
  overflow: hidden;
  padding: 8px 10px;
}

.project-work-items__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.project-work-items--secondary .project-work-items__head {
  align-items: center;
}

.project-work-items__head h3 {
  margin: 4px 0;
  font-size: var(--text-lg);
}

.project-work-items--secondary .project-work-items__head h3 {
  margin: 0;
  font-size: var(--text-sm);
}

.project-work-items__head p {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.project-work-items--secondary .project-work-items__head p {
  display: none;
}

.project-work-list {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
}

.project-work-items--secondary .project-work-list {
  grid-template-columns: minmax(180px, 1fr);
  min-width: 220px;
  max-width: 320px;
  gap: 6px;
}

.project-work-items--secondary .quiet-empty {
  margin: 0;
  text-align: right;
  white-space: nowrap;
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

.project-work-items--secondary .project-work-card {
  gap: 2px;
  padding: 6px 8px;
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
  gap: var(--space-2);
  padding: var(--space-2);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}

.view-toolbar__filters,
.view-toolbar__utilities {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  min-width: 0;
}

.view-toolbar__utilities {
  justify-content: space-between;
  padding-top: var(--space-2);
  border-top: 1px solid #edf1f6;
}

.view-toolbar__filters > * {
  min-width: 0;
}

.view-toolbar__filters > .project-keyword-input {
  flex: 1 1 260px;
}

.view-toolbar__filters > .arco-select-view,
.view-toolbar__filters > .arco-input-wrapper:not(.project-keyword-input),
.view-toolbar__filters > .arco-input-wrapper {
  flex: 0 1 132px;
  width: auto;
}

.view-toolbar__filters :deep(.arco-select-view) {
  flex: 0 1 132px;
  width: auto;
}

.view-toolbar__filters :deep(.arco-input-wrapper:not(.project-keyword-input)) {
  flex: 0 1 132px;
  width: auto;
}

.toolbar-check {
  flex: 0 0 auto;
}

.view-toolbar__filters > .arco-btn {
  flex: 0 0 76px;
}

.view-toolbar--ledger {
  gap: 0;
  padding: 0;
  overflow: hidden;
  border-color: #dfe6f0;
  border-radius: 10px;
  background: #fff;
}

.ledger-command-row {
  display: grid;
  grid-template-columns: minmax(360px, 520px) 108px 162px 82px 1fr;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
}

.ledger-command-row > * {
  min-width: 0;
}

.ledger-command-row :deep(.arco-input-wrapper),
.ledger-command-row :deep(.arco-select-view) {
  height: 40px;
  border-color: #dfe6f0;
  border-radius: 7px;
  background: #fff;
  box-shadow: none;
}

.ledger-command-row :deep(.arco-input-wrapper:hover),
.ledger-command-row :deep(.arco-select-view:hover) {
  border-color: #b9c8dc;
}

.ledger-command-row :deep(.arco-input-wrapper-focus),
.ledger-command-row :deep(.arco-select-view-focus) {
  border-color: #7aa5f8;
  box-shadow: 0 0 0 2px rgba(22, 93, 255, .08);
}

.ledger-command-row > .arco-btn {
  height: 40px;
  border-radius: 7px;
  font-size: 14px;
}

.ledger-filter-trigger,
.ledger-clear-filters,
.ledger-view-actions button,
.ledger-selection-context button {
  border: 0;
  background: transparent;
  cursor: pointer;
  font: inherit;
}

.ledger-filter-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  height: 40px;
  padding: 0 12px;
  color: #4d5f78;
  border: 1px solid #dfe6f0;
  border-radius: 7px;
  background: #fff;
  font-size: 14px;
}

.ledger-filter-trigger:hover,
.ledger-filter-trigger.active {
  color: #165dff;
  border-color: #9ab9f5;
  background: #f6f9ff;
}

.ledger-filter-trigger:focus {
  outline: none;
}

.ledger-filter-trigger:focus-visible {
  border-color: #7aa5f8;
  box-shadow: 0 0 0 2px rgba(22, 93, 255, .12);
}

.ledger-filter-trigger b {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 19px;
  height: 19px;
  padding: 0 5px;
  color: #fff;
  border-radius: 10px;
  background: #165dff;
  font-size: 11px;
  line-height: 1;
}

.ledger-sort-control {
  position: relative;
  display: flex;
  align-items: center;
}

.ledger-sort-control > .arco-icon {
  position: absolute;
  z-index: 1;
  left: 11px;
  color: #718099;
  pointer-events: none;
}

.ledger-sort-control :deep(.arco-select-view) {
  width: 100%;
  padding-left: 30px;
}

.ledger-advanced-filters {
  display: grid;
  grid-template-columns: repeat(3, minmax(160px, 220px)) 1fr;
  align-items: end;
  gap: 14px;
  padding: 14px 12px;
  border-top: 1px solid #edf1f6;
  background: #fafbfd;
}

.ledger-advanced-filters label {
  display: grid;
  gap: 6px;
  color: #5e6d84;
  font-size: 12px;
}

.ledger-advanced-filters :deep(.arco-select-view),
.ledger-advanced-filters :deep(.arco-input-wrapper) {
  width: 100%;
  height: 36px;
  border-color: #dfe6f0;
  border-radius: 6px;
  background: #fff;
}

.ledger-clear-filters {
  justify-self: end;
  min-height: 36px;
  padding: 0 10px;
  color: #566985;
  font-size: 13px;
}

.ledger-clear-filters:hover:not(:disabled) {
  color: #165dff;
}

.ledger-clear-filters:disabled {
  color: #b9c2d0;
  cursor: not-allowed;
}

.view-toolbar--ledger .view-toolbar__utilities {
  min-height: 46px;
  padding: 0 12px;
  border-top: 1px solid #edf1f6;
}

.view-toolbar--ledger .view-toolbar__utilities.is-selection-mode {
  background: #f3f7ff;
  border-top-color: #dce8ff;
}

.view-toolbar--ledger .saved-views {
  align-self: stretch;
  flex-wrap: nowrap;
  gap: 26px;
}

.view-toolbar--ledger .saved-views button {
  position: relative;
  min-height: 45px;
  padding: 0 2px;
  border: 0;
  color: #5f6f86;
  background: transparent;
  font-size: 13px;
}

.view-toolbar--ledger .saved-views button::after {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  height: 2px;
  background: transparent;
  content: '';
}

.view-toolbar--ledger .saved-views button:hover,
.view-toolbar--ledger .saved-views button.active {
  color: #165dff;
  background: transparent;
}

.view-toolbar--ledger .saved-views button.active::after {
  background: #165dff;
}

.view-toolbar--ledger .custom-views {
  flex: 1 1 auto;
  padding-left: 4px;
}

.ledger-view-actions {
  display: flex;
  align-items: center;
  gap: 18px;
  margin-left: auto;
}

.ledger-view-actions button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  padding: 0 2px;
  color: #5d6e86;
  font-size: 13px;
}

.ledger-view-actions button:hover:not(:disabled) {
  color: #165dff;
}

.ledger-view-actions button:disabled {
  color: #b8c1ce;
  cursor: not-allowed;
}

.ledger-group-control {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #66778f;
}

.ledger-group-control :deep(.arco-select-view) {
  width: 104px;
  min-height: 32px;
  padding-left: 2px;
  border: 0;
  background: transparent;
  box-shadow: none;
}

.ledger-selection-context {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-height: 45px;
  color: #3e5f91;
  font-size: 13px;
}

.ledger-selection-context__count {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-right: 8px;
  color: #254f91;
}

.ledger-selection-context button {
  min-height: 30px;
  padding: 0 10px;
  color: #315f9f;
  border-radius: 5px;
}

.ledger-selection-context button:hover {
  background: #edf4ff;
}

.ledger-selection-context button.primary {
  color: #fff;
  background: #165dff;
}

.ledger-selection-context button.primary:disabled {
  opacity: .6;
  cursor: wait;
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

.panel-head__side {
  display: flex;
  align-items: center;
  gap: 14px;
}

.ledger-layout-switch {
  display: inline-flex;
  align-items: center;
  padding: 3px;
  background: #f1f4f8;
  border: 1px solid #e2e7ef;
  border-radius: 7px;
}

.ledger-layout-switch button {
  min-height: 28px;
  padding: 0 10px;
  color: #77859a;
  background: transparent;
  border: 0;
  border-radius: 5px;
  cursor: pointer;
  font: inherit;
  font-size: 12px;
}

.ledger-layout-switch button:hover,
.ledger-layout-switch button.active {
  color: #165dff;
  background: #fff;
  box-shadow: 0 2px 7px rgba(40, 69, 114, .08);
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

.project-table-groups--compact :deep(.arco-table-th),
.project-table-groups--compact :deep(.arco-table-td) {
  padding-top: 8px;
  padding-bottom: 8px;
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

.construction-unit-cell,
.payment-cell {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.construction-unit-cell strong,
.payment-cell strong {
  overflow: hidden;
  color: #41516b;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.construction-unit-cell span,
.payment-cell span,
.amount-payment-hint {
  overflow: hidden;
  color: #929dac;
  font-size: 10px !important;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.payment-cell :deep(.arco-tag) {
  justify-self: start;
}

.project-card-groups {
  display: grid;
  gap: 18px;
}

.project-card-group {
  min-width: 0;
}

.ledger-card-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.project-card-group > .project-table-group__head {
  margin-bottom: 10px;
  border: 1px solid #e5eaf2;
  border-radius: 7px;
}

.ledger-project-card {
  display: grid;
  gap: 14px;
  min-width: 0;
  min-height: 286px;
  padding: 16px;
  color: #718098;
  background: #fff;
  border: 1px solid #e3e9f1;
  border-radius: 9px;
  box-shadow: 0 4px 14px rgba(38, 65, 108, .04);
  cursor: pointer;
  text-align: left;
  font: inherit;
  transition: border-color .16s ease, box-shadow .16s ease, transform .16s ease;
}

.ledger-project-card:hover {
  border-color: #aec5f2;
  box-shadow: 0 10px 24px rgba(43, 78, 135, .09);
  transform: translateY(-1px);
}

.ledger-project-card > header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.ledger-project-card > header > div {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.ledger-project-card > header span {
  color: #93a0b2;
  font-size: 10px;
}

.ledger-project-card > header strong {
  overflow: hidden;
  color: #2f405d;
  font-size: 14px;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ledger-project-card dl {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 16px;
  margin: 0;
}

.ledger-project-card dl > div {
  min-width: 0;
}

.ledger-project-card dt,
.ledger-project-card dd {
  margin: 0;
}

.ledger-project-card dt {
  color: #9aa5b5;
  font-size: 10px;
}

.ledger-project-card dd {
  margin-top: 4px;
  overflow: hidden;
  color: #52627b;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ledger-project-card dd.warning {
  color: #b4761a;
}

.ledger-project-card__amount {
  display: grid;
  gap: 6px;
  padding: 11px 12px;
  background: #f7f9fc;
  border: 1px solid #e9edf3;
  border-radius: 7px;
}

.ledger-project-card__amount > span {
  color: #9aa5b5;
  font-size: 10px;
}

.ledger-project-card__amount :deep(.money-display--compact span) {
  white-space: normal;
}

.ledger-project-card > footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: auto;
  padding-top: 11px;
  border-top: 1px solid #edf1f5;
}

.ledger-project-card > footer span {
  color: #8996a8;
  font-size: 11px;
}

.ledger-project-card > footer span.paid {
  color: #2d8b61;
}

.ledger-project-card > footer em {
  color: #165dff;
  font-size: 11px;
  font-style: normal;
}

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

.detail-panel--dialog {
  max-height: calc(100vh - 180px);
  overflow: auto;
  display: grid;
  gap: var(--space-4);
  padding: var(--space-4);
  background: var(--color-gray-20);
  border: 0;
}

.project-management :deep(.project-detail-modal .arco-modal-body) {
  padding: 0;
  background: var(--color-gray-20);
}

.detail-panel--dialog .detail-head {
  align-items: flex-start;
  padding: var(--space-5);
  background: var(--bg-surface);
  border: 1px solid var(--color-brand-100);
  border-left: 4px solid var(--color-brand-500);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
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
}

.project-detail-brief article {
  display: grid;
  gap: 4px;
  min-height: 88px;
  align-content: center;
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
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
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
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

.business-flow-panel {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
}

.business-flow-list {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--space-2);
}

.business-flow-list button {
  position: relative;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  min-width: 0;
  min-height: 112px;
  padding: var(--space-3);
  color: var(--text-primary);
  text-align: left;
  background: color-mix(in srgb, var(--bg-surface) 84%, var(--color-brand-50));
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.business-flow-list button:hover,
.business-flow-list button:focus-visible {
  transform: translateY(-1px);
  border-color: var(--color-brand-300);
  box-shadow: var(--shadow-elevated);
  outline: none;
}

.business-flow-list i {
  width: 10px;
  height: 10px;
  margin-top: 4px;
  border-radius: 999px;
  background: var(--text-tertiary);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--text-tertiary) 12%, transparent);
}

.business-flow-list button[data-state='complete'] i {
  background: var(--color-success);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--color-success) 16%, transparent);
}

.business-flow-list button[data-state='active'] i {
  background: var(--color-brand-500);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--color-brand-500) 14%, transparent);
}

.business-flow-list button[data-state='warning'] i {
  background: var(--color-warning);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--color-warning) 16%, transparent);
}

.business-flow-list strong,
.business-flow-list span,
.business-flow-list em {
  display: block;
  min-width: 0;
}

.business-flow-list strong {
  font-size: var(--text-sm);
}

.business-flow-list span {
  margin-top: 5px;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  line-height: 1.6;
}

.business-flow-list em {
  grid-column: 2;
  align-self: end;
  margin-top: 8px;
  color: var(--color-brand-600);
  font-size: var(--text-xs);
  font-style: normal;
  font-weight: 600;
}

.next-action-panel {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
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
  background: var(--color-gray-20);
  border: 1px solid var(--border-color);
  border-left: 3px solid var(--color-brand-500);
  border-radius: var(--radius-sm);
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
  padding: var(--space-2);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

.detail-tabs button {
  flex: 0 0 auto;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--color-gray-20);
  color: var(--text-secondary);
  cursor: pointer;
  padding: 8px 12px;
}

.detail-tabs button.active {
  color: var(--color-brand-600);
  border-color: var(--color-brand-400);
  background: var(--color-brand-50);
}

.detail-section {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
}

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
  background: var(--color-gray-20);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
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
  padding: var(--space-4);
  background: var(--color-gray-20);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
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

.doc-card__tools {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-2);
}

.doc-stage-select {
  width: 132px;
}

.doc-required-toggle,
.icon-text-button {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-surface);
  color: var(--text-secondary);
  cursor: pointer;
  font-size: var(--text-xs);
  padding: 5px 8px;
}

.doc-required-toggle:hover,
.doc-required-toggle:focus-visible,
.icon-text-button:hover,
.icon-text-button:focus-visible {
  color: var(--color-brand-600);
  background: var(--color-brand-50);
  border-color: var(--color-brand-300);
  outline: none;
}

.doc-required-toggle:disabled {
  cursor: not-allowed;
  opacity: .55;
}

.doc-files {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 34px;
}

.file-pill {
  border: 1px solid var(--border-color);
  background: var(--bg-surface);
  border-radius: var(--radius-sm);
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
  border-radius: var(--radius-sm);
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

.project-form-modal :deep(.arco-modal-header) {
  height: 48px;
  border-bottom: 1px solid var(--border-color);
}

.project-form-modal :deep(.arco-modal-title) {
  color: var(--text-primary);
  font-size: var(--text-md);
  font-weight: 600;
}

.project-form-modal :deep(.arco-modal-body) {
  max-height: min(78vh, 820px);
  overflow: auto;
  padding: var(--space-4);
  background: var(--bg-surface);
}

.project-form-modal :deep(.arco-modal-footer) {
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--border-color);
}

.project-form-modal__titlebar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-width: 0;
  gap: var(--space-4);
}

.project-form-modal__titlebar > strong {
  min-width: 0;
  overflow: hidden;
  color: var(--text-primary);
  font-size: var(--text-md);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-form-modal__title-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: var(--space-2);
}

.project-form-modal__title-actions .arco-btn {
  min-height: 28px;
  padding: 3px 10px;
  font-size: var(--text-xs);
}

.arco-project-form :deep(.arco-form-item) {
  margin-bottom: 0;
}

.project-create-wizard {
  display: grid;
  gap: var(--space-4);
}

.project-create-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--space-4);
  height: min(70vh, 740px);
  min-height: 0;
  max-height: min(70vh, 740px);
  overflow: hidden;
}

.project-create-shell--preview-collapsed {
  grid-template-columns: minmax(0, 1fr) auto;
}

.project-create-shell__form,
.project-create-shell__preview {
  min-width: 0;
  min-height: 0;
  overflow: auto;
}

.project-create-shell__form {
  padding-right: 2px;
}

.project-create-shell__preview {
  display: grid;
  grid-template-rows: minmax(0, 1fr);
  overflow: hidden;
}

.wizard-stepper {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(116px, 1fr));
  gap: 8px;
  padding: 10px;
  background: #F7F8FA;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.wizard-stepper__item {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr);
  align-items: center;
  gap: 8px;
  min-height: 42px;
  padding: 8px 10px;
  color: var(--text-secondary);
  text-align: left;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
}

.wizard-stepper__item span {
  display: inline-grid;
  place-items: center;
  width: 24px;
  height: 24px;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-weight: 700;
  background: #fff;
  border: 1px solid var(--border-color);
  border-radius: 50%;
}

.wizard-stepper__item strong {
  overflow: hidden;
  font-size: var(--text-sm);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wizard-stepper__item.is-active {
  color: var(--color-primary);
  background: #fff;
  border-color: var(--color-primary);
  box-shadow: 0 6px 16px rgba(22, 93, 255, 0.08);
}

.wizard-stepper__item.is-active span,
.wizard-stepper__item.is-done span {
  color: #fff;
  background: var(--color-primary);
  border-color: var(--color-primary);
}

.wizard-panel {
  display: grid;
  gap: var(--space-4);
}

.wizard-panel__header {
  display: grid;
  gap: 6px;
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--border-color);
}

.wizard-panel__header h3 {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--text-lg);
  font-weight: 700;
}

.wizard-panel__header p {
  max-width: 780px;
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  line-height: 1.7;
}

.wizard-option-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}

.wizard-option-card,
.wizard-choice-card {
  display: grid;
  gap: 8px;
  min-height: 96px;
  padding: var(--space-3);
  color: var(--text-primary);
  text-align: left;
  background: #fff;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  cursor: pointer;
}

.wizard-option-card:hover,
.wizard-choice-card:hover,
.wizard-option-card.is-selected,
.wizard-choice-card.is-selected {
  border-color: var(--color-primary);
  box-shadow: 0 8px 20px rgba(22, 93, 255, 0.08);
}

.wizard-option-card.is-selected,
.wizard-choice-card.is-selected {
  background: #F2F6FF;
}

.wizard-option-card strong,
.wizard-choice-card strong {
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: 700;
}

.wizard-option-card em,
.wizard-choice-card span {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
  line-height: 1.6;
}

.wizard-choice-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.wizard-money-grid {
  padding-top: var(--space-2);
  border-top: 1px solid var(--border-color);
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.status-dot--green { background: #00A870; }
.status-dot--red { background: #E34D59; }
.status-dot--orange { background: #ED7B2F; }
.status-dot--gold { background: #D89614; }
.status-dot--purple { background: #722ED1; }
.status-dot--magenta { background: #C41D7F; }
.status-dot--arcoblue { background: var(--color-primary); }
.status-dot--gray { background: #8C8C8C; }

.material-directory-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}

.material-directory-card {
  display: grid;
  gap: 8px;
  min-height: 112px;
  padding: var(--space-3);
  background: #fff;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.material-directory-card span {
  width: fit-content;
  padding: 2px 8px;
  color: var(--color-primary);
  font-size: var(--text-xs);
  font-weight: 700;
  background: #F2F6FF;
  border-radius: 999px;
}

.material-directory-card strong {
  color: var(--text-primary);
  font-size: var(--text-sm);
}

.material-directory-card em {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
  line-height: 1.6;
}

.wizard-review {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

.wizard-review article {
  display: grid;
  gap: var(--space-2);
  padding: var(--space-3);
  background: #fff;
  border: 1px solid var(--border-color);
  border-radius: 8px;
}

.wizard-review h4 {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: 700;
}

.wizard-review dl {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
  gap: 8px 12px;
  margin: 0;
}

.wizard-review dt,
.wizard-review dd {
  margin: 0;
  font-size: var(--text-xs);
  line-height: 1.6;
}

.wizard-review dt {
  color: var(--text-tertiary);
}

.wizard-review dd {
  color: var(--text-primary);
}

.review-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.wizard-footer-extra {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 32px;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.file-upload-form {
  display: grid;
  gap: var(--space-3);
}

.file-upload-form :deep(.arco-form-item) {
  margin-bottom: 0;
}

.file-upload-form :deep(.arco-select-view-single),
.file-upload-form :deep(.arco-input-wrapper) {
  width: 100%;
}

.inline-preview-shell,
.upload-preview-card {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--color-brand-100);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
}

.inline-preview-shell__head,
.upload-preview-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.inline-preview-shell__head strong,
.upload-preview-card__head strong {
  display: block;
  overflow-wrap: anywhere;
  color: var(--text-primary);
  font-size: var(--text-sm);
}

.upload-preview-card__head span {
  display: block;
  margin-top: 3px;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.upload-preview-card__head button {
  flex: 0 0 auto;
  border: 0;
  background: transparent;
  color: var(--color-danger);
  cursor: pointer;
  font-size: var(--text-xs);
}

.inline-preview-frame,
.upload-preview-window {
  overflow: hidden;
  display: grid;
  place-items: center;
  min-height: 280px;
  background: var(--color-gray-20);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

.upload-preview-window {
  min-height: 180px;
}

.inline-preview-frame iframe,
.upload-preview-window iframe {
  width: 100%;
  height: min(58vh, 620px);
  border: 0;
  background: #fff;
}

.upload-preview-window iframe {
  height: 220px;
}

.inline-preview-frame img,
.upload-preview-window img {
  display: block;
  max-width: 100%;
  max-height: 58vh;
  object-fit: contain;
}

.inline-preview-frame pre,
.upload-preview-window pre {
  width: 100%;
  max-height: 58vh;
  margin: 0;
  overflow: auto;
  padding: var(--space-4);
  color: var(--text-primary);
  background: #fff;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  white-space: pre-wrap;
}

.preview-unavailable,
.upload-preview-window > div {
  display: grid;
  gap: 6px;
  justify-items: center;
  padding: var(--space-5);
  color: var(--text-secondary);
  text-align: center;
}

.preview-unavailable strong,
.upload-preview-window strong {
  color: var(--text-primary);
  font-size: var(--text-sm);
}

.preview-unavailable span,
.upload-preview-window span {
  font-size: var(--text-xs);
}

.upload-progress {
  position: relative;
  overflow: hidden;
  height: 26px;
  background: var(--color-gray-100);
  border-radius: var(--radius-sm);
}

.upload-progress span {
  display: block;
  height: 100%;
  background: var(--color-brand-500);
  transition: width var(--duration-normal) var(--ease-out);
}

.upload-progress em {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: var(--text-primary);
  font-size: var(--text-xs);
  font-style: normal;
  font-weight: 600;
}

.modal-business-form :deep(.arco-form-item) {
  margin-bottom: 0;
}

.modal-business-form :deep(.arco-select-view-single),
.modal-business-form :deep(.arco-input-wrapper),
.modal-business-form :deep(.arco-input-number),
.modal-business-form :deep(.arco-textarea-wrapper) {
  width: 100%;
}

.arco-project-form :deep(.arco-form-item-label) {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-weight: 600;
}

.arco-project-form :deep(.arco-input-wrapper),
.arco-project-form :deep(.arco-select-view-single),
.arco-project-form :deep(.arco-input-number),
.arco-project-form :deep(.arco-picker),
.arco-project-form :deep(.arco-textarea-wrapper),
.filter-view-form :deep(.arco-input-wrapper) {
  width: 100%;
  background: #fff;
  border-color: var(--border-strong);
}

.arco-project-form :deep(.arco-input-wrapper),
.arco-project-form :deep(.arco-select-view-single),
.arco-project-form :deep(.arco-input-number),
.arco-project-form :deep(.arco-picker) {
  min-height: 34px;
}

.arco-project-form :deep(.arco-input-wrapper.arco-input-disabled),
.arco-project-form :deep(.arco-input-wrapper:has(input[readonly])) {
  background: var(--bg-muted);
  color: var(--text-secondary);
}

:global(.arco-select-dropdown) {
  max-height: min(320px, 42vh);
}

:global(.arco-select-dropdown .arco-scrollbar),
:global(.arco-select-dropdown .arco-scrollbar-container) {
  max-height: min(300px, 40vh);
}

.arco-project-form :deep(.arco-form-item-error .arco-input-wrapper),
.arco-project-form :deep(.arco-form-item-error .arco-input-number),
.arco-project-form :deep(.arco-form-item-error .arco-picker) {
  border-color: var(--color-danger);
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

@media (max-width: 1080px) {
  .exception-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .ledger-card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .work-queue-row { grid-template-columns: 62px minmax(220px, 1fr) 100px 78px; }
  .work-queue-row > time { display: none; }
  .summary-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .project-dashboard { grid-template-columns: 1fr; }
  .project-dashboard--secondary {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .project-work-items--secondary {
    display: flex;
    min-height: 52px;
  }
  .project-work-items--secondary .project-work-items__head {
    flex: 1 1 auto;
  }
  .project-work-items--secondary .project-work-list {
    flex: 0 0 220px;
  }
  .project-work-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .project-work-items--secondary .project-work-list {
    grid-template-columns: minmax(0, 1fr);
  }
  .business-flow-list { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .toolbar:not(.view-toolbar--ledger) { grid-template-columns: 1fr 1fr 1fr 1fr; }
  .ledger-command-row { grid-template-columns: minmax(280px, 1fr) 104px 152px 78px; }
  .ledger-view-actions { gap: 10px; }
  .workspace { grid-template-columns: 1fr; }
  .detail-panel { position: static; }
}

@media (max-width: 1280px) {
  .ledger-command-row { grid-template-columns: minmax(280px, 1fr) 104px 152px 78px; }
}

@media (max-width: 960px) {
  .project-create-shell,
  .project-create-shell--preview-collapsed {
    grid-template-columns: minmax(0, 1fr);
  }

  .project-create-shell__preview {
    overflow: visible;
  }
}

@media (max-width: 760px) {
  .project-management { padding: 12px; }
  .project-form-modal :deep(.arco-modal-header) {
    height: auto;
    min-height: 48px;
  }
  .project-form-modal__titlebar {
    align-items: flex-start;
    flex-wrap: wrap;
  }
  .project-form-modal__title-actions {
    width: 100%;
    justify-content: flex-end;
  }
  .exception-grid { grid-template-columns: 1fr; }
  .ledger-card-grid { grid-template-columns: 1fr; }
  .panel-head__side { align-items: stretch; flex-direction: column; }
  .ledger-layout-switch { width: 100%; }
  .ledger-layout-switch button { flex: 1; }
  .work-queue-row { grid-template-columns: 58px minmax(0, 1fr) 70px; }
  .work-queue-row > span:not(.work-queue-row__level) { display: none; }
  .lifecycle-board { grid-template-columns: repeat(5, 220px); }
  .summary-grid,
  .document-grid,
  .detail-metrics,
  .project-detail-brief,
  .project-timeline,
  .next-action-list,
  .business-flow-list,
  .info-grid,
  .wizard-stepper,
  .wizard-option-grid,
  .wizard-choice-row,
  .material-directory-grid,
  .wizard-review,
  .dialog-grid { grid-template-columns: 1fr; }
  .wizard-stepper__item {
    min-height: 38px;
  }
  .project-empty-onboarding {
    align-items: stretch;
    flex-direction: column;
  }
  .dialog-span-2,
  .dialog-hint { grid-column: span 1; }
  .toolbar:not(.view-toolbar--ledger) {
    grid-template-columns: 1fr;
  }
  .ledger-command-row {
    grid-template-columns: 100px minmax(120px, 1fr) 80px;
  }
  .ledger-command-row > .project-keyword-input {
    grid-column: 1 / -1;
  }
  .ledger-advanced-filters {
    grid-template-columns: 1fr;
  }
  .ledger-clear-filters {
    justify-self: start;
  }
  .view-toolbar__filters,
  .view-toolbar__utilities {
    align-items: stretch;
    flex-direction: column;
  }
  .view-toolbar__filters > .project-keyword-input,
  .view-toolbar__filters > .arco-select-view,
  .view-toolbar__filters > .arco-input-wrapper,
  .view-toolbar__filters > .arco-btn,
  .view-toolbar__filters :deep(.arco-select-view),
  .view-toolbar__filters :deep(.arco-input-wrapper) {
    flex: 0 0 auto;
    width: 100%;
  }
  .view-toolbar__utilities .saved-views,
  .view-toolbar__utilities .custom-views,
  .view-toolbar__utilities .table-tools,
  .view-toolbar__utilities .ledger-view-actions {
    width: 100%;
  }
  .view-toolbar--ledger .view-toolbar__utilities {
    padding: 8px 12px;
  }
  .view-toolbar--ledger .saved-views {
    justify-content: space-between;
  }
  .ledger-view-actions {
    justify-content: space-between;
    margin-left: 0;
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

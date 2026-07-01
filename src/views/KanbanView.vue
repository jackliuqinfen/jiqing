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
            @click="requestViewMode(item.value)"
          >
            <t-icon :name="item.icon" />
            <span>{{ item.label }}</span>
          </button>
        </div>
        <t-button v-if="authStore.isAdmin && viewMode === 'table'" variant="outline" size="small" @click="openTableSettings">
          <template #icon><t-icon name="setting" /></template>
          表格设置
        </t-button>
        <t-button
          v-if="authStore.isAdmin && viewMode === 'table' && tableSettingsDirty"
          theme="primary"
          size="small"
          :loading="tableSettingsSaving"
          @click="requestSaveTableSettings()"
        >
          保存表格设置
        </t-button>
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
      <section
        v-if="workItems.length"
        ref="workItemStripRef"
        class="work-item-strip"
        :class="{ 'work-item-strip--focus': workItemStripFocused }"
        aria-label="待办与异常"
      >
        <div class="work-item-strip__head">
          <strong>待办与异常</strong>
          <span>{{ workItems.length }} 项需关注</span>
        </div>
        <button
          v-for="item in workItems.slice(0, 4)"
          :key="item.id"
          type="button"
          class="work-item-card"
          :data-level="item.level"
          @click="openWorkItem(item)"
        >
          <span>{{ item.type }}</span>
          <strong>{{ item.projectName }}</strong>
          <em>{{ item.description }}</em>
        </button>
      </section>

      <section class="summary-grid">
        <button
          v-for="card in summaryCards"
          :key="card.label"
          type="button"
          class="summary-card"
          :class="{ 'summary-card--active': activeSummaryCard === card.key }"
          @click="applySummaryCard(card)"
        >
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <em>{{ card.hint }}</em>
        </button>
      </section>

      <section class="toolbar">
        <input ref="auditKeywordInputRef" v-model="store.filters.keyword" class="native-input keyword" placeholder="搜索项目、楼栋、结算编号" @keyup.enter="store.refreshProjects" />
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

      <section v-if="activeFilterChips.length" class="active-filter-strip" aria-label="已应用筛选">
        <span>已应用筛选</span>
        <button v-for="chip in activeFilterChips" :key="chip.key" type="button" @click="clearActiveFilterChip(chip.key)">
          {{ chip.label }}：{{ chip.value }}
          <b aria-hidden="true">×</b>
        </button>
        <button type="button" class="active-filter-strip__clear" @click="resetFilters">清除全部</button>
      </section>

      <t-alert v-if="store.error" theme="error" :close="false" class="error-alert">
        <template #message>
          <div class="recoverable-alert">
            <div>
              <strong>审计数据加载失败</strong>
              <span>{{ auditErrorMessage }}</span>
            </div>
            <t-button size="small" variant="outline" :loading="store.loading" @click="retryAuditLoad">重新加载</t-button>
          </div>
        </template>
      </t-alert>

      <div v-if="store.loading && store.projects.length === 0" class="center-state">
        <t-loading size="large" text="正在加载审计项目..." />
      </div>

      <section v-else-if="viewMode === 'kanban'" class="kanban-board">
        <div v-for="stage in store.meta.stages" :key="stage.code" class="kanban-column">
          <div class="column-head" :style="{ borderTopColor: stage.color }">
            <div>
              <h2>{{ stage.title }}</h2>
              <span>按阶段推进</span>
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

      <section v-else-if="layoutMode !== 'vertical'" class="stage-table-view" aria-label="审计阶段横向表格">
        <article v-for="stage in store.meta.stages" :key="stage.code" class="stage-table-card">
          <div class="stage-table-rail" :style="{ '--stage-color': stage.color }">
            <span class="stage-table-rail__line" />
            <span class="stage-table-rail__text">{{ stage.title }}</span>
            <span class="stage-table-rail__count">{{ stageCount(stage.code) }}</span>
          </div>
          <div class="stage-table-panel">
            <div class="stage-table-head">
              <div>
                <h2>{{ stage.title }}</h2>
                <p>本阶段字段按业务配置展示</p>
              </div>
              <strong>{{ stageCount(stage.code) }} 项</strong>
            </div>
            <div class="stage-table-scroll">
              <table>
                <colgroup>
                  <col style="width: 260px; min-width: 220px" />
                  <col v-for="field in stageTableFields(stage.code)" :key="field.id" :style="{ width: fieldColumnWidth(field) }" />
                  <col style="width: 84px" />
                </colgroup>
                <thead>
                  <tr>
                    <th>项目</th>
                    <th
                      v-for="field in stageTableFields(stage.code)"
                      :key="field.id"
                      class="resizable-th"
                      :style="{ width: fieldColumnWidth(field), minWidth: fieldColumnWidth(field) }"
                    >
                      <span>{{ field.fieldLabel }}</span>
                      <button
                        v-if="authStore.isAdmin"
                        class="column-resize-handle"
                        type="button"
                        aria-label="调整列宽"
                        title="拖拽调整列宽"
                        @mousedown.prevent="startColumnResize($event, field)"
                      />
                    </th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="project in store.projectsByStage[stage.code]" :key="project.id">
                    <td class="stage-table-project">
                      <button class="project-link" type="button" @click="openDetail(project)">
                        <strong>{{ project.projectName }}</strong>
                        <span>{{ project.projectCode }} · {{ project.contractor.name }}</span>
                      </button>
                    </td>
                    <td v-for="field in stageTableFields(stage.code)" :key="field.id" :style="{ width: fieldColumnWidth(field), minWidth: fieldColumnWidth(field) }">
                      {{ displayField(project, field) }}
                    </td>
                    <td><button class="link-button" @click="openDetail(project)">查看</button></td>
                  </tr>
                  <tr v-if="stageCount(stage.code) === 0">
                    <td :colspan="stageTableFields(stage.code).length + 2" class="stage-table-empty">该阶段暂无项目</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </article>
      </section>

      <section v-else class="stage-card-view" aria-label="审计阶段纵向卡片">
        <article v-for="stage in store.meta.stages" :key="stage.code" class="stage-card-section" :style="{ '--stage-color': stage.color }">
          <div class="stage-card-section__head">
            <div>
              <span class="stage-dot" />
              <h2>{{ stage.title }}</h2>
              <p>按项目阅读字段重点，适合走查、汇报和移动浏览。</p>
            </div>
            <strong>{{ stageCount(stage.code) }} 项</strong>
          </div>
          <div class="audit-project-card-grid">
            <button
              v-for="project in store.projectsByStage[stage.code]"
              :key="project.id"
              type="button"
              class="audit-project-card"
              @click="openDetail(project)"
            >
              <div class="audit-project-card__title">
                <div>
                  <strong>{{ project.projectName }}</strong>
                  <span>{{ project.projectCode }} · {{ project.contractor.name || project.auditedUnit }}</span>
                </div>
                <em :class="{ overdue: isOverdue(project) }">{{ isOverdue(project) ? '已逾期' : statusTitle(project.status) }}</em>
              </div>
              <div class="audit-card-keyline">
                <span>负责人</span>
                <strong>{{ project.managerName || '-' }}</strong>
                <span>计划完成</span>
                <strong>{{ project.deadline.auditDeadline || '未设期限' }}</strong>
                <span>送审金额</span>
                <strong>{{ money(project.amount.submittedAmount) }}</strong>
              </div>
              <dl class="audit-card-fields">
                <template v-for="field in stageTableFields(stage.code).slice(0, 6)" :key="field.id">
                  <dt>{{ field.fieldLabel }}</dt>
                  <dd>{{ displayField(project, field) }}</dd>
                </template>
              </dl>
              <div class="audit-project-card__footer">
                <span>{{ project.docStatus || '资料状态待确认' }}</span>
                <em>查看详情</em>
              </div>
            </button>
            <div v-if="stageCount(stage.code) === 0" class="stage-card-empty">该阶段暂无项目</div>
          </div>
        </article>
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

      <section v-if="detailVisible" ref="detailSectionRef" class="audit-detail-workspace" aria-label="审计项目详情">
      <div class="audit-detail-panel">
        <div class="audit-detail-head">
          <div>
            <h2>{{ editing ? '编辑项目' : '审计详情' }}</h2>
            <p>{{ editing ? '按字段配置生成表单' : '项目详情与进度流转' }}</p>
          </div>
          <button class="icon-button" title="收起详情" @click="closeDrawer"><t-icon name="close" /></button>
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
          <div class="audit-detail-hero">
            <div>
              <span class="stage-pill">{{ stageTitle(store.selectedProject.stage) }}</span>
              <h3>{{ store.selectedProject.projectName }}</h3>
              <p>{{ store.selectedProject.projectCode }} · {{ store.selectedProject.auditedUnit || store.selectedProject.contractor.name || '未填写被审计单位' }}</p>
            </div>
            <div class="audit-detail-actions">
              <t-button v-if="store.selectedProject.projectId" size="small" variant="outline" theme="default" @click="goProject(store.selectedProject.projectId)">
                <template #icon><t-icon name="task" /></template>
                项目台账
              </t-button>
              <t-button size="small" theme="primary" variant="outline" @click="startEdit(store.selectedProject)">编辑审计信息</t-button>
            </div>
          </div>
          <div class="audit-detail-kpis">
            <article>
              <span>当前负责人</span>
              <strong>{{ store.selectedProject.managerName || store.selectedProject.contractor.name || '-' }}</strong>
            </article>
            <article>
              <span>计划完成</span>
              <strong :class="{ overdue: isOverdue(store.selectedProject) }">{{ store.selectedProject.deadline.auditDeadline || '未设期限' }}</strong>
            </article>
            <article>
              <span>送审金额</span>
              <strong>{{ money(store.selectedProject.amount.submittedAmount) }}</strong>
            </article>
            <article>
              <span>资料状态</span>
              <strong>{{ store.selectedProject.docStatus || '待确认' }}</strong>
            </article>
          </div>
          <div class="next-action-panel">
            <div class="section-title-row">
              <h3>下一步建议</h3>
              <span>根据阶段、期限和资料状态生成</span>
            </div>
            <div class="next-action-list">
              <button v-for="item in auditActionHints" :key="item.label" type="button" :data-level="item.level" @click="item.action">
                <span>{{ item.label }}</span>
                <strong>{{ item.title }}</strong>
                <em>{{ item.description }}</em>
              </button>
            </div>
          </div>
          <dl class="detail-grid">
            <template v-for="field in store.detailFields" :key="field.id">
              <dt>{{ field.fieldLabel }}</dt>
              <dd>{{ displayField(store.selectedProject, field) }}</dd>
            </template>
          </dl>
          <div class="progress-box">
            <h3>进度流转</h3>
            <p>点击阶段可更新当前审计进度，系统会保留阶段记录。</p>
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
            <div class="audit-timeline">
              <article v-for="stage in store.selectedProject.stages || []" :key="stage.id">
                <span />
                <div>
                  <strong>{{ stageTitle(stage.stage_code || stage.stage_name) }}</strong>
                  <p>{{ statusTitle(stage.status) }} · {{ stage.handler_name || stage.owner || '-' }} · {{ formatDateTime(stage.entered_at) }}</p>
                </div>
              </article>
              <div v-if="(store.selectedProject.stages || []).length === 0" class="detail-empty-action">
                <strong>还没有阶段流转记录</strong>
                <span>更新当前阶段后，系统会在这里保留处理人、时间和阶段状态。</span>
              </div>
            </div>
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
            <div v-else class="detail-empty-action">
              <strong>当前审计项目还没有附件</strong>
              <span>上传报审资料、结论附件或补充说明，方便审计过程留痕。</span>
              <t-button v-if="authStore.isEditor" size="small" theme="primary" @click="triggerAttachmentSelect">上传附件</t-button>
            </div>
          </div>
          <div class="log-box">
            <h3>操作日志</h3>
            <p v-for="log in store.selectedProject.logs || []" :key="log.id">{{ formatDateTime(log.created_at) }} · {{ log.operator || '系统' }} · {{ auditLogText(log.note || log.action) }}</p>
            <div v-if="(store.selectedProject.logs || []).length === 0" class="detail-empty-action">
              <strong>暂无操作记录</strong>
              <span>编辑项目信息、上传附件或更新阶段后，会自动形成操作记录。</span>
            </div>
          </div>
        </div>
      </div>
      </section>
    </main>

    <aside v-if="tableSettingsVisible" class="drawer">
      <div class="drawer-panel table-settings-panel">
        <div class="drawer-head">
          <div>
            <h2>表格设置</h2>
            <p>调整审计看板表格字段、顺序与列宽，保存后会影响当前看板展示。</p>
          </div>
          <button class="icon-button" @click="closeTableSettings"><t-icon name="close" /></button>
        </div>

        <div class="table-settings-body">
          <div class="table-settings-help">
            <strong>仅管理员可配置</strong>
            <span>字段名称、显示状态、阶段归属、排序和列宽会保存为审计看板的表格展示规则。</span>
          </div>
          <div class="table-settings-table">
            <table>
              <thead>
                <tr>
                  <th>显示</th>
                  <th>字段名称</th>
                  <th>所属阶段</th>
                  <th>排序</th>
                  <th>列宽</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="field in tableSettingsDraft" :key="field.id">
                  <td>
                    <input v-model="field.visibleInTable" type="checkbox" @change="markTableSettingsDirty" />
                  </td>
                  <td>
                    <input v-model.trim="field.fieldLabel" class="native-input" placeholder="请输入业务字段名称" @input="markTableSettingsDirty" />
                    <span class="field-key-hint">{{ field.fieldKey }}</span>
                  </td>
                  <td>
                    <select v-model="field.stageKey" class="native-select" @change="markTableSettingsDirty">
                      <option value="">全部阶段</option>
                      <option v-for="stage in store.meta.stages" :key="stage.code" :value="stage.code">{{ stage.title }}</option>
                    </select>
                  </td>
                  <td>
                    <input v-model.number="field.sortOrder" class="native-input compact-number" type="number" min="0" @input="markTableSettingsDirty" />
                  </td>
                  <td>
                    <input
                      v-model.number="field.tableWidth"
                      class="native-input compact-number"
                      type="number"
                      :min="field.fieldKey === 'project_name' ? 220 : 96"
                      @input="updateDraftWidth(field)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="drawer-actions table-settings-actions">
          <span v-if="tableSettingsDirty" class="dirty-hint">有未保存的表格设置</span>
          <t-button variant="outline" @click="discardTableSettings">放弃更改</t-button>
          <t-button theme="primary" :loading="tableSettingsSaving" @click="requestSaveTableSettings()">保存设置</t-button>
        </div>
      </div>
    </aside>

    <div v-if="confirmState.visible" class="confirm-mask">
      <div class="confirm-panel">
        <h3>{{ confirmState.title }}</h3>
        <p>{{ confirmState.message }}</p>
        <div class="confirm-actions">
          <button v-if="confirmState.thirdText" type="button" class="ghost-button" @click="confirmThirdAction">{{ confirmState.thirdText }}</button>
          <button type="button" class="ghost-button" @click="confirmCancelAction">{{ confirmState.cancelText }}</button>
          <button type="button" class="primary-button" :disabled="tableSettingsSaving" @click="confirmPrimaryAction">{{ confirmState.confirmText }}</button>
        </div>
      </div>
    </div>

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
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import { MessagePlugin } from '@/ui/message'
import { fetchAttachmentDownloadBlob, fetchAttachmentPreviewBlob, saveFieldConfig } from '@/api/audit'
import { fetchWorkItems } from '@/api/projects'
import { useAuditStore } from '@/store/audit'
import { useAuthStore } from '@/store/auth'
import { friendlyErrorMessage } from '@/utils/errors'
import type { WorkItem } from '@/types'
import type { AuditFieldConfig, AuditFilters, AuditLayoutMode, AuditProject, AuditProjectAttachment, AuditStageCode, AuditViewMode } from '@/types/audit'

type AuditSummaryCard = {
  key: string
  label: string
  value: string | number
  hint: string
  filters: Partial<AuditFilters>
}
type AuditFilterChip = {
  key: string
  label: string
  value: string
}

const router = useRouter()
const route = useRoute()
const store = useAuditStore()
const authStore = useAuthStore()
defineProps<{ embedded?: boolean }>()
const viewMode = ref<AuditViewMode>('kanban')
const layoutMode = ref<AuditLayoutMode>('horizontal')
const activeSummaryCard = ref('')
const detailVisible = ref(false)
const editing = ref(false)
const editingId = ref('')
const formValues = reactive<Record<string, string>>({})
const customOptionValues = reactive<Record<string, string>>({})
const attachmentInputRef = ref<HTMLInputElement | null>(null)
const auditKeywordInputRef = ref<HTMLInputElement | null>(null)
const detailSectionRef = ref<HTMLElement | null>(null)
const workItemStripRef = ref<HTMLElement | null>(null)
const attachmentUploading = ref(false)
const workItems = ref<WorkItem[]>([])
const workItemStripFocused = ref(false)
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
type TableFieldDraft = AuditFieldConfig & { tableWidth: number }
const tableSettingsVisible = ref(false)
const tableSettingsDirty = ref(false)
const tableSettingsSaving = ref(false)
const tableSettingsDraft = ref<TableFieldDraft[]>([])
const tableWidthOverrides = reactive<Record<string, number>>({})
const allowNextRouteLeave = ref(false)
const pendingLeaveAction = ref<null | (() => void | Promise<void>)>(null)
const resizingColumn = ref<null | { id: string; startX: number; startWidth: number; minWidth: number }>(null)
const confirmState = reactive({
  visible: false,
  title: '',
  message: '',
  confirmText: '确定',
  cancelText: '取消',
  thirdText: '',
  onConfirm: null as null | (() => void | Promise<void>),
  onCancel: null as null | (() => void | Promise<void>),
  onThird: null as null | (() => void | Promise<void>),
})

const viewModes: { value: AuditViewMode; label: string; icon: string }[] = [
  { value: 'kanban', label: '看板', icon: 'view-column' },
  { value: 'gantt', label: '甘特', icon: 'chart' },
  { value: 'table', label: '表格', icon: 'view-list' },
]

const options = computed(() => store.meta.options)
const activeFilterChips = computed<AuditFilterChip[]>(() => {
  const chips: AuditFilterChip[] = []
  const filters = store.filters
  if (filters.keyword) chips.push({ key: 'keyword', label: '关键词', value: filters.keyword })
  if (filters.stage) chips.push({ key: 'stage', label: '审计阶段', value: stageTitle(filters.stage) })
  if (filters.priority) chips.push({ key: 'priority', label: '优先级', value: optionLabel('priority', filters.priority) })
  if (filters.category) chips.push({ key: 'category', label: '项目分类', value: optionLabel('category', filters.category) })
  if (filters.status) chips.push({ key: 'status', label: '项目状态', value: statusTitle(filters.status) })
  if (filters.owner) chips.push({ key: 'owner', label: '负责人', value: filters.owner })
  if (filters.startDate) chips.push({ key: 'startDate', label: '开始日期', value: filters.startDate })
  if (filters.endDate) chips.push({ key: 'endDate', label: '结束日期', value: filters.endDate })
  if (filters.onlyOverdue) chips.push({ key: 'onlyOverdue', label: '期限状态', value: '仅看超期' })
  if (filters.onlyUpcomingDue) chips.push({ key: 'onlyUpcomingDue', label: '计划时间', value: '7 天内到期' })
  if (filters.onlyMonthlyNew) chips.push({ key: 'onlyMonthlyNew', label: '创建时间', value: '本月新增' })
  if (filters.sort && filters.sort !== 'stage') chips.push({ key: 'sort', label: '排序', value: sortTitle(filters.sort) })
  return chips
})
const auditErrorMessage = computed(() => friendlyErrorMessage(store.error, '审计数据加载失败，请稍后重试或联系管理员'))
const visibleCardFields = computed(() => store.cardFields.filter((field) => !['project_name', 'current_stage'].includes(field.fieldKey)).slice(0, 5))
const totalPages = computed(() => Math.max(1, Math.ceil(store.total / store.filters.pageSize)))
const auditActionHints = computed(() => {
  const project = store.selectedProject
  if (!project) return []
  const items: Array<{ label: string; title: string; description: string; level: string; action: () => void }> = []
  if (isOverdue(project)) {
    items.push({
      label: '期限风险',
      title: '当前审计已逾期',
      description: '建议优先核对责任人、截止时间和当前阶段处理情况。',
      level: 'danger',
      action: () => {
        store.filters.onlyOverdue = true
        store.filters.page = 1
        store.refreshProjects()
      },
    })
  }
  if (!project.docStatus || project.docStatus.includes('缺') || project.docStatus.includes('补') || project.docStatus.includes('更正')) {
    items.push({
      label: '资料状态',
      title: project.docStatus || '资料状态待确认',
      description: '优先确认资料完整性，避免阶段流转被退回。',
      level: 'warning',
      action: () => triggerAttachmentSelect(),
    })
  }
  if (project.projectId) {
    items.push({
      label: '项目主档案',
      title: '回到项目台账',
      description: '查看合同资料、结算资料、变更签证和项目操作记录。',
      level: 'primary',
      action: () => goProject(project.projectId),
    })
  }
  if (!items.length) {
    items.push({
      label: '审计推进',
      title: '当前阶段可正常推进',
      description: '可根据业务进展更新阶段，系统会保留阶段记录。',
      level: 'success',
      action: () => {},
    })
  }
  return items.slice(0, 3)
})
const summaryCards = computed<AuditSummaryCard[]>(() => [
  { key: 'all', label: '总项目', value: store.summary.totalProjects, hint: '当前项目合计', filters: {} },
  { key: 'active', label: '在审项目', value: store.summary.inAuditProjects, hint: '一审 + 二审', filters: { status: 'active' } },
  { key: 'completed', label: '已完成', value: store.summary.completedProjects, hint: '已完成/归档', filters: { stage: 'archived' } },
  { key: 'overdue', label: '超期督办', value: store.summary.overdueProjects, hint: '未归档且过期', filters: { onlyOverdue: true, sort: 'plannedEndDate' } },
  { key: 'monthly', label: '本月新增', value: store.summary.monthlyNewProjects, hint: '按创建时间统计', filters: { onlyMonthlyNew: true, sort: 'updatedAt' } },
  { key: 'upcoming', label: '即将到期', value: store.summary.upcomingDueProjects, hint: '7 天内计划完成', filters: { onlyUpcomingDue: true, sort: 'plannedEndDate' } },
  { key: 'amount', label: '送审金额', value: money(store.summary.totalSubmittedAmount), hint: '全部项目合计', filters: { sort: 'amount' } },
])

onMounted(async () => {
  applyRouteFilters()
  await store.refreshAll()
  try {
    workItems.value = await fetchWorkItems(20)
  } catch {
    workItems.value = []
  }
  await focusWorkItemsFromRoute()
  window.addEventListener('beforeunload', handleBeforeUnload)
  window.addEventListener('keydown', handleAuditKeyboard)
  await openAuditProjectFromRoute()
})

async function openAuditProjectFromRoute() {
  const projectId = String(route.query.projectId || '').trim()
  if (!projectId) return false
  const target = store.projects.find((item) => item.id === projectId) || null
  if (target) {
    await openDetail(target)
    return true
  }
  try {
    await store.selectProject({ id: projectId } as AuditProject)
    detailVisible.value = true
    editing.value = false
    await nextTick()
    detailSectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    return true
  } catch {
    store.selectedProject = null
    detailVisible.value = false
    editing.value = false
    MessagePlugin.warning('已进入审计看板，但未找到对应项目，请先确认项目是否已同步到审计模块')
    return false
  }
}

async function focusWorkItemsFromRoute() {
  if (String(route.query.focus || '') !== 'work-items') return
  await nextTick()
  if (!workItemStripRef.value) {
    if (!workItems.value.length) MessagePlugin.success('当前没有需要优先处理的待办事项')
    return
  }
  workItemStripFocused.value = true
  workItemStripRef.value.scrollIntoView({ behavior: 'smooth', block: 'start' })
  window.setTimeout(() => {
    workItemStripFocused.value = false
  }, 1800)
}

async function retryAuditLoad() {
  try {
    await store.refreshAll()
    try {
      workItems.value = await fetchWorkItems(20)
    } catch {
      workItems.value = []
    }
    await focusWorkItemsFromRoute()
    await openAuditProjectFromRoute()
    MessagePlugin.success('审计数据已更新')
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '审计数据加载失败，请稍后重试或联系管理员'))
  }
}

function applyRouteFilters() {
  const query = route.query
  const stage = String(query.stage || '').trim()
  const status = String(query.status || '').trim()
  const sort = String(query.sort || '').trim()
  const owner = String(query.owner || '').trim()
  const onlyOverdue = String(query.onlyOverdue || '').trim()
  const onlyUpcomingDue = String(query.onlyUpcomingDue || '').trim()
  const onlyMonthlyNew = String(query.onlyMonthlyNew || '').trim()

  if (stage) store.filters.stage = stage
  if (status) store.filters.status = status
  if (sort) store.filters.sort = sort
  if (owner) store.filters.owner = owner
  if (onlyOverdue === '1' || onlyOverdue === 'true') store.filters.onlyOverdue = true
  if (onlyUpcomingDue === '1' || onlyUpcomingDue === 'true') store.filters.onlyUpcomingDue = true
  if (onlyMonthlyNew === '1' || onlyMonthlyNew === 'true') store.filters.onlyMonthlyNew = true
  if (store.filters.onlyOverdue) activeSummaryCard.value = 'overdue'
  else if (store.filters.onlyUpcomingDue) activeSummaryCard.value = 'upcoming'
  else if (store.filters.onlyMonthlyNew) activeSummaryCard.value = 'monthly'
  else if (store.filters.stage === 'archived') activeSummaryCard.value = 'completed'
  else if (store.filters.status === 'active') activeSummaryCard.value = 'active'
  else if (store.filters.sort === 'amount') activeSummaryCard.value = 'amount'
  store.filters.page = 1
}

watch(
  () => route.query.projectId,
  async (projectId, previousProjectId) => {
    if (!projectId || projectId === previousProjectId) return
    await openAuditProjectFromRoute()
  },
)

watch(
  () => route.query.focus,
  async (focus, previousFocus) => {
    if (focus !== 'work-items' || focus === previousFocus) return
    await focusWorkItemsFromRoute()
  },
)

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload)
  window.removeEventListener('keydown', handleAuditKeyboard)
  removeColumnResizeListeners()
})

onBeforeRouteLeave((to) => {
  if (allowNextRouteLeave.value) {
    allowNextRouteLeave.value = false
    return true
  }
  if (!tableSettingsDirty.value) return true
  pendingLeaveAction.value = async () => {
    allowNextRouteLeave.value = true
    await router.push(to.fullPath)
  }
  showUnsavedTableSettingsPrompt()
  return false
})

function money(value: number) {
  if (!value) return '0'
  if (value >= 100000000) return `${(value / 100000000).toFixed(2)} 亿`
  if (value >= 10000) return `${(value / 10000).toFixed(1)} 万`
  return value.toLocaleString('zh-CN')
}

function formatDateTime(value: string) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function auditLogText(value: string) {
  if (!value) return '记录已更新'
  if (value.includes('数据库') || value.includes('初始化') || value.includes('seed')) return '系统已导入初始项目记录'
  if (value === 'create') return '新建审计项目'
  if (value === 'update') return '更新项目信息'
  if (value === 'move') return '更新审计阶段'
  return value
}

function displayField(project: AuditProject, field: AuditFieldConfig) {
  const value = store.readField(project, field)
  if (field.fieldType === 'number') return money(Number(value))
  if (typeof value === 'boolean') return value ? '是' : '否'
  if (value === null || value === undefined || value === '') return '-'
  return optionValueTitle(field, value)
}

function stageTitle(code: string) {
  return store.meta.stages.find((stage) => stage.code === code)?.title || code
}

function optionLabel(group: string, value: string) {
  return options.value[group]?.find((item) => item.optionValue === value)?.optionLabel || value || '未设置'
}

function statusTitle(value: string) {
  const labels: Record<string, string> = {
    not_started: '未开始',
    active: '进行中',
    delayed: '已逾期',
    completed: '已完成',
    paused: '暂停',
    submitted: '报审待受理',
    first_audit: '一级初审',
    second_audit: '二级复审',
    conclusion: '定案结论',
    archived: '办结归档',
  }
  return labels[value] || '待确认'
}

function sortTitle(value: string) {
  const labels: Record<string, string> = {
    stage: '按阶段',
    plannedEndDate: '按计划日期',
    progress: '按进度',
    amount: '按金额',
    updatedAt: '按更新',
  }
  return labels[value] || value || '默认排序'
}

function isEditableTarget(target: EventTarget | null) {
  const element = target as HTMLElement | null
  if (!element) return false
  const tag = element.tagName.toLowerCase()
  return tag === 'input' || tag === 'textarea' || tag === 'select' || element.isContentEditable
}

function focusAuditKeywordInput() {
  auditKeywordInputRef.value?.focus()
  auditKeywordInputRef.value?.select()
}

function handleAuditKeyboard(event: KeyboardEvent) {
  const shouldFocusSearch = event.key === '/' || ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k')
  if (shouldFocusSearch && !isEditableTarget(event.target)) {
    event.preventDefault()
    focusAuditKeywordInput()
    return
  }
  if (event.key !== 'Escape') return
  if (attachmentPreview.visible) {
    closeAttachmentPreview()
    return
  }
  if (tableSettingsVisible.value) {
    tableSettingsVisible.value = false
    return
  }
  if (detailVisible.value && !editing.value) {
    detailVisible.value = false
    store.selectedProject = null
  }
}

function optionValueTitle(field: AuditFieldConfig, value: unknown) {
  const raw = String(value)
  if (field.optionGroup) {
    const option = optionList(field.optionGroup).find((item) => item.optionValue === raw)
    if (option) return option.optionLabel
  }
  if (field.optionGroup === 'stage' || field.fieldKey === 'current_stage' || field.fieldKey === 'stage' || field.bindField === 'stage') {
    return stageTitle(raw)
  }
  if (field.optionGroup === 'status' || field.fieldKey === 'status' || field.bindField === 'status') {
    return statusTitle(raw)
  }
  return raw ? '待确认' : '-'
}

function stageCount(code: string) {
  return store.projectsByStage[code]?.length || 0
}

function stageTableFields(code: string) {
  return store.tableFieldsByStage[code] || store.tableFields
}

function normalizeColumnWidth(width?: number, minWidth = 96) {
  const value = Number(width || 140)
  return Math.max(minWidth, Number.isFinite(value) ? Math.round(value) : 140)
}

function fieldMinWidth(field: AuditFieldConfig) {
  return field.fieldKey === 'project_name' ? 220 : 96
}

function fieldColumnWidth(field: AuditFieldConfig) {
  return `${normalizeColumnWidth(tableWidthOverrides[field.id] ?? field.tableWidth, fieldMinWidth(field))}px`
}

function cloneTableField(field: AuditFieldConfig): TableFieldDraft {
  return {
    ...field,
    fieldLabel: field.fieldLabel || field.fieldName || field.fieldKey,
    stageKey: field.stageKey || '',
    tableWidth: normalizeColumnWidth(tableWidthOverrides[field.id] ?? field.tableWidth, fieldMinWidth(field)),
  }
}

function initTableSettingsDraft() {
  tableSettingsDraft.value = store.meta.fieldConfigs
    .filter((field) => field.enabled)
    .map(cloneTableField)
    .sort((a, b) => Number(a.sortOrder || 0) - Number(b.sortOrder || 0))
}

function markTableSettingsDirty() {
  tableSettingsDirty.value = true
}

function openTableSettings() {
  initTableSettingsDraft()
  tableSettingsVisible.value = true
}

function closeTableSettings() {
  if (!tableSettingsDirty.value) {
    tableSettingsVisible.value = false
    return
  }
  pendingLeaveAction.value = () => {
    tableSettingsVisible.value = false
  }
  showUnsavedTableSettingsPrompt()
}

function updateDraftWidth(field: TableFieldDraft) {
  field.tableWidth = normalizeColumnWidth(field.tableWidth, fieldMinWidth(field))
  tableWidthOverrides[field.id] = field.tableWidth
  markTableSettingsDirty()
}

function findDraftField(id: string) {
  return tableSettingsDraft.value.find((item) => item.id === id)
}

function ensureDraftField(field: AuditFieldConfig) {
  if (!tableSettingsDraft.value.length) initTableSettingsDraft()
  let draft = findDraftField(field.id)
  if (!draft) {
    draft = cloneTableField(field)
    tableSettingsDraft.value.push(draft)
  }
  return draft
}

function startColumnResize(event: MouseEvent, field: AuditFieldConfig) {
  if (!authStore.isAdmin) return
  const draft = ensureDraftField(field)
  resizingColumn.value = {
    id: field.id,
    startX: event.clientX,
    startWidth: normalizeColumnWidth(tableWidthOverrides[field.id] ?? draft.tableWidth ?? field.tableWidth, fieldMinWidth(field)),
    minWidth: fieldMinWidth(field),
  }
  document.addEventListener('mousemove', handleColumnResize)
  document.addEventListener('mouseup', stopColumnResize)
}

function handleColumnResize(event: MouseEvent) {
  if (!resizingColumn.value) return
  const nextWidth = normalizeColumnWidth(resizingColumn.value.startWidth + event.clientX - resizingColumn.value.startX, resizingColumn.value.minWidth)
  tableWidthOverrides[resizingColumn.value.id] = nextWidth
  const draft = findDraftField(resizingColumn.value.id)
  if (draft) draft.tableWidth = nextWidth
  markTableSettingsDirty()
}

function stopColumnResize() {
  resizingColumn.value = null
  removeColumnResizeListeners()
}

function removeColumnResizeListeners() {
  document.removeEventListener('mousemove', handleColumnResize)
  document.removeEventListener('mouseup', stopColumnResize)
}

function hasFieldConfigChanged(original: AuditFieldConfig, draft: TableFieldDraft) {
  return (
    original.fieldLabel !== draft.fieldLabel ||
    Boolean(original.visibleInTable) !== Boolean(draft.visibleInTable) ||
    (original.stageKey || '') !== (draft.stageKey || '') ||
    Number(original.sortOrder || 0) !== Number(draft.sortOrder || 0) ||
    normalizeColumnWidth(original.tableWidth, fieldMinWidth(original)) !== normalizeColumnWidth(draft.tableWidth, fieldMinWidth(original))
  )
}

function changedTableSettings() {
  const originals = new Map(store.meta.fieldConfigs.map((field) => [field.id, field]))
  return tableSettingsDraft.value
    .map((draft) => {
      const original = originals.get(draft.id)
      return original && hasFieldConfigChanged(original, draft) ? { original, draft } : null
    })
    .filter((item): item is { original: AuditFieldConfig; draft: TableFieldDraft } => Boolean(item))
}

function requestSaveTableSettings(afterSave?: () => void | Promise<void>) {
  if (!tableSettingsDirty.value) {
    MessagePlugin.warning('当前没有需要保存的表格设置')
    return
  }
  openConfirm({
    title: '确认保存表格设置？',
    message: '保存后将影响审计看板表格展示，请确认字段名称、显示状态、阶段归属和列宽已调整正确。',
    confirmText: '保存设置',
    cancelText: '继续编辑',
    onConfirm: async () => {
      await saveTableSettings()
      if (afterSave) await afterSave()
    },
  })
}

async function saveTableSettings() {
  if (!tableSettingsDraft.value.length) initTableSettingsDraft()
  const changed = changedTableSettings()
  if (!changed.length) {
    tableSettingsDirty.value = false
    MessagePlugin.warning('当前没有需要保存的表格设置')
    return
  }
  tableSettingsSaving.value = true
  try {
    for (const { original, draft } of changed) {
      await saveFieldConfig({
        ...original,
        fieldLabel: draft.fieldLabel,
        fieldName: draft.fieldLabel,
        visibleInTable: Boolean(draft.visibleInTable),
        stageKey: draft.stageKey || '',
        sortOrder: Number(draft.sortOrder || 0),
        tableWidth: normalizeColumnWidth(draft.tableWidth, fieldMinWidth(original)),
      })
    }
    await store.refreshAll()
    for (const key of Object.keys(tableWidthOverrides)) delete tableWidthOverrides[key]
    tableSettingsDirty.value = false
    tableSettingsVisible.value = false
    initTableSettingsDraft()
    MessagePlugin.success('表格设置已保存')
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '表格设置保存失败，请稍后重试或联系管理员'))
    throw err
  } finally {
    tableSettingsSaving.value = false
  }
}

function discardTableSettings() {
  initTableSettingsDraft()
  for (const key of Object.keys(tableWidthOverrides)) delete tableWidthOverrides[key]
  tableSettingsDirty.value = false
  tableSettingsVisible.value = false
  const action = pendingLeaveAction.value
  pendingLeaveAction.value = null
  action?.()
}

function showUnsavedTableSettingsPrompt() {
  openConfirm({
    title: '表格设置尚未保存',
    message: '当前字段显示、排序或列宽还没有保存。可以保存后离开，也可以放弃本次更改。',
    confirmText: '保存并离开',
    cancelText: '继续编辑',
    thirdText: '放弃更改',
    onConfirm: async () => {
      await saveTableSettings()
      const action = pendingLeaveAction.value
      pendingLeaveAction.value = null
      await action?.()
    },
    onThird: () => {
      discardTableSettings()
    },
  })
}

function requestViewMode(nextMode: AuditViewMode) {
  if (nextMode === viewMode.value) return
  if (!tableSettingsDirty.value) {
    viewMode.value = nextMode
    return
  }
  pendingLeaveAction.value = () => {
    viewMode.value = nextMode
  }
  showUnsavedTableSettingsPrompt()
}

function handleBeforeUnload(event: BeforeUnloadEvent) {
  if (!tableSettingsDirty.value) return
  event.preventDefault()
  event.returnValue = '当前表格设置尚未保存，是否离开？'
}

function openConfirm(options: {
  title: string
  message: string
  confirmText: string
  cancelText: string
  thirdText?: string
  onConfirm?: () => void | Promise<void>
  onCancel?: () => void | Promise<void>
  onThird?: () => void | Promise<void>
}) {
  confirmState.visible = true
  confirmState.title = options.title
  confirmState.message = options.message
  confirmState.confirmText = options.confirmText
  confirmState.cancelText = options.cancelText
  confirmState.thirdText = options.thirdText || ''
  confirmState.onConfirm = options.onConfirm || null
  confirmState.onCancel = options.onCancel || null
  confirmState.onThird = options.onThird || null
}

function closeConfirm() {
  confirmState.visible = false
  confirmState.onConfirm = null
  confirmState.onCancel = null
  confirmState.onThird = null
}

async function confirmPrimaryAction() {
  const action = confirmState.onConfirm
  closeConfirm()
  await action?.()
}

async function confirmCancelAction() {
  const action = confirmState.onCancel
  closeConfirm()
  await action?.()
}

async function confirmThirdAction() {
  const action = confirmState.onThird
  closeConfirm()
  await action?.()
}

function goProject(projectId: string) {
  router.push({ path: '/project-management', query: { projectId } })
}

function openWorkItem(item: WorkItem) {
  if (item.auditProjectId) {
    router.push({ path: '/audit', query: { projectId: item.auditProjectId } })
    return
  }
  if (item.projectId) {
    router.push({ path: '/project-management', query: { projectId: item.projectId } })
  }
}

function isOverdue(project: AuditProject) {
  return Boolean(project.deadline.auditDeadline && project.deadline.auditDeadline < new Date().toISOString().slice(0, 10) && project.stage !== 'archived')
}

function applyFilters() {
  activeSummaryCard.value = ''
  store.filters.page = 1
  store.refreshProjects()
}

function clearActiveFilterChip(key: string) {
  activeSummaryCard.value = ''
  if (key === 'keyword') store.filters.keyword = ''
  if (key === 'stage') store.filters.stage = ''
  if (key === 'priority') store.filters.priority = ''
  if (key === 'category') store.filters.category = ''
  if (key === 'status') store.filters.status = ''
  if (key === 'owner') store.filters.owner = ''
  if (key === 'startDate') store.filters.startDate = ''
  if (key === 'endDate') store.filters.endDate = ''
  if (key === 'onlyOverdue') store.filters.onlyOverdue = false
  if (key === 'onlyUpcomingDue') store.filters.onlyUpcomingDue = false
  if (key === 'onlyMonthlyNew') store.filters.onlyMonthlyNew = false
  if (key === 'sort') store.filters.sort = 'stage'
  store.filters.page = 1
  store.refreshProjects()
}

function resetFilters() {
  activeSummaryCard.value = ''
  store.resetFilters()
  store.refreshProjects()
}

function applySummaryCard(card: AuditSummaryCard) {
  store.resetFilters()
  Object.assign(store.filters, card.filters)
  store.filters.page = 1
  activeSummaryCard.value = card.key
  detailVisible.value = false
  editing.value = false
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
  await nextTick()
  detailSectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
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
    MessagePlugin.error(friendlyErrorMessage(err, '附件上传失败，请检查文件后重试'))
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
    attachmentPreview.error = friendlyErrorMessage(err, '预览失败，请下载后查看')
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
    MessagePlugin.error(friendlyErrorMessage(err, '下载失败，请稍后重试'))
  }
}

async function removeAttachment(file: AuditProjectAttachment) {
  openConfirm({
    title: '删除附件？',
    message: `删除「${attachmentName(file)}」后，将不再出现在当前审计项目的资料列表中。`,
    confirmText: '删除附件',
    cancelText: '取消',
    thirdText: '',
    onConfirm: async () => {
      await runRemoveAttachment(file)
    },
  })
}

async function runRemoveAttachment(file: AuditProjectAttachment) {
  try {
    await store.removeAttachment(file.id)
    MessagePlugin.success('附件已删除')
  } catch (err) {
    MessagePlugin.error(friendlyErrorMessage(err, '附件删除失败，请稍后重试'))
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
.work-item-strip {
  display: grid;
  grid-template-columns: 160px repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  scroll-margin-top: var(--space-4);
  transition: box-shadow .2s ease, background .2s ease;
}
.work-item-strip--focus {
  padding: 4px;
  margin: -4px -4px calc(var(--space-4) - 4px);
  background: var(--color-brand-50);
  box-shadow: 0 0 0 2px var(--color-brand-300);
}
.work-item-strip__head,
.work-item-card {
  min-height: 92px;
  padding: var(--space-3);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-elevated);
}
.work-item-strip__head {
  display: grid;
  align-content: center;
  gap: 4px;
}
.work-item-strip__head strong { font-size: var(--text-lg); }
.work-item-strip__head span,
.work-item-card span,
.work-item-card em {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
}
.work-item-card {
  display: grid;
  gap: 4px;
  text-align: left;
  cursor: pointer;
}
.work-item-card strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.work-item-card em {
  display: -webkit-box;
  overflow: hidden;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.work-item-card[data-level='danger'] { border-left: 3px solid var(--color-danger); }
.work-item-card[data-level='warning'] { border-left: 3px solid var(--color-warning); }
.work-item-card[data-level='primary'] { border-left: 3px solid var(--color-brand-500); }
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
  text-align: left;
  cursor: pointer;
  font: inherit;
}
.summary-card:hover,
.summary-card:focus-visible,
.summary-card--active {
  border-color: var(--color-brand-300);
  box-shadow: var(--shadow-overlay);
  outline: none;
}
.summary-card--active {
  background: var(--color-brand-50);
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
.active-filter-strip {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin: calc(var(--space-2) * -1) 0 var(--space-4);
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
  border-radius: var(--radius-md);
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
.error-alert { margin-bottom: var(--space-4); }
.recoverable-alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
}
.recoverable-alert > div { display: grid; gap: 2px; }
.recoverable-alert strong { color: var(--text-primary); font-size: var(--text-sm); }
.recoverable-alert span { color: var(--text-secondary); font-size: var(--text-sm); line-height: 1.7; }
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

.gantt-view, .table-view, .stage-table-view {
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
.stage-table-view {
  display: grid;
  gap: var(--space-3);
  padding: var(--space-3);
}
.stage-table-card {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: var(--space-3);
  align-items: stretch;
  min-width: 0;
}
.stage-table-rail {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 100%;
  padding: var(--space-3) 0;
  color: var(--stage-color, var(--color-brand-500));
}
.stage-table-rail__line {
  width: 2px;
  flex: 1 1 auto;
  min-height: 36px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--stage-color, var(--color-brand-500)) 72%, white);
  opacity: .9;
}
.stage-table-rail__text {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  display: inline-block;
  font-size: var(--text-sm);
  font-weight: 700;
  letter-spacing: 0;
  white-space: nowrap;
  transform: rotate(180deg);
  transform-origin: center;
}
.stage-table-rail__count {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  display: inline-block;
  font-size: var(--text-xs);
  color: var(--text-secondary);
  white-space: nowrap;
  transform: rotate(180deg);
  transform-origin: center;
}
.stage-table-panel {
  min-width: 0;
  overflow: hidden;
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}
.stage-table-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  align-items: flex-start;
  padding: var(--space-4) var(--space-4) var(--space-3);
  border-bottom: 1px solid var(--border-color);
  background: var(--bg-muted);
}
.stage-table-head h2 { margin: 0; font-size: var(--text-lg); }
.stage-table-head p { margin: 4px 0 0; color: var(--text-secondary); font-size: var(--text-xs); }
.stage-table-head strong { font-size: var(--text-lg); }
.stage-table-scroll { overflow: auto; }
.stage-table-scroll table {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
  table-layout: fixed;
}
.stage-table-scroll th, .stage-table-scroll td {
  border-bottom: 1px solid var(--border-color);
  padding: 12px 14px;
  text-align: left;
  font-size: var(--text-sm);
  vertical-align: top;
  overflow-wrap: anywhere;
}
.stage-table-scroll th {
  position: relative;
  background: var(--bg-page);
  color: var(--text-secondary);
  font-weight: 600;
  white-space: nowrap;
}
.resizable-th {
  padding-right: 18px !important;
  user-select: none;
}
.resizable-th > span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
}
.column-resize-handle {
  position: absolute;
  top: 0;
  right: 0;
  width: 10px;
  height: 100%;
  border: 0;
  border-right: 2px solid transparent;
  background: transparent;
  cursor: col-resize;
}
.column-resize-handle:hover,
.column-resize-handle:focus-visible {
  border-right-color: var(--color-brand-500);
  background: color-mix(in srgb, var(--color-brand-500) 8%, transparent);
  outline: none;
}
.stage-table-project { min-width: 220px; }
.stage-table-project .project-link {
  width: 100%;
  text-align: left;
  border: 0;
  background: transparent;
  padding: 0;
  cursor: pointer;
  display: grid;
  gap: 3px;
}
.stage-table-project .project-link strong {
  font-size: var(--text-sm);
  line-height: 1.45;
}
.stage-table-project .project-link span {
  font-size: var(--text-xs);
  color: var(--text-secondary);
}
.stage-table-empty {
  text-align: center;
  color: var(--text-tertiary);
  padding: var(--space-5) !important;
}
.link-button { border: 0; background: transparent; color: var(--color-brand-500); cursor: pointer; }

.stage-card-view {
  display: grid;
  gap: var(--space-4);
}

.stage-card-section {
  padding: var(--space-4);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-elevated);
  border-left: 3px solid var(--stage-color, var(--color-brand-500));
}

.stage-card-section__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.stage-card-section__head h2 {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: var(--text-lg);
}

.stage-card-section__head p {
  margin: 4px 0 0 20px;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.stage-card-section__head strong {
  color: var(--stage-color, var(--color-brand-500));
  font-size: var(--text-lg);
}

.stage-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  margin-right: 8px;
  border-radius: 999px;
  background: var(--stage-color, var(--color-brand-500));
}

.audit-project-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--space-3);
}

.audit-project-card {
  display: grid;
  gap: var(--space-3);
  min-width: 0;
  padding: var(--space-4);
  text-align: left;
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-left: 3px solid var(--stage-color, var(--color-brand-500));
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color var(--duration-fast), box-shadow var(--duration-fast), transform var(--duration-fast);
}

.audit-project-card:hover {
  border-color: var(--stage-color, var(--color-brand-500));
  box-shadow: var(--shadow-elevated);
  transform: translateY(-1px);
}

.audit-project-card__title,
.audit-project-card__footer {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
}

.audit-project-card__title strong {
  display: block;
  font-size: var(--text-md);
  line-height: 1.45;
}

.audit-project-card__title span,
.audit-project-card__footer,
.audit-card-keyline span,
.audit-card-fields dt {
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.audit-project-card__title em,
.audit-project-card__footer em {
  flex: 0 0 auto;
  font-style: normal;
  color: var(--color-brand-600);
  font-size: var(--text-xs);
}

.audit-project-card__title em {
  padding: 2px 8px;
  color: var(--color-brand-600);
  background: var(--bg-active);
  border: 1px solid color-mix(in srgb, var(--color-brand-500) 24%, white);
  border-radius: var(--radius-sm);
}

.audit-card-keyline {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px var(--space-3);
  padding: var(--space-3);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
}

.audit-card-keyline span,
.audit-card-keyline strong {
  min-width: 0;
}

.audit-card-fields {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px var(--space-3);
  margin: 0;
}

.audit-card-fields dt,
.audit-card-fields dd {
  margin: 0;
  min-width: 0;
}

.audit-card-fields dd {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stage-card-empty {
  grid-column: 1 / -1;
  padding: var(--space-5);
  color: var(--text-tertiary);
  text-align: center;
  background: var(--bg-muted);
  border: 1px dashed var(--border-color);
}
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
.table-settings-panel {
  width: min(960px, 100vw);
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
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

.audit-detail-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-color);
}

.audit-detail-head h2 { font-size: var(--text-xl); margin: 0; }
.audit-detail-head p { font-size: var(--text-sm); color: var(--text-secondary); margin: 3px 0 0; }

.audit-detail-workspace {
  scroll-margin-top: var(--space-4);
}

.audit-detail-panel {
  display: grid;
  gap: var(--space-4);
  padding: var(--space-5);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-elevated);
}

.audit-detail-workspace .detail-view {
  display: grid;
  gap: var(--space-4);
}

.audit-detail-hero {
  display: flex;
  justify-content: space-between;
  gap: var(--space-4);
  align-items: flex-start;
  padding: var(--space-4);
  background: linear-gradient(135deg, var(--color-brand-50), var(--bg-surface) 64%);
  border: 1px solid var(--color-brand-200);
}

.audit-detail-hero h3 {
  margin: 8px 0 4px;
  font-size: var(--text-2xl);
}

.audit-detail-hero p {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.audit-detail-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--space-2);
}

.audit-detail-kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
}

.audit-detail-kpis article {
  display: grid;
  gap: 6px;
  padding: var(--space-3);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
}

.audit-detail-kpis span {
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.audit-detail-kpis strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-md);
}

.next-action-panel {
  display: grid;
  gap: var(--space-3);
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
.next-action-list em,
.next-action-panel .section-title-row span {
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

.audit-detail-workspace .detail-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  margin: 0;
  border: 1px solid var(--border-color);
}

.audit-detail-workspace .detail-grid dt,
.audit-detail-workspace .detail-grid dd {
  margin: 0;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-color);
}

.audit-detail-workspace .detail-grid dt {
  color: var(--text-secondary);
  background: var(--bg-muted);
  font-size: var(--text-xs);
}

.audit-detail-workspace .detail-grid dd {
  min-width: 0;
  overflow-wrap: anywhere;
  font-size: var(--text-sm);
}

.progress-box p {
  margin: -4px 0 var(--space-3);
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.audit-timeline {
  display: grid;
  gap: var(--space-2);
}

.audit-timeline article {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--space-2);
  align-items: start;
}

.audit-timeline article > span {
  width: 10px;
  height: 10px;
  margin-top: 4px;
  border-radius: 999px;
  background: var(--color-brand-500);
}

.audit-timeline strong {
  display: block;
  font-size: var(--text-sm);
}

.audit-timeline p {
  margin: 3px 0 0;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}
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
.table-settings-body {
  min-height: 0;
  overflow: auto;
  padding: var(--space-5);
}
.table-settings-help {
  display: grid;
  gap: 4px;
  margin-bottom: var(--space-3);
  padding: var(--space-3);
  border: 1px solid var(--border-color);
  background: var(--bg-muted);
  color: var(--text-secondary);
  font-size: var(--text-sm);
}
.table-settings-help strong { color: var(--text-primary); }
.table-settings-table {
  overflow: auto;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}
.table-settings-table table {
  width: 100%;
  min-width: 820px;
  border-collapse: collapse;
}
.table-settings-table th,
.table-settings-table td {
  border-bottom: 1px solid var(--border-color);
  padding: 10px 12px;
  text-align: left;
  font-size: var(--text-sm);
  vertical-align: top;
}
.table-settings-table th {
  background: var(--bg-muted);
  color: var(--text-secondary);
  font-weight: 600;
}
.table-settings-table tr:last-child td { border-bottom: 0; }
.field-key-hint {
  display: block;
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: var(--text-xs);
}
.compact-number { width: 96px; }
.table-settings-actions {
  grid-column: auto;
  margin: 0;
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--border-color);
}
.dirty-hint {
  margin-right: auto;
  color: var(--color-warning);
  font-size: var(--text-sm);
}
.confirm-mask {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: grid;
  place-items: center;
  padding: var(--space-5);
  background: rgba(15, 23, 42, .42);
}
.confirm-panel {
  width: min(420px, 92vw);
  padding: var(--space-5);
  background: var(--bg-surface);
  border: 1px solid var(--border-color-strong);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-overlay);
}
.confirm-panel h3 {
  margin: 0;
  font-size: var(--text-lg);
}
.confirm-panel p {
  margin: var(--space-3) 0 var(--space-4);
  color: var(--text-secondary);
  line-height: 1.65;
  font-size: var(--text-sm);
}
.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.ghost-button,
.primary-button {
  min-height: 34px;
  border-radius: var(--radius-md);
  padding: 0 14px;
  font: inherit;
  cursor: pointer;
}
.ghost-button {
  border: 1px solid var(--border-color);
  background: #fff;
  color: var(--text-secondary);
}
.primary-button {
  border: 1px solid var(--color-brand-500);
  background: var(--color-brand-500);
  color: var(--text-on-brand);
}
.primary-button:disabled {
  cursor: not-allowed;
  opacity: .65;
}

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
.layout-vertical .column-head {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: var(--space-3);
}
.layout-vertical .column-head h2 {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  margin: 0;
  line-height: 1.1;
  white-space: nowrap;
}
.layout-vertical .column-head span {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  white-space: nowrap;
}
.layout-vertical .column-head strong {
  writing-mode: vertical-rl;
  text-orientation: mixed;
  white-space: nowrap;
}
.layout-vertical .column-body { min-height: 180px; }
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
  .audit-detail-hero { flex-direction: column; }
  .audit-detail-head { flex-direction: column; }
  .audit-detail-actions { justify-content: flex-start; }
  .audit-detail-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .next-action-list { grid-template-columns: 1fr; }
  .audit-detail-workspace .detail-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .project-form { grid-template-columns: 1fr; }
  .attachment-item { grid-template-columns: 1fr; }
  .attachment-actions { flex-wrap: wrap; }
}

@media (max-width: 640px) {
  .summary-grid { grid-template-columns: 1fr; }
  .toolbar { grid-template-columns: 1fr; }
  .audit-detail-kpis { grid-template-columns: 1fr; }
  .keyword { min-width: 100%; }
  .small-filter, .date-filter { width: 100%; }
  .segmented span { display: none; }
  .gantt-head, .gantt-row { grid-template-columns: 220px 520px; }
  .stage-table-card { grid-template-columns: 1fr; }
  .stage-table-rail {
    flex-direction: row;
    justify-content: flex-start;
    min-height: auto;
    padding: 0 0 var(--space-2);
  }
  .stage-table-rail__line,
  .stage-table-rail__text,
  .stage-table-rail__count {
    writing-mode: horizontal-tb;
    text-orientation: initial;
    transform: none;
  }
  .stage-table-rail__line { width: 40px; height: 2px; min-height: 0; flex: 0 0 auto; }
}
</style>

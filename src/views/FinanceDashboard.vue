<template>
  <main class="settlement-center">
    <header class="settlement-hero">
      <div>
        <p class="eyebrow">SETTLEMENT FINANCE</p>
        <h1>结算财务中心</h1>
        <span>围绕项目、合同付款节点、发票、收付款、资料和质保金进行真实业务管理。</span>
      </div>
      <div class="hero-actions">
        <span v-if="!canManageSettlementFinance" class="permission-pill">当前账号仅可查看</span>
        <button v-if="canManageSettlementFinance" class="primary-action" type="button" @click="openExistingProjectSettlement">纳入结算管理</button>
        <button class="ghost-action" type="button" @click="refresh">刷新</button>
      </div>
    </header>

    <nav class="view-tabs" aria-label="结算财务中心视图">
      <button v-for="item in views" :key="item.key" :class="{ active: activeView === item.key }" type="button" @click="setActiveView(item.key)">
        {{ item.label }}
      </button>
    </nav>

    <section v-if="activeView === 'overview'" class="view-panel">
      <div class="panel-title">
        <div>
          <h2>结算管理概览</h2>
          <span>只展示结算财务接口返回的汇总数据，未接入字段显示为“未接入”。</span>
        </div>
      </div>
      <div class="metric-grid metric-grid--wide">
        <article v-for="item in overviewMetrics" :key="item.label" class="metric-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <em>{{ item.hint }}</em>
        </article>
      </div>
      <div class="board-grid">
        <article class="sub-panel">
          <h3>今日重点待办</h3>
          <EmptyBlock v-if="workbenchItems.length === 0" title="暂无真实待办" text="财务工作台接口未返回待办数据。" />
          <div v-else class="todo-list">
            <button v-for="item in workbenchItems" :key="item.id" type="button">
              <span>{{ item.projectName || '项目待补充' }}</span>
              <strong>{{ item.action || '待处理' }}</strong>
            </button>
          </div>
        </article>
        <article class="sub-panel">
          <h3>回款风险排行</h3>
          <EmptyBlock title="暂无真实风险数据" text="逾期、可收款和责任人排行需要结算财务接口返回后展示。" />
        </article>
        <article class="sub-panel">
          <h3>结算进度分布</h3>
          <EmptyBlock v-if="settlementProjects.length === 0" title="暂无结算台账数据" text="未读取到项目结算台账。" />
          <div v-else class="status-list">
            <span v-for="item in settlementStatusStats" :key="item.status">
              <strong>{{ item.status }}</strong><em>{{ item.count }}</em>
            </span>
          </div>
        </article>
      </div>
    </section>

    <section v-else-if="activeView === 'workbench'" class="view-panel">
      <div class="panel-title">
        <div>
          <h2>财务工作台</h2>
          <span>待开发票、待登记收款、待上传回单、逾期未收款等任务从财务工作台接口读取。</span>
        </div>
      </div>
      <DataTable :columns="['项目名称', '建设单位/付款单位', '当前付款节点', '应收/应付金额', '剩余金额', '状态/操作']">
        <article v-for="item in workbenchItems" :key="item.id" class="table-row table-row--six">
          <span>{{ item.projectName || '-' }}</span>
          <span>{{ item.ownerUnit || '-' }}</span>
          <span>{{ item.currentNode || '-' }}</span>
          <MoneyCell :amount="item.amount" />
          <MoneyCell :amount="item.remainingAmount" />
          <span><em class="status-pill" :class="{ danger: item.isOverdue }">{{ item.action || item.invoiceStatus || '-' }}</em></span>
        </article>
        <div v-if="workbenchItems.length === 0" class="empty-row">暂无真实财务待办</div>
      </DataTable>
    </section>

    <section v-else-if="activeView === 'ledger'" class="view-panel">
      <div class="panel-title">
        <div>
          <h2>项目结算台账</h2>
          <span>按项目主档案集中查看合同、审计、开票、收款和下一步动作。</span>
        </div>
        <div class="settlement-ledger__summary">
          <strong>{{ visibleSettlementProjects.length }}</strong>
          <span>/ {{ settlementProjects.length }} 个项目</span>
        </div>
      </div>
      <div class="settlement-ledger__toolbar">
        <div class="settlement-ledger__toolbar-title">
          <strong>项目结算视图</strong>
          <span>筛选只影响当前展示，不改变结算数据。</span>
        </div>
        <div class="settlement-ledger__filters" role="group" aria-label="按结算状态筛选">
          <span>结算状态</span>
          <button
            v-for="option in ledgerStatusOptions"
            :key="option.value"
            type="button"
            :class="{ active: ledgerStatusFilter === option.value }"
            @click="ledgerStatusFilter = option.value"
          >
            {{ option.label }} <b>{{ option.count }}</b>
          </button>
        </div>
      </div>
      <div class="settlement-ledger" role="table" aria-label="项目结算台账">
        <div class="settlement-ledger__group-head" role="row">
          <span role="columnheader">项目档案<small>项目与参建单位</small></span>
          <span role="columnheader">资金与结算<small>合同、审计、开票、收款</small></span>
          <span role="columnheader">推进状态<small>当前状态与下一步动作</small></span>
        </div>
        <div class="settlement-ledger__head" role="row">
          <span role="columnheader">项目主档案</span>
          <span role="columnheader">建设 / 施工单位</span>
          <span role="columnheader">合同与审计</span>
          <span role="columnheader">开票与收款</span>
          <span role="columnheader">当前状态</span>
          <span role="columnheader">下一步动作</span>
        </div>
        <article v-for="item in visibleSettlementProjects" :key="item.id" class="settlement-ledger__row" role="row">
          <span class="settlement-ledger__project" role="cell">
            <strong>{{ item.projectName || '项目名称待补充' }}</strong>
            <small>{{ item.projectCode || '项目编号待补充' }}</small>
          </span>
          <span class="settlement-ledger__parties" role="cell">
            <strong>{{ item.ownerUnit || '建设单位待补充' }}</strong>
            <small>施工：{{ item.constructionUnit || '待补充' }}</small>
            <small v-if="item.managerName">项目经理：{{ item.managerName }}</small>
          </span>
          <span class="settlement-ledger__money-stack" role="cell">
            <small><em>合同额</em><strong>{{ formatNullableMoney(item.contractAmount) }}</strong></small>
            <small><em>送审</em><strong>{{ formatNullableMoney(item.submittedAmount) }}</strong></small>
            <small><em>审定</em><strong>{{ formatNullableMoney(item.finalAuditAmount ?? item.finalAuditedAmount) }}</strong></small>
          </span>
          <span class="settlement-ledger__money-stack" role="cell">
            <small><em>已开票</em><strong>{{ formatNullableMoney(item.invoicedAmount ?? item.invoiceAmount) }}</strong></small>
            <small><em>已收款</em><strong>{{ formatNullableMoney(item.paymentSummary?.ownerPaidAmount ?? item.receivedAmount) }}</strong></small>
            <small v-if="item.receivableAmount !== undefined && item.receivableAmount !== null"><em>待收款</em><strong>{{ formatNullableMoney(item.receivableAmount) }}</strong></small>
          </span>
          <span class="settlement-ledger__status" role="cell">
            <em class="status-pill">{{ item.settlementStatus || '状态待补充' }}</em>
            <small>{{ item.collectionStatus || item.invoiceStatus || item.auditStatus || '结算信息待补充' }}</small>
          </span>
          <span class="settlement-ledger__next-action" role="cell">
            <strong>{{ item.nextAction || item.nextPaymentNode || '待补充下一步动作' }}</strong>
            <small v-if="item.nextPaymentNode && item.nextAction">付款节点：{{ item.nextPaymentNode }}</small>
            <small v-else>根据当前结算状态继续维护</small>
          </span>
        </article>
        <div v-if="visibleSettlementProjects.length === 0" class="settlement-ledger__empty">
          <span>{{ settlementProjects.length === 0 ? '暂无真实项目结算台账' : '当前筛选条件下暂无项目' }}</span>
          <button v-if="settlementProjects.length > 0" type="button" @click="ledgerStatusFilter = 'all'">清除筛选</button>
          <button v-if="settlementProjects.length === 0 && canManageSettlementFinance" type="button" @click="openExistingProjectSettlement">纳入结算管理</button>
          <small v-else-if="settlementProjects.length === 0">如需维护结算信息，请联系管理员开通编辑权限。</small>
        </div>
      </div>
    </section>

    <section v-else-if="activeView === 'invoice'" class="view-panel">
      <div class="panel-title">
        <div>
          <h2>发票管理</h2>
          <span>发票号码、金额、税率、状态和回款联动均来自发票接口。</span>
        </div>
      </div>
      <DataTable :columns="['发票编号', '项目/合同', '付款节点', '发票金额', '开票日期', '状态']">
        <article v-for="item in invoices" :key="item.id" class="table-row table-row--six">
          <span>{{ item.invoiceNo || '-' }}</span>
          <span>
            <strong>{{ item.projectName || '-' }}</strong>
            <small>{{ item.contractName || '-' }}</small>
          </span>
          <span>{{ item.paymentNodeName || '-' }}</span>
          <MoneyCell :amount="item.invoiceAmount" />
          <span>{{ item.invoiceDate || '-' }}</span>
          <span><em class="status-pill">{{ item.invoiceStatus || item.collectionStatus || '-' }}</em></span>
        </article>
        <div v-if="invoices.length === 0" class="empty-row">暂无真实发票记录</div>
      </DataTable>
    </section>

    <section v-else-if="activeView === 'payment'" class="view-panel">
      <SettlementPaymentFlowPanel :settlements="settlementProjects" :can-manage="canManageSettlementFinance" @saved="refresh" />
    </section>

    <section v-else-if="activeView === 'documents'" class="view-panel">
      <div class="panel-title">
        <div>
          <h2>结算资料管理</h2>
          <span>与项目台账资料中心同步，按结算项目查看合同、过程、验收、审计和财务资料。</span>
        </div>
        <div class="settlement-ledger__summary">
          <strong>{{ settlementDocumentCount }}</strong>
          <span>份资料 · {{ settlementDocumentGroups.length }} 个项目</span>
        </div>
      </div>
      <div v-if="settlementDocumentGroups.length === 0" class="settlement-documents__empty">
        <EmptyBlock
          :title="settlementProjects.length === 0 ? '暂无结算项目' : '暂无已归档结算资料'"
          :text="settlementProjects.length === 0 ? '请先从项目台账纳入结算管理。' : '当前结算项目尚未在项目资料中心归档资料。资料上传后会自动同步到这里。'"
        />
      </div>
      <div v-else class="settlement-document-groups">
        <article v-for="group in settlementDocumentGroups" :key="group.key" class="settlement-document-group">
          <header class="settlement-document-group__head">
            <div>
              <strong>{{ group.projectName }}</strong>
              <small>{{ group.projectCode || '项目编号待补充' }} · {{ group.files.length }} 份资料</small>
            </div>
            <button type="button" @click="openSettlementProject(group.projectId)">打开项目台账</button>
          </header>
          <div class="settlement-document-group__categories">
            <span v-for="category in group.categories" :key="category.label">
              {{ category.label }} <b>{{ category.count }}</b>
            </span>
          </div>
          <ul class="settlement-document-list">
            <li v-for="file in group.files" :key="file.id">
              <span class="settlement-document-list__main">
                <strong>{{ file.displayName || file.originalName || '未命名资料' }}</strong>
                <small>{{ file.categoryName || '项目资料' }} · {{ file.stageLabel || '项目资料' }} · {{ file.sourceLabel || '项目资料中心' }}</small>
              </span>
              <em>{{ file.evidenceStatus || '已归档' }}</em>
            </li>
          </ul>
        </article>
      </div>
    </section>

    <section v-else class="view-panel">
      <div class="panel-title">
        <div>
          <h2>质保金管理</h2>
          <span>质保金金额、到期日和退还状态从质保金接口读取。</span>
        </div>
      </div>
      <DataTable :columns="['项目/合同', '质保金比例', '质保金金额', '开始日期', '到期日期', '退还状态']">
        <article v-for="item in retentions" :key="item.id" class="table-row table-row--six">
          <span>
            <strong>{{ item.projectName || '-' }}</strong>
            <small>{{ item.contractName || '-' }}</small>
          </span>
          <span>{{ formatRatio(item.retentionRatio) }}</span>
          <MoneyCell :amount="item.retentionAmount" />
          <span>{{ item.warrantyStartDate || '-' }}</span>
          <span>{{ item.warrantyEndDate || '-' }}</span>
          <span><em class="status-pill" :class="{ danger: item.isDue && item.refundStatus !== '已退还' }">{{ item.refundStatus || '-' }}</em></span>
        </article>
        <div v-if="retentions.length === 0" class="empty-row">暂无真实质保金记录</div>
      </DataTable>
    </section>

    <p v-if="loadMessage" class="system-note">{{ loadMessage }}</p>
    <p v-if="formMessage" class="system-note" :class="{ danger: formMessageType === 'error', success: formMessageType === 'success' }">{{ formMessage }}</p>

    <SettlementManagementWizard
      v-model:visible="existingSettlementDialog.visible"
      :projects="existingProjects"
      :settlements="settlementProjects"
      @saved="refresh"
    />

    <AModal
      v-if="false"
      v-model:visible="existingSettlementDialog.visible"
      title="给已有项目增加结算信息"
      width="1080px"
      :confirm-btn="{ content: existingWizardPrimaryText, loading: existingSettlementDialog.saving }"
      :mask-closable="false"
      @confirm="handleExistingSettlementWizardConfirm"
    >
      <div class="settlement-wizard">
        <aside class="settlement-wizard__steps">
          <button
            v-for="(step, index) in settlementWizardSteps"
            :key="step.key"
            type="button"
            :class="{ active: existingSettlementStepIndex === index, done: existingSettlementStepIndex > index }"
            @click="existingSettlementStepIndex = index"
          >
            <span>{{ index + 1 }}</span>
            <strong>{{ step.label }}</strong>
            <em>{{ step.hint }}</em>
          </button>
        </aside>

        <AForm :model="existingSettlementForm" layout="vertical" class="settlement-wizard__body">
          <section v-if="existingSettlementStepKey === 'project'" class="wizard-pane">
            <div class="wizard-pane__head">
              <h3>先选择项目，系统自动带出主档案</h3>
              <p>从项目管理中选择已有项目，避免重复填写项目名称、建设单位、施工单位和负责人。</p>
            </div>
            <AFormItem field="projectId" label="选择已有项目" required>
              <ASelect
                v-model="existingSettlementForm.projectId"
                :options="projectSelectOptions"
                allow-search
                placeholder="请选择项目管理中已有的项目"
              />
            </AFormItem>
            <div class="auto-info-grid">
              <article v-for="item in selectedProjectFacts" :key="item.label">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </article>
            </div>
          </section>

          <section v-else-if="existingSettlementStepKey === 'contract'" class="wizard-pane">
            <div class="wizard-pane__head">
              <h3>确认合同金额和付款约定</h3>
              <p>合同信息优先从项目主档案带出；财务只补充本次结算事项和必要金额。</p>
            </div>
            <div class="auto-info-grid">
              <article>
                <span>合同金额</span>
                <strong>{{ formatNullableMoney(selectedExistingProject?.contractAmount) }}</strong>
              </article>
              <article>
                <span>已付款金额</span>
                <strong>{{ formatNullableMoney(selectedExistingProject?.paidAmount) }}</strong>
              </article>
              <article class="wide">
                <span>付款条款</span>
                <strong>{{ selectedExistingProject?.paymentTerms || '项目主档案暂未填写付款条款' }}</strong>
              </article>
            </div>
            <div class="settlement-form-grid">
              <AFormItem class="form-span-2" field="settlementName" label="本次结算名称" required>
                <AInput v-model="existingSettlementForm.settlementName" placeholder="如：竣工结算款、合同进度款、质保金退还" />
              </AFormItem>
              <AFormItem field="settlementType" label="结算事项">
                <AInput v-model="existingSettlementForm.settlementType" placeholder="如：合同款、结算款、质保金" />
              </AFormItem>
              <AFormItem field="applyAmount" label="本次申报金额">
                <AInputNumber v-model="existingSettlementForm.applyAmount" :min="0" :precision="2" hide-button />
              </AFormItem>
            </div>
          </section>

          <section v-else-if="existingSettlementStepKey === 'stage'" class="wizard-pane">
            <div class="wizard-pane__head">
              <h3>判断当前结算阶段</h3>
              <p>通过业务问答确认是否送审、是否审定、是否已付款，减少状态误选。</p>
            </div>
            <div class="wizard-choice-grid">
              <button
                v-for="option in settlementStatusOptions"
                :key="option.value"
                type="button"
                :class="{ active: existingSettlementForm.settlementStatus === option.value }"
                @click="existingSettlementForm.settlementStatus = option.value"
              >
                <strong>{{ option.label }}</strong>
                <span>{{ settlementStatusHint(option.value) }}</span>
              </button>
            </div>
            <div class="settlement-form-grid">
              <AFormItem field="approvedAmount" label="核定 / 审定金额">
                <AInputNumber v-model="existingSettlementForm.approvedAmount" :min="0" :precision="2" hide-button />
              </AFormItem>
              <AFormItem field="paidAmount" label="已付款金额">
                <AInputNumber v-model="existingSettlementForm.paidAmount" :min="0" :precision="2" hide-button />
              </AFormItem>
              <AFormItem field="applyDate" label="申报日期">
                <AInput v-model="existingSettlementForm.applyDate" placeholder="YYYY-MM-DD" />
              </AFormItem>
              <AFormItem field="paidDate" label="实际付款日期">
                <AInput v-model="existingSettlementForm.paidDate" placeholder="YYYY-MM-DD" />
              </AFormItem>
            </div>
          </section>

          <section v-else-if="existingSettlementStepKey === 'template'" class="wizard-pane">
            <div class="wizard-pane__head">
              <h3>生成付款节点、资料清单和财务待办</h3>
              <p>当前版本先保存结算台账信息；付款条款模板、资料清单和待办生成需后端模板接口接入后自动生成。</p>
            </div>
            <div class="generated-preview-grid">
              <article>
                <strong>付款节点</strong>
                <span>{{ selectedExistingProject?.paymentTerms ? '将根据项目付款条款生成节点' : '待补充付款条款后生成' }}</span>
              </article>
              <article>
                <strong>资料清单</strong>
                <span>待模板接口接入后自动生成合同、审计、发票和回单资料清单</span>
              </article>
              <article>
                <strong>财务待办</strong>
                <span>保存后进入结算台账，后续由财务工作台接口返回待办</span>
              </article>
            </div>
            <AFormItem field="expectedPayDate" label="预计付款日期">
              <AInput v-model="existingSettlementForm.expectedPayDate" placeholder="YYYY-MM-DD" />
            </AFormItem>
          </section>

          <section v-else class="wizard-pane">
            <div class="wizard-pane__head">
              <h3>确认生成结算台账</h3>
              <p>请确认系统带出的项目主数据和财务补充信息，确认后写入真实结算记录。</p>
            </div>
            <div class="wizard-review-list">
              <span v-for="item in existingSettlementReviewItems" :key="item.label">
                <em>{{ item.label }}</em>
                <strong>{{ item.value }}</strong>
              </span>
            </div>
            <AFormItem field="remark" label="备注">
              <ATextarea v-model="existingSettlementForm.remark" :auto-size="{ minRows: 3, maxRows: 5 }" placeholder="记录付款条件、资料要求或财务备注" />
            </AFormItem>
          </section>

          <div class="wizard-inline-actions">
            <button type="button" :disabled="existingSettlementStepIndex === 0" @click="existingSettlementStepIndex -= 1">上一步</button>
            <span>{{ existingSettlementStepIndex + 1 }} / {{ settlementWizardSteps.length }}</span>
          </div>
        </AForm>
      </div>
    </AModal>

    <AModal
      v-if="false"
      v-model:visible="newSettlementProjectDialog.visible"
      title="新增结算项目"
      width="1080px"
      :confirm-btn="{ content: newWizardPrimaryText, loading: newSettlementProjectDialog.saving }"
      :mask-closable="false"
      @confirm="handleNewSettlementWizardConfirm"
    >
      <div class="settlement-wizard">
        <aside class="settlement-wizard__steps">
          <button
            v-for="(step, index) in settlementWizardSteps"
            :key="step.key"
            type="button"
            :class="{ active: newSettlementStepIndex === index, done: newSettlementStepIndex > index }"
            @click="newSettlementStepIndex = index"
          >
            <span>{{ index + 1 }}</span>
            <strong>{{ step.label }}</strong>
            <em>{{ step.hint }}</em>
          </button>
        </aside>

        <AForm :model="newSettlementProjectForm" layout="vertical" class="settlement-wizard__body">
          <section v-if="newSettlementStepKey === 'project'" class="wizard-pane">
            <div class="wizard-pane__head">
              <h3>录入最小项目主数据</h3>
              <p>只在项目管理中不存在该项目时使用；已有项目应从“补充已有项目”进入。</p>
            </div>
            <div class="settlement-form-grid">
              <AFormItem class="form-span-2" field="projectName" label="项目名称" required>
                <AInput v-model="newSettlementProjectForm.projectName" placeholder="请输入真实结算项目名称" />
              </AFormItem>
              <AFormItem field="projectCode" label="项目编号">
                <AInput v-model="newSettlementProjectForm.projectCode" placeholder="如已有编号可填写" />
              </AFormItem>
              <AFormItem field="managerName" label="负责人">
                <AInput v-model="newSettlementProjectForm.managerName" placeholder="请输入负责人姓名" />
              </AFormItem>
              <AFormItem field="ownerUnit" label="建设/付款单位">
                <AInput v-model="newSettlementProjectForm.ownerUnit" placeholder="请输入建设单位或付款单位" />
              </AFormItem>
              <AFormItem field="constructionUnit" label="施工单位">
                <AInput v-model="newSettlementProjectForm.constructionUnit" placeholder="请输入施工单位" />
              </AFormItem>
            </div>
          </section>

          <section v-else-if="newSettlementStepKey === 'contract'" class="wizard-pane">
            <div class="wizard-pane__head">
              <h3>确认合同金额、暂列金、暂估价和付款条款</h3>
              <p>金额由财务确认，后续付款节点将基于付款条款模板自动拆分。</p>
            </div>
            <div class="settlement-form-grid">
              <AFormItem field="contractAmount" label="合同金额">
                <AInputNumber v-model="newSettlementProjectForm.contractAmount" :min="0" :precision="2" hide-button />
              </AFormItem>
              <AFormItem field="submittedAmount" label="送审金额">
                <AInputNumber v-model="newSettlementProjectForm.submittedAmount" :min="0" :precision="2" hide-button />
              </AFormItem>
              <AFormItem field="provisionalSum" label="暂列金">
                <AInputNumber v-model="newSettlementProjectForm.provisionalSum" :min="0" :precision="2" hide-button />
              </AFormItem>
              <AFormItem field="estimatedPrice" label="暂估价">
                <AInputNumber v-model="newSettlementProjectForm.estimatedPrice" :min="0" :precision="2" hide-button />
              </AFormItem>
              <AFormItem class="form-span-2" field="nextPaymentNode" label="付款条款 / 下一付款节点">
                <AInput v-model="newSettlementProjectForm.nextPaymentNode" placeholder="如：竣工验收后支付至 80%，审定后支付至 97%" />
              </AFormItem>
            </div>
          </section>

          <section v-else-if="newSettlementStepKey === 'stage'" class="wizard-pane">
            <div class="wizard-pane__head">
              <h3>问答判断当前结算阶段</h3>
              <p>确认是否送审、一审/二审/定案是否完成，系统据此进入正确台账状态。</p>
            </div>
            <div class="wizard-choice-grid">
              <button
                v-for="option in settlementStatusOptions"
                :key="option.value"
                type="button"
                :class="{ active: newSettlementProjectForm.settlementStatus === option.value }"
                @click="newSettlementProjectForm.settlementStatus = option.value"
              >
                <strong>{{ option.label }}</strong>
                <span>{{ settlementStatusHint(option.value) }}</span>
              </button>
            </div>
            <div class="settlement-form-grid">
              <AFormItem field="firstAuditAmount" label="一审金额">
                <AInputNumber v-model="newSettlementProjectForm.firstAuditAmount" :min="0" :precision="2" hide-button />
              </AFormItem>
              <AFormItem field="secondAuditAmount" label="二审金额">
                <AInputNumber v-model="newSettlementProjectForm.secondAuditAmount" :min="0" :precision="2" hide-button />
              </AFormItem>
              <AFormItem field="finalAuditedAmount" label="定案 / 审定金额">
                <AInputNumber v-model="newSettlementProjectForm.finalAuditedAmount" :min="0" :precision="2" hide-button />
              </AFormItem>
              <AFormItem field="retentionAmount" label="质保金金额">
                <AInputNumber v-model="newSettlementProjectForm.retentionAmount" :min="0" :precision="2" hide-button />
              </AFormItem>
            </div>
          </section>

          <section v-else-if="newSettlementStepKey === 'template'" class="wizard-pane">
            <div class="wizard-pane__head">
              <h3>选择付款条款模板并生成待办</h3>
              <p>模板接口接入后将自动生成付款节点、应收/应付金额、资料清单和财务待办；当前先记录真实关键字段。</p>
            </div>
            <div class="settlement-form-grid">
              <AFormItem field="invoiceAmount" label="已开票金额">
                <AInputNumber v-model="newSettlementProjectForm.invoiceAmount" :min="0" :precision="2" hide-button />
              </AFormItem>
              <AFormItem field="receivedAmount" label="已收款金额">
                <AInputNumber v-model="newSettlementProjectForm.receivedAmount" :min="0" :precision="2" hide-button />
              </AFormItem>
              <AFormItem field="invoiceStatus" label="开票状态">
                <AInput v-model="newSettlementProjectForm.invoiceStatus" placeholder="如：未开票、部分开票、已开票" />
              </AFormItem>
              <AFormItem field="collectionStatus" label="收款状态">
                <AInput v-model="newSettlementProjectForm.collectionStatus" placeholder="如：未收款、部分收款、已结清" />
              </AFormItem>
              <AFormItem class="form-span-2" field="nextAction" label="下一步财务待办">
                <ATextarea v-model="newSettlementProjectForm.nextAction" :auto-size="{ minRows: 3, maxRows: 5 }" placeholder="请输入下一步需要财务或项目负责人处理的真实事项" />
              </AFormItem>
            </div>
          </section>

          <section v-else class="wizard-pane">
            <div class="wizard-pane__head">
              <h3>确认生成结算台账</h3>
              <p>确认后创建真实结算项目；未接入模板服务的自动资料清单不会被虚构。</p>
            </div>
            <div class="wizard-review-list">
              <span v-for="item in newSettlementReviewItems" :key="item.label">
                <em>{{ item.label }}</em>
                <strong>{{ item.value }}</strong>
              </span>
            </div>
          </section>

          <div class="wizard-inline-actions">
            <button type="button" :disabled="newSettlementStepIndex === 0" @click="newSettlementStepIndex -= 1">上一步</button>
            <span>{{ newSettlementStepIndex + 1 }} / {{ settlementWizardSteps.length }}</span>
          </div>
        </AForm>
      </div>
    </AModal>
  </main>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SettlementManagementWizard from '@/components/SettlementManagementWizard.vue'
import SettlementPaymentFlowPanel from '@/components/SettlementPaymentFlowPanel.vue'
import { fetchProjectEvidence, fetchProjectRecords, saveProjectSettlement } from '@/api/projects'
import {
  createSettlementProject,
  fetchSettlementOverviewDashboard,
  fetchSettlementFinanceWorkbench,
  fetchSettlementInvoices,
  fetchSettlementProjects,
  fetchSettlementRetentions,
  type SettlementProjectPayload,
  type SettlementOverviewDashboard,
  type SettlementInvoiceRecord,
  type SettlementProjectLedgerItem,
  type SettlementRetentionRecord,
  type SettlementWorkbenchItem,
} from '@/api/settlementFinance'
import { useAuthStore } from '@/store/auth'
import type { ProjectEvidenceFile, ProjectRecord, ProjectSettlement } from '@/types'
import { amountToChineseUpper, formatWan } from '@/utils/format'

type ViewKey = 'overview' | 'workbench' | 'ledger' | 'invoice' | 'payment' | 'documents' | 'retention'
type SettlementWizardStepKey = 'project' | 'contract' | 'stage' | 'template' | 'review'
type SettlementDocumentGroup = {
  key: string
  projectId: string
  projectName: string
  projectCode: string
  files: ProjectEvidenceFile[]
  categories: { label: string; count: number }[]
}

const views: { key: ViewKey; label: string }[] = [
  { key: 'ledger', label: '项目结算台账' },
  { key: 'payment', label: '付款申请与到账' },
  { key: 'workbench', label: '财务待办' },
  { key: 'invoice', label: '发票管理' },
  { key: 'documents', label: '结算资料管理' },
  { key: 'retention', label: '质保金管理' },
  { key: 'overview', label: '结算管理概览' },
]

const route = useRoute()
const router = useRouter()
// The ledger is the operational entry point: it exposes the real empty state and
// gives finance a direct path to include an existing project in settlement management.
const activeView = ref<ViewKey>('ledger')
const ledgerStatusFilter = ref('all')
const authStore = useAuthStore()
const canManageSettlementFinance = computed(() => authStore.isEditor)
const overviewDashboard = ref<SettlementOverviewDashboard | null>(null)
const workbenchItems = ref<SettlementWorkbenchItem[]>([])
const settlementProjects = ref<SettlementProjectLedgerItem[]>([])
const settlementDocuments = ref<ProjectEvidenceFile[]>([])
const invoices = ref<SettlementInvoiceRecord[]>([])
const retentions = ref<SettlementRetentionRecord[]>([])
const existingProjects = ref<ProjectRecord[]>([])
const unavailableEndpoints = ref<string[]>([])
const formMessage = ref('')
const formMessageType = ref<'info' | 'success' | 'error'>('info')
const existingSettlementDialog = reactive({ visible: false, saving: false })
const newSettlementProjectDialog = reactive({ visible: false, saving: false })
const settlementStatusOptions = [
  { label: '未开始', value: '未开始' },
  { label: '已付款（部分未结清）', value: '已付款（部分未结清）' },
  { label: '已结清', value: '已结清' },
]
const settlementWizardSteps: { key: SettlementWizardStepKey; label: string; hint: string }[] = [
  { key: 'project', label: '项目主档案', hint: '先带出基础信息' },
  { key: 'contract', label: '合同与条款', hint: '确认金额和付款约定' },
  { key: 'stage', label: '结算阶段', hint: '问答判断当前状态' },
  { key: 'template', label: '节点与资料', hint: '生成待办和资料清单' },
  { key: 'review', label: '确认生成', hint: '写入真实台账' },
]
const existingSettlementStepIndex = ref(0)
const newSettlementStepIndex = ref(0)
const existingSettlementForm = reactive<Partial<ProjectSettlement>>({
  projectId: '',
  settlementName: '',
  settlementStatus: '未开始',
  settlementType: '',
  applyAmount: undefined,
  approvedAmount: undefined,
  paidAmount: undefined,
  applyDate: '',
  expectedPayDate: '',
  paidDate: '',
  remark: '',
})
const newSettlementProjectForm = reactive<SettlementProjectPayload>({
  projectName: '',
  projectCode: '',
  ownerUnit: '',
  constructionUnit: '',
  managerName: '',
  contractAmount: undefined,
  submittedAmount: undefined,
  finalAuditedAmount: undefined,
  invoiceAmount: undefined,
  receivedAmount: undefined,
  retentionAmount: undefined,
  settlementStatus: '未开始',
  invoiceStatus: '',
  collectionStatus: '',
  nextPaymentNode: '',
  nextAction: '',
})
const existingSettlementStepKey = computed(() => settlementWizardSteps[existingSettlementStepIndex.value]?.key || 'project')
const newSettlementStepKey = computed(() => settlementWizardSteps[newSettlementStepIndex.value]?.key || 'project')
const existingWizardPrimaryText = computed(() => existingSettlementStepKey.value === 'review' ? '确认生成结算台账' : '下一步')
const newWizardPrimaryText = computed(() => newSettlementStepKey.value === 'review' ? '创建结算项目' : '下一步')
const selectedExistingProject = computed(() => existingProjects.value.find((item) => item.id === existingSettlementForm.projectId) || null)
const selectedProjectFacts = computed(() => {
  const project = selectedExistingProject.value
  return [
    { label: '项目名称', value: project?.projectName || '请选择项目' },
    { label: '项目编号', value: project?.projectCode || '-' },
    { label: '建设单位', value: project?.ownerUnit || '-' },
    { label: '施工单位', value: project?.constructionUnit || '-' },
    { label: '负责人', value: project?.managerName || '-' },
    { label: '项目状态', value: project?.projectStatusText || project?.projectStatus || '-' },
  ]
})
const existingSettlementReviewItems = computed(() => [
  { label: '项目', value: selectedExistingProject.value?.projectName || '-' },
  { label: '建设单位', value: selectedExistingProject.value?.ownerUnit || '-' },
  { label: '施工单位', value: selectedExistingProject.value?.constructionUnit || '-' },
  { label: '结算名称', value: existingSettlementForm.settlementName || '-' },
  { label: '结算状态', value: existingSettlementForm.settlementStatus || '-' },
  { label: '申报金额', value: formatNullableMoney(existingSettlementForm.applyAmount) },
  { label: '核定金额', value: formatNullableMoney(existingSettlementForm.approvedAmount) },
  { label: '已付款金额', value: formatNullableMoney(existingSettlementForm.paidAmount) },
])
const newSettlementReviewItems = computed(() => [
  { label: '项目', value: newSettlementProjectForm.projectName || '-' },
  { label: '建设/付款单位', value: newSettlementProjectForm.ownerUnit || '-' },
  { label: '施工单位', value: newSettlementProjectForm.constructionUnit || '-' },
  { label: '合同金额', value: formatNullableMoney(newSettlementProjectForm.contractAmount) },
  { label: '送审金额', value: formatNullableMoney(newSettlementProjectForm.submittedAmount) },
  { label: '审定金额', value: formatNullableMoney(newSettlementProjectForm.finalAuditedAmount) },
  { label: '已开票金额', value: formatNullableMoney(newSettlementProjectForm.invoiceAmount) },
  { label: '已收款金额', value: formatNullableMoney(newSettlementProjectForm.receivedAmount) },
  { label: '结算状态', value: newSettlementProjectForm.settlementStatus || '-' },
  { label: '下一步动作', value: newSettlementProjectForm.nextAction || '-' },
])

const loadMessage = computed(() => {
  if (unavailableEndpoints.value.length === 0) return ''
  return `以下结算财务接口暂未接入或无权限访问：${unavailableEndpoints.value.join('、')}`
})
const overviewMetrics = computed(() => [
  metric('合同总金额', overviewDashboard.value?.contractTotalAmount),
  metric('审定总金额', overviewDashboard.value?.auditedTotalAmount),
  metric('已开票金额', overviewDashboard.value?.invoiceTotalAmount),
  metric('已收款金额', overviewDashboard.value?.receivedTotalAmount),
  metric('待收款金额', overviewDashboard.value?.receivableAmount),
  metric('逾期未收款', overviewDashboard.value?.overdueReceivableAmount),
  metric('质保金余额', overviewDashboard.value?.retentionAmount),
  metric('可申请收款金额', overviewDashboard.value?.collectibleAmount),
])

const settlementStatusStats = computed(() => {
  const map = new Map<string, number>()
  settlementProjects.value.forEach((item) => {
    const status = item.settlementStatus || '状态待补充'
    map.set(status, (map.get(status) || 0) + 1)
  })
  return Array.from(map.entries()).map(([status, count]) => ({ status, count }))
})

const ledgerStatusOptions = computed(() => {
  const counts = new Map<string, number>()
  settlementProjects.value.forEach((item) => {
    const status = item.settlementStatus || '状态待补充'
    counts.set(status, (counts.get(status) || 0) + 1)
  })
  return [
    { value: 'all', label: '全部', count: settlementProjects.value.length },
    ...Array.from(counts.entries()).map(([status, count]) => ({ value: status, label: status, count })),
  ]
})

const visibleSettlementProjects = computed(() => {
  if (ledgerStatusFilter.value === 'all') return settlementProjects.value
  return settlementProjects.value.filter((item) => (item.settlementStatus || '状态待补充') === ledgerStatusFilter.value)
})

const settlementDocumentGroups = computed<SettlementDocumentGroup[]>(() => {
  const projects = settlementProjects.value
  if (projects.length === 0) return []
  const byProjectId = new Map<string, SettlementProjectLedgerItem>()
  const byProjectName = new Map<string, SettlementProjectLedgerItem>()
  projects.forEach((item) => {
    const id = String(item.projectId || item.id || '')
    if (id) byProjectId.set(id, item)
    if (item.projectName) byProjectName.set(item.projectName, item)
  })
  const groups = new Map<string, SettlementDocumentGroup>()
  settlementDocuments.value.forEach((file) => {
    const project = byProjectId.get(String(file.projectId || '')) || byProjectName.get(file.projectName || '')
    if (!project) return
    const projectId = String(project.projectId || project.id || file.projectId || '')
    if (!projectId) return
    const key = projectId
    const group = groups.get(key) || {
      key,
      projectId,
      projectName: project.projectName || file.projectName || '项目名称待补充',
      projectCode: project.projectCode || file.projectCode || '',
      files: [],
      categories: [],
    }
    group.files.push(file)
    groups.set(key, group)
  })
  return Array.from(groups.values()).map((group) => {
    const categoryCounts = new Map<string, number>()
    group.files.forEach((file) => {
      const label = file.categoryName || '项目资料'
      categoryCounts.set(label, (categoryCounts.get(label) || 0) + 1)
    })
    group.categories = Array.from(categoryCounts.entries()).map(([label, count]) => ({ label, count }))
    return group
  })
})

const settlementDocumentCount = computed(() => settlementDocumentGroups.value.reduce((total, group) => total + group.files.length, 0))

const projectSelectOptions = computed(() => existingProjects.value.map((item) => ({
  label: `${item.projectName || '未命名项目'}${item.projectCode ? ` · ${item.projectCode}` : ''}`,
  value: item.id,
})))

const DataTable = defineComponent({
  name: 'DataTable',
  props: { columns: { type: Array<string>, required: true } },
  setup(props, { slots }) {
    return () =>
      h('div', { class: 'data-table' }, [
        h('div', { class: 'table-head table-row--six' }, props.columns.map((column) => h('span', column))),
        slots.default?.(),
      ])
  },
})

const EmptyBlock = defineComponent({
  name: 'EmptyBlock',
  props: { title: { type: String, required: true }, text: { type: String, required: true } },
  setup(props) {
    return () => h('div', { class: 'empty-state' }, [h('strong', props.title), h('span', props.text)])
  },
})

const MoneyCell = defineComponent({
  name: 'MoneyCell',
  props: { amount: { type: Number, default: undefined } },
  setup(props) {
    return () =>
      h('span', { class: 'money-cell' }, [
        h('strong', formatNullableMoney(props.amount)),
        props.amount === undefined || props.amount === null ? null : h('small', amountToChineseUpper(props.amount)),
      ])
  },
})

function metric(label: string, value?: number) {
  if (value === undefined || value === null) return { label, value: '未接入', hint: '等待结算财务接口' }
  return { label, value: formatWan(value), hint: amountToChineseUpper(value) }
}

function formatNullableMoney(value?: number) {
  if (value === undefined || value === null) return '-'
  return formatWan(value)
}

function formatRatio(value?: number) {
  if (value === undefined || value === null) return '-'
  return `${Number(value).toLocaleString('zh-CN', { maximumFractionDigits: 2 })}%`
}

function settlementStatusHint(value: string) {
  if (value === '已结清') return '已完成全部应收/应付和票据资料'
  if (value.includes('部分')) return '已发生付款，但仍存在未结清金额或资料'
  return '尚未形成完整付款或结算记录'
}

function isViewKey(value: unknown): value is ViewKey {
  return typeof value === 'string' && views.some((item) => item.key === value)
}

function syncViewFromRoute() {
  const routeView = route.query.view
  if (isViewKey(routeView)) activeView.value = routeView
}

function setActiveView(view: ViewKey) {
  activeView.value = view
  const nextQuery = { ...route.query, view }
  router.replace({ path: '/finance', query: nextQuery }).catch(() => {})
}

function openSettlementProject(projectId: string) {
  if (!projectId) return
  router.push({ path: '/project-management', query: { view: 'ledger', projectId } })
}

function handleSidebarAction(event: Event) {
  const action = (event as CustomEvent<{ action?: string }>).detail?.action
  if (action === 'finance:add-existing-project') {
    openExistingProjectSettlement()
    return
  }
  if (action === 'finance:new-settlement-project') {
    openNewSettlementProject()
  }
}

async function readEndpoint<T>(label: string, loader: () => Promise<T>, fallback: T) {
  try {
    return await loader()
  } catch {
    unavailableEndpoints.value.push(label)
    return fallback
  }
}

function setFormMessage(type: typeof formMessageType.value, message: string) {
  formMessageType.value = type
  formMessage.value = message
}

function resetExistingSettlementForm() {
  existingSettlementStepIndex.value = 0
  Object.assign(existingSettlementForm, {
    projectId: '',
    settlementName: '',
    settlementStatus: '未开始',
    settlementType: '',
    applyAmount: undefined,
    approvedAmount: undefined,
    paidAmount: undefined,
    applyDate: '',
    expectedPayDate: '',
    paidDate: '',
    remark: '',
  })
}

function resetNewSettlementProjectForm() {
  newSettlementStepIndex.value = 0
  Object.assign(newSettlementProjectForm, {
    projectName: '',
    projectCode: '',
    ownerUnit: '',
    constructionUnit: '',
    managerName: '',
    contractAmount: undefined,
    provisionalSum: undefined,
    estimatedPrice: undefined,
    submittedAmount: undefined,
    firstAuditAmount: undefined,
    secondAuditAmount: undefined,
    finalAuditedAmount: undefined,
    invoiceAmount: undefined,
    receivedAmount: undefined,
    retentionAmount: undefined,
    settlementStatus: '未开始',
    invoiceStatus: '',
    collectionStatus: '',
    nextPaymentNode: '',
    nextAction: '',
  })
}

watch(
  () => existingSettlementForm.projectId,
  () => {
    const project = selectedExistingProject.value
    if (!project) return
    if (!existingSettlementForm.settlementName) existingSettlementForm.settlementName = `${project.projectName}结算`
    if (!existingSettlementForm.settlementType) existingSettlementForm.settlementType = '项目结算'
    if (existingSettlementForm.applyAmount === undefined || existingSettlementForm.applyAmount === null) {
      existingSettlementForm.applyAmount = project.submittedAmount || project.contractAmount || undefined
    }
    if (existingSettlementForm.paidAmount === undefined || existingSettlementForm.paidAmount === null) {
      existingSettlementForm.paidAmount = project.paidAmount || undefined
    }
  },
)

function openExistingProjectSettlement() {
  if (!canManageSettlementFinance.value) {
    setFormMessage('error', '当前账号只有查看权限，不能维护结算信息。')
    return
  }
  resetExistingSettlementForm()
  setFormMessage('info', existingProjects.value.length ? '' : '正在读取项目列表；如果项目列表接口未接入，无法给已有项目增加结算信息。')
  existingSettlementDialog.visible = true
}

function openNewSettlementProject() {
  openExistingProjectSettlement()
}

function cleanPayload<T extends Record<string, unknown>>(payload: T) {
  return Object.fromEntries(
    Object.entries(payload).filter(([, value]) => value !== '' && value !== undefined && value !== null)
  ) as Partial<T>
}

async function submitExistingProjectSettlement() {
  if (!canManageSettlementFinance.value) {
    setFormMessage('error', '当前账号只有查看权限，不能保存结算信息。')
    return
  }
  if (!existingSettlementForm.projectId) {
    setFormMessage('error', '请先选择一个已有项目。')
    return
  }
  if (!String(existingSettlementForm.settlementName || '').trim()) {
    setFormMessage('error', '请填写结算名称。')
    return
  }
  existingSettlementDialog.saving = true
  try {
    const projectId = String(existingSettlementForm.projectId)
    await saveProjectSettlement(projectId, cleanPayload({
      settlementName: existingSettlementForm.settlementName,
      settlementStatus: existingSettlementForm.settlementStatus,
      settlementType: existingSettlementForm.settlementType,
      applyAmount: existingSettlementForm.applyAmount,
      approvedAmount: existingSettlementForm.approvedAmount,
      paidAmount: existingSettlementForm.paidAmount,
      applyDate: existingSettlementForm.applyDate,
      expectedPayDate: existingSettlementForm.expectedPayDate,
      paidDate: existingSettlementForm.paidDate,
      remark: existingSettlementForm.remark,
    }))
    existingSettlementDialog.visible = false
    setFormMessage('success', '已保存到该项目的真实结算信息。')
    await refresh()
  } catch (error) {
    setFormMessage('error', error instanceof Error ? error.message : '保存结算信息失败')
  } finally {
    existingSettlementDialog.saving = false
  }
}

function validateExistingSettlementStep() {
  if (existingSettlementStepKey.value === 'project' && !existingSettlementForm.projectId) {
    setFormMessage('error', '请先从项目管理中选择一个已有项目。')
    return false
  }
  if (existingSettlementStepKey.value === 'contract' && !String(existingSettlementForm.settlementName || '').trim()) {
    setFormMessage('error', '请填写本次结算名称。')
    return false
  }
  setFormMessage('info', '')
  return true
}

async function handleExistingSettlementWizardConfirm() {
  if (!validateExistingSettlementStep()) return
  if (existingSettlementStepKey.value !== 'review') {
    existingSettlementStepIndex.value = Math.min(existingSettlementStepIndex.value + 1, settlementWizardSteps.length - 1)
    return
  }
  await submitExistingProjectSettlement()
}

async function submitNewSettlementProject() {
  if (!canManageSettlementFinance.value) {
    setFormMessage('error', '当前账号只有查看权限，不能新增结算项目。')
    return
  }
  if (!String(newSettlementProjectForm.projectName || '').trim()) {
    setFormMessage('error', '请填写项目名称。')
    return
  }
  newSettlementProjectDialog.saving = true
  try {
    await createSettlementProject(cleanPayload({ ...newSettlementProjectForm }))
    newSettlementProjectDialog.visible = false
    setFormMessage('success', '已提交新增结算项目。')
    await refresh()
  } catch (error) {
    setFormMessage('error', error instanceof Error ? error.message : '新增结算项目失败；请确认结算中心创建接口已接入。')
  } finally {
    newSettlementProjectDialog.saving = false
  }
}

function validateNewSettlementStep() {
  if (newSettlementStepKey.value === 'project' && !String(newSettlementProjectForm.projectName || '').trim()) {
    setFormMessage('error', '请填写项目名称。')
    return false
  }
  setFormMessage('info', '')
  return true
}

async function handleNewSettlementWizardConfirm() {
  if (!validateNewSettlementStep()) return
  if (newSettlementStepKey.value !== 'review') {
    newSettlementStepIndex.value = Math.min(newSettlementStepIndex.value + 1, settlementWizardSteps.length - 1)
    return
  }
  await submitNewSettlementProject()
}

async function refresh() {
  unavailableEndpoints.value = []
  const [overview, workbench, projects, invoiceList, retentionList, projectList, documents] = await Promise.all([
    readEndpoint('结算管理概览', fetchSettlementOverviewDashboard, null),
    readEndpoint('财务工作台', fetchSettlementFinanceWorkbench, []),
    readEndpoint('项目结算台账', fetchSettlementProjects, []),
    readEndpoint('发票管理', fetchSettlementInvoices, []),
    readEndpoint('质保金管理', fetchSettlementRetentions, []),
    readEndpoint('已有项目列表', () => fetchProjectRecords({ page: 1, pageSize: 200 }).then((res) => res.data), []),
    readEndpoint('结算资料', fetchProjectEvidence, []),
  ])
  overviewDashboard.value = overview
  workbenchItems.value = workbench
  settlementProjects.value = projects
  invoices.value = invoiceList
  retentions.value = retentionList
  existingProjects.value = projectList
  settlementDocuments.value = documents
}

watch(() => route.query.view, syncViewFromRoute, { immediate: true })

onMounted(() => {
  window.addEventListener('jiqing-sidebar-action', handleSidebarAction)
  refresh()
})

onBeforeUnmount(() => {
  window.removeEventListener('jiqing-sidebar-action', handleSidebarAction)
})
</script>

<style scoped>
.settlement-center {
  display: grid;
  gap: 16px;
  color: var(--premium-ink);
}

.settlement-hero,
.view-panel,
.metric-card,
.sub-panel {
  background: var(--premium-glass);
  border: 1px solid var(--premium-line);
  border-radius: var(--premium-radius);
  box-shadow: var(--premium-shadow-soft);
  backdrop-filter: blur(18px) saturate(145%);
  -webkit-backdrop-filter: blur(18px) saturate(145%);
}

.settlement-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.eyebrow {
  margin: 0 0 6px;
  color: var(--premium-blue);
  font-size: 12px;
  font-weight: 700;
}

h1,
h2,
h3 {
  margin: 0;
}

h1 {
  font-size: 26px;
  line-height: 1.2;
}

.settlement-hero span,
.panel-title span,
.metric-card em,
small,
.empty-state span,
.system-note {
  color: var(--premium-muted);
}

.primary-action,
.secondary-action,
.ghost-action,
.empty-row--action button {
  height: 36px;
  padding: 0 16px;
  border-radius: var(--premium-radius-compact);
  cursor: pointer;
}

.primary-action {
  border: 0;
  color: #fff;
  background: linear-gradient(135deg, #2f7cff, #165dff 64%, #0f43d6);
  box-shadow: 0 10px 22px rgba(22, 93, 255, 0.18);
}

.secondary-action,
.ghost-action,
.empty-row--action button {
  color: var(--premium-blue);
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(22, 93, 255, 0.24);
}

.ghost-action {
  color: var(--premium-muted);
  border-color: rgba(128, 158, 210, 0.24);
}

.permission-pill {
  display: inline-flex;
  align-items: center;
  height: 32px;
  padding: 0 12px;
  color: var(--premium-muted);
  background: rgba(255, 255, 255, 0.58);
  border: 1px solid rgba(128, 158, 210, 0.22);
  border-radius: var(--premium-radius-compact);
  font-size: 12px;
}

.view-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 4px;
  background: rgba(255, 255, 255, 0.54);
  border: 1px solid rgba(128, 158, 210, 0.22);
  border-radius: var(--premium-radius);
}

.view-tabs button {
  height: 32px;
  padding: 0 12px;
  border: 0;
  border-radius: var(--premium-radius-compact);
  color: var(--premium-muted);
  background: transparent;
  cursor: pointer;
}

.view-tabs button.active {
  color: var(--premium-blue);
  background: #fff;
  box-shadow: 0 6px 14px rgba(54, 95, 160, 0.08);
  font-weight: 700;
}

.view-panel,
.sub-panel {
  padding: 16px;
}

.panel-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.metric-grid {
  display: grid;
  gap: 12px;
}

.metric-grid--wide {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.metric-card {
  display: grid;
  gap: 6px;
  min-width: 0;
  padding: 16px;
}

.metric-card strong {
  overflow-wrap: anywhere;
  font-size: 22px;
}

.metric-card em {
  overflow-wrap: anywhere;
  font-size: 12px;
  font-style: normal;
}

.board-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.todo-list,
.status-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.todo-list button,
.status-list span {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px;
  color: inherit;
  text-align: left;
  background: rgba(255, 255, 255, 0.52);
  border: 1px solid rgba(128, 158, 210, 0.2);
  border-radius: var(--premium-radius-compact);
}

.status-list em {
  color: var(--premium-blue);
  font-style: normal;
  font-weight: 800;
}

.data-table {
  overflow: hidden;
  border: 1px solid rgba(128, 158, 210, 0.22);
  border-radius: var(--premium-radius);
}

.settlement-ledger__summary {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  flex-shrink: 0;
  padding: 8px 12px;
  color: var(--premium-muted);
  background: rgba(240, 247, 255, 0.72);
  border: 1px solid rgba(128, 158, 210, 0.2);
  border-radius: var(--premium-radius-compact);
  font-size: 12px;
}

.settlement-ledger__summary strong {
  color: var(--premium-blue);
  font-size: 18px;
}

.settlement-ledger__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
  padding: 12px 14px;
  background: rgba(246, 250, 255, 0.78);
  border: 1px solid rgba(128, 158, 210, 0.18);
  border-radius: var(--premium-radius-compact);
}

.settlement-ledger__toolbar-title {
  display: grid;
  gap: 4px;
  min-width: 180px;
}

.settlement-ledger__toolbar-title span {
  color: var(--premium-muted);
  font-size: 12px;
}

.settlement-ledger__filters {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px;
}

.settlement-ledger__filters > span {
  margin-right: 4px;
  color: var(--premium-muted);
  font-size: 12px;
}

.settlement-ledger__filters button {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 30px;
  padding: 0 10px;
  color: var(--premium-muted);
  background: rgba(255, 255, 255, .72);
  border: 1px solid rgba(128, 158, 210, .2);
  border-radius: 999px;
  cursor: pointer;
}

.settlement-ledger__filters button b {
  color: inherit;
  font-size: 11px;
  font-weight: 700;
}

.settlement-ledger__filters button:hover,
.settlement-ledger__filters button.active {
  color: var(--premium-blue);
  background: rgba(231, 240, 255, .92);
  border-color: rgba(22, 93, 255, .3);
}

.settlement-ledger {
  overflow-x: auto;
  border: 1px solid rgba(128, 158, 210, 0.22);
  border-radius: var(--premium-radius);
}

.settlement-ledger__head,
.settlement-ledger__row,
.settlement-ledger__group-head {
  display: grid;
  grid-template-columns: minmax(220px, 1.45fr) minmax(180px, 1.18fr) minmax(180px, 1.1fr) minmax(170px, 1.05fr) minmax(145px, .9fr) minmax(180px, 1.15fr);
  gap: 14px;
  min-width: 1180px;
  align-items: start;
}

.settlement-ledger__group-head {
  padding: 10px 14px 8px;
  color: var(--premium-blue);
  background: rgba(232, 241, 255, 0.92);
  border-bottom: 1px solid rgba(128, 158, 210, 0.18);
}

.settlement-ledger__group-head > span {
  display: grid;
  grid-column: span 2;
  gap: 2px;
  min-width: 0;
  padding-right: 12px;
  border-right: 1px solid rgba(128, 158, 210, 0.2);
  font-size: 12px;
  font-weight: 800;
}

.settlement-ledger__group-head > span:last-child {
  border-right: 0;
}

.settlement-ledger__group-head small {
  color: var(--premium-muted);
  font-size: 11px;
  font-weight: 500;
}

.settlement-ledger__head {
  padding: 12px 14px;
  color: #385071;
  background: rgba(240, 247, 255, 0.78);
  font-size: 12px;
  font-weight: 700;
}

.settlement-ledger__head > span:first-child,
.settlement-ledger__row > :first-child {
  position: sticky;
  left: 0;
  z-index: 1;
  box-shadow: 10px 0 14px -14px rgba(26, 56, 102, .6);
}

.settlement-ledger__head > span:first-child {
  background: rgba(240, 247, 255, .98);
}

.settlement-ledger__row > :first-child {
  background: rgba(255, 255, 255, .98);
}

.settlement-ledger__row {
  padding: 16px 14px;
  background: rgba(255, 255, 255, 0.52);
  border-top: 1px solid rgba(128, 158, 210, 0.18);
  transition: background .18s ease;
}

.settlement-ledger__row:hover {
  background: rgba(246, 250, 255, 0.94);
}

.settlement-ledger__project,
.settlement-ledger__parties,
.settlement-ledger__status,
.settlement-ledger__next-action,
.settlement-ledger__money-stack {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.settlement-ledger__project strong,
.settlement-ledger__parties strong,
.settlement-ledger__next-action strong {
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.settlement-ledger__project small,
.settlement-ledger__parties small,
.settlement-ledger__status small,
.settlement-ledger__next-action small {
  color: var(--premium-muted);
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.settlement-ledger__money-stack > small {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
  color: var(--premium-muted);
  line-height: 1.35;
}

.settlement-ledger__money-stack em {
  flex-shrink: 0;
  color: var(--premium-muted);
  font-size: 11px;
  font-style: normal;
}

.settlement-ledger__money-stack strong {
  color: var(--premium-ink);
  font-size: 13px;
  text-align: right;
  overflow-wrap: anywhere;
}

.settlement-ledger__status .status-pill {
  justify-self: start;
}

.settlement-ledger__empty {
  display: grid;
  place-items: center;
  gap: 10px;
  min-height: 150px;
  padding: 24px;
  color: var(--premium-muted);
  text-align: center;
  border-top: 1px solid rgba(128, 158, 210, 0.18);
}

.settlement-ledger__empty button {
  height: 34px;
  padding: 0 14px;
  color: var(--premium-blue);
  background: rgba(255, 255, 255, .82);
  border: 1px solid rgba(22, 93, 255, .24);
  border-radius: var(--premium-radius-compact);
  cursor: pointer;
}

.settlement-documents__empty {
  max-width: 720px;
}

.settlement-document-groups {
  display: grid;
  gap: 14px;
}

.settlement-document-group {
  overflow: hidden;
  background: rgba(255, 255, 255, .56);
  border: 1px solid rgba(128, 158, 210, .22);
  border-radius: var(--premium-radius);
}

.settlement-document-group__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  background: rgba(240, 247, 255, .74);
  border-bottom: 1px solid rgba(128, 158, 210, .18);
}

.settlement-document-group__head > div {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.settlement-document-group__head strong,
.settlement-document-group__head small {
  overflow-wrap: anywhere;
}

.settlement-document-group__head small {
  color: var(--premium-muted);
}

.settlement-document-group__head button {
  flex-shrink: 0;
  height: 32px;
  padding: 0 12px;
  color: var(--premium-blue);
  background: rgba(255, 255, 255, .82);
  border: 1px solid rgba(22, 93, 255, .24);
  border-radius: var(--premium-radius-compact);
  cursor: pointer;
}

.settlement-document-group__categories {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  padding: 12px 16px 4px;
}

.settlement-document-group__categories span {
  padding: 4px 8px;
  color: var(--premium-muted);
  background: rgba(128, 158, 210, .11);
  border-radius: 999px;
  font-size: 12px;
}

.settlement-document-group__categories b {
  margin-left: 3px;
  color: var(--premium-blue);
}

.settlement-document-list {
  display: grid;
  gap: 0;
  margin: 0;
  padding: 6px 16px 10px;
  list-style: none;
}

.settlement-document-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 11px 0;
  border-bottom: 1px solid rgba(128, 158, 210, .14);
}

.settlement-document-list li:last-child {
  border-bottom: 0;
}

.settlement-document-list__main {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.settlement-document-list__main strong,
.settlement-document-list__main small {
  overflow-wrap: anywhere;
}

.settlement-document-list__main small {
  color: var(--premium-muted);
  font-size: 12px;
}

.settlement-document-list li > em {
  flex-shrink: 0;
  padding: 4px 8px;
  color: var(--premium-muted);
  background: rgba(128, 158, 210, .11);
  border-radius: 6px;
  font-size: 12px;
  font-style: normal;
}

.table-row--six {
  display: grid;
  grid-template-columns: minmax(180px, 1.25fr) minmax(150px, 1fr) minmax(120px, .9fr) minmax(130px, .9fr) minmax(120px, .85fr) minmax(130px, .85fr);
  gap: 12px;
  align-items: center;
}

.table-head {
  padding: 12px 14px;
  color: #385071;
  background: rgba(240, 247, 255, 0.7);
  font-size: 12px;
  font-weight: 700;
}

.table-row {
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.48);
  border-top: 1px solid rgba(128, 158, 210, 0.18);
}

.table-row > span,
.money-cell {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.table-row strong,
.table-row small,
.money-cell strong,
.money-cell small {
  overflow-wrap: anywhere;
}

.status-pill {
  width: max-content;
  padding: 4px 8px;
  color: var(--premium-muted);
  background: rgba(128, 158, 210, 0.14);
  border-radius: 6px;
  font-style: normal;
  font-weight: 700;
}

.status-pill.danger {
  color: #c9372c;
  background: rgba(245, 63, 63, 0.1);
}

.empty-state {
  display: grid;
  place-items: center;
  gap: 8px;
  min-height: 140px;
  padding: 20px;
  text-align: center;
  background: rgba(255, 255, 255, 0.48);
  border: 1px dashed rgba(128, 158, 210, 0.3);
  border-radius: var(--premium-radius);
}

.empty-row {
  padding: 32px 14px;
  color: var(--premium-muted);
  text-align: center;
  background: rgba(255, 255, 255, 0.48);
  border-top: 1px solid rgba(128, 158, 210, 0.18);
}

.empty-row--action {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.system-note {
  margin: 0;
  padding: 12px 14px;
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(255, 176, 32, 0.35);
  border-radius: var(--premium-radius);
}

.system-note.danger {
  color: #c9372c;
  border-color: rgba(245, 63, 63, 0.32);
}

.system-note.success {
  color: #067a46;
  border-color: rgba(0, 168, 112, 0.32);
}

.settlement-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 16px;
}

.form-span-2 {
  grid-column: 1 / -1;
}

.settlement-form-grid :deep(.arco-form-item) {
  margin-bottom: 0;
}

.settlement-form-grid :deep(.arco-input-wrapper),
.settlement-form-grid :deep(.arco-input-number),
.settlement-form-grid :deep(.arco-select-view),
.settlement-form-grid :deep(.arco-textarea-wrapper) {
  border-radius: var(--premium-radius-compact);
}

.settlement-wizard {
  display: grid;
  grid-template-columns: 250px minmax(0, 1fr);
  gap: 18px;
  min-height: 520px;
}

.settlement-wizard__steps {
  display: grid;
  align-content: start;
  gap: 10px;
  padding: 12px;
  border: 1px solid rgba(128, 158, 210, 0.18);
  border-radius: var(--premium-radius);
  background: linear-gradient(180deg, rgba(248, 252, 255, 0.82), rgba(255, 255, 255, 0.58));
}

.settlement-wizard__steps button {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr);
  gap: 4px 10px;
  width: 100%;
  padding: 12px;
  border: 1px solid transparent;
  border-radius: var(--premium-radius-compact);
  color: var(--premium-muted);
  background: transparent;
  text-align: left;
  cursor: pointer;
}

.settlement-wizard__steps button.active,
.settlement-wizard__steps button.done {
  border-color: rgba(22, 93, 255, 0.18);
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 10px 22px rgba(61, 105, 185, 0.06);
}

.settlement-wizard__steps button span {
  grid-row: 1 / span 2;
  width: 30px;
  height: 30px;
  display: inline-grid;
  place-items: center;
  border-radius: 999px;
  background: rgba(22, 93, 255, 0.08);
  color: var(--premium-blue);
  font-weight: 800;
}

.settlement-wizard__steps button.active span {
  color: #fff;
  background: linear-gradient(135deg, #2f7cff, #165dff);
}

.settlement-wizard__steps strong {
  color: var(--premium-ink);
}

.settlement-wizard__steps em {
  font-size: 12px;
  font-style: normal;
}

.settlement-wizard__body {
  min-width: 0;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 14px;
}

.wizard-pane {
  display: grid;
  align-content: start;
  gap: 16px;
  min-width: 0;
  padding: 16px;
  border: 1px solid rgba(128, 158, 210, 0.18);
  border-radius: var(--premium-radius);
  background: rgba(255, 255, 255, 0.56);
}

.wizard-pane__head {
  display: grid;
  gap: 5px;
}

.wizard-pane__head h3 {
  font-size: 20px;
}

.wizard-pane__head p {
  margin: 0;
  color: var(--premium-muted);
}

.auto-info-grid,
.generated-preview-grid,
.wizard-review-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.auto-info-grid article,
.generated-preview-grid article,
.wizard-review-list span {
  display: grid;
  gap: 6px;
  min-width: 0;
  padding: 12px;
  border: 1px solid rgba(128, 158, 210, 0.16);
  border-radius: var(--premium-radius-compact);
  background: rgba(248, 251, 255, 0.72);
}

.auto-info-grid article.wide {
  grid-column: span 2;
}

.auto-info-grid span,
.wizard-review-list em {
  color: var(--premium-muted);
  font-size: 12px;
  font-style: normal;
}

.auto-info-grid strong,
.generated-preview-grid strong,
.wizard-review-list strong {
  min-width: 0;
  color: var(--premium-ink);
  overflow-wrap: anywhere;
}

.generated-preview-grid span {
  color: var(--premium-muted);
  line-height: 1.55;
}

.wizard-choice-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.wizard-choice-grid button {
  display: grid;
  gap: 8px;
  min-height: 92px;
  padding: 14px;
  border: 1px solid rgba(128, 158, 210, 0.18);
  border-radius: var(--premium-radius-compact);
  background: rgba(255, 255, 255, 0.72);
  text-align: left;
  cursor: pointer;
}

.wizard-choice-grid button.active {
  border-color: rgba(22, 93, 255, 0.35);
  background: rgba(235, 243, 255, 0.9);
  box-shadow: 0 10px 22px rgba(22, 93, 255, 0.08);
}

.wizard-choice-grid span {
  color: var(--premium-muted);
  line-height: 1.5;
}

.wizard-inline-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.wizard-inline-actions button {
  height: 34px;
  padding: 0 14px;
  border: 1px solid rgba(128, 158, 210, 0.3);
  border-radius: var(--premium-radius-compact);
  background: rgba(255, 255, 255, 0.72);
  color: var(--premium-ink);
  cursor: pointer;
}

.wizard-inline-actions button:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}

.wizard-inline-actions span {
  color: var(--premium-muted);
  font-size: 12px;
}

@media (max-width: 1180px) {
  .metric-grid--wide,
  .board-grid,
  .auto-info-grid,
  .generated-preview-grid,
  .wizard-review-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .table-row--six {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .settlement-hero,
  .panel-title,
  .hero-actions,
  .settlement-ledger__toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .settlement-ledger__filters {
    justify-content: flex-start;
  }

  .metric-grid--wide,
  .board-grid,
  .table-row--six,
  .settlement-form-grid,
  .settlement-wizard,
  .auto-info-grid,
  .generated-preview-grid,
  .wizard-review-list,
  .wizard-choice-grid {
    grid-template-columns: 1fr;
  }

  .form-span-2 {
    grid-column: auto;
  }
}
</style>

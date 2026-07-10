<template>
  <main class="business-workbench bidding-dashboard">
    <header class="business-head">
      <div>
        <p class="eyebrow">招投标业务工作台</p>
        <h1>机会发现与开标预测</h1>
        <span>当前模块只展示真实采集、真实开标记录和真实配置数据；未接入的数据保持为空。</span>
      </div>
      <button class="primary-action" type="button" @click="refresh">刷新数据</button>
    </header>

    <section class="metric-grid">
      <article v-for="item in metrics" :key="item.label" class="metric-card">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <em>{{ item.hint }}</em>
      </article>
    </section>

    <section class="source-status-panel" aria-label="招投标数据来源">
      <div class="panel-title">
        <div>
          <h2>数据来源状态</h2>
          <span>当前仅展示接口接入状态；未接入不等于真实数量为 0。</span>
        </div>
      </div>
      <div class="source-status-grid">
        <article v-for="item in sourceStatusItems" :key="item.label" :data-state="item.state">
          <strong>{{ item.label }}</strong>
          <span>{{ item.text }}</span>
        </article>
      </div>
    </section>

    <section class="board-layout board-layout--top">
      <article class="workbench-panel">
        <div class="panel-title">
          <div>
            <h2>招投标网址配置</h2>
            <span>等待后台配置接口接入后，由管理员维护采集来源。</span>
          </div>
        </div>
        <div class="empty-state">
          <strong>暂无已配置网址</strong>
          <span>未从服务器读取到招投标网址配置，因此不展示任何采集来源。</span>
        </div>
      </article>

      <article class="workbench-panel">
        <div class="panel-title">
          <div>
            <h2>待开标提醒</h2>
            <span>仅展示真实开标计划，不从项目台账推算。</span>
          </div>
        </div>
        <div class="empty-state">
          <strong>暂无待开标记录</strong>
          <span>开标提醒接口未返回数据，或暂未录入开标计划。</span>
        </div>
      </article>
    </section>

    <section class="workbench-panel">
      <div class="panel-title">
        <div>
          <h2>机会发现</h2>
          <span>采集服务接入前，这里不会使用项目数据生成机会。</span>
        </div>
      </div>
      <div class="empty-state empty-state--large">
        <strong>暂无真实采集机会</strong>
        <span>请先接入招投标网站采集服务或后台录入真实机会，再在这里归纳展示。</span>
      </div>
    </section>

    <section class="workbench-panel">
      <div class="panel-title">
        <div>
          <h2>开标记录分析</h2>
          <span>只基于真实开标记录表计算预测区间，不使用模拟报价。</span>
        </div>
      </div>
      <div class="analysis-table">
        <div class="table-head">
          <span>项目</span>
          <span>控制价/预算价</span>
          <span>有效报价数</span>
          <span>预测区间</span>
          <span>预测中标报价</span>
        </div>
        <div class="empty-row">暂无开标记录表数据</div>
      </div>
    </section>

    <p v-if="errorMessage" class="error-note">{{ errorMessage }}</p>
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const errorMessage = ref('')

const metrics = computed(() => [
  { label: '已配置网址', value: '待配置', hint: '等待后台配置接口' },
  { label: '真实采集机会', value: '未接入', hint: '采集服务接入后展示' },
  { label: '待开标提醒', value: '暂无数据', hint: '未读取到开标计划' },
  { label: '报价预测记录', value: '待录入', hint: '上传开标记录表后计算' },
])
const sourceStatusItems = computed(() => [
  { label: '网址配置', state: 'pending', text: '等待后台配置接口接入' },
  { label: '机会采集', state: 'pending', text: '等待招投标网站采集服务接入' },
  { label: '开标计划', state: 'pending', text: '等待开标提醒接口或真实计划录入' },
  { label: '报价预测', state: 'pending', text: '等待真实开标记录表上传后计算' },
])

function refresh() {
  errorMessage.value = ''
}
</script>

<style scoped>
.business-workbench {
  display: grid;
  gap: 16px;
  color: var(--premium-ink);
}

.business-head,
.workbench-panel,
.source-status-panel,
.metric-card {
  background: var(--premium-glass);
  border: 1px solid var(--premium-line);
  border-radius: var(--premium-radius);
  box-shadow: var(--premium-shadow-soft);
  backdrop-filter: blur(18px) saturate(145%);
  -webkit-backdrop-filter: blur(18px) saturate(145%);
}

.business-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 20px;
}

.eyebrow {
  margin: 0 0 6px;
  color: var(--premium-blue);
  font-size: 12px;
  font-weight: 700;
}

h1,
h2,
p {
  margin: 0;
}

h1 {
  font-size: 26px;
  line-height: 1.2;
}

.business-head span,
.panel-title span,
.metric-card em,
.empty-state span {
  color: var(--premium-muted);
}

.primary-action {
  height: 36px;
  padding: 0 16px;
  border: 0;
  border-radius: var(--premium-radius-compact);
  color: #fff;
  background: linear-gradient(135deg, #2f7cff, #165dff 64%, #0f43d6);
  box-shadow: 0 10px 22px rgba(22, 93, 255, 0.18);
  cursor: pointer;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  display: grid;
  gap: 6px;
  min-width: 0;
  padding: 16px;
}

.metric-card strong {
  font-size: 24px;
}

.metric-card em {
  font-size: 12px;
  font-style: normal;
}

.board-layout {
  display: grid;
  gap: 16px;
}

.board-layout--top {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.workbench-panel {
  padding: 16px;
}

.source-status-panel {
  padding: 16px;
}

.panel-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.panel-title h2 {
  font-size: 18px;
}

.source-status-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.source-status-grid article {
  display: grid;
  gap: 5px;
  min-width: 0;
  padding: 12px;
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid rgba(255, 176, 32, 0.28);
  border-radius: var(--premium-radius-compact);
}

.source-status-grid strong,
.source-status-grid span {
  overflow-wrap: anywhere;
}

.source-status-grid span {
  color: var(--premium-muted);
  font-size: 12px;
  line-height: 1.5;
}

.empty-state {
  display: grid;
  place-items: center;
  gap: 8px;
  min-height: 120px;
  padding: 20px;
  text-align: center;
  background: rgba(255, 255, 255, 0.48);
  border: 1px dashed rgba(128, 158, 210, 0.3);
  border-radius: var(--premium-radius);
}

.empty-state--large {
  min-height: 180px;
}

.analysis-table {
  overflow: hidden;
  border: 1px solid rgba(128, 158, 210, 0.22);
  border-radius: var(--premium-radius);
}

.table-head {
  display: grid;
  grid-template-columns: minmax(240px, 1.4fr) .9fr .6fr 1fr .9fr;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  color: #385071;
  background: rgba(240, 247, 255, 0.7);
  font-size: 12px;
  font-weight: 700;
}

.empty-row {
  padding: 32px 14px;
  color: var(--premium-muted);
  text-align: center;
  background: rgba(255, 255, 255, 0.48);
  border-top: 1px solid rgba(128, 158, 210, 0.18);
}

.error-note {
  color: #d54941;
}

@media (max-width: 900px) {
  .metric-grid,
  .source-status-grid,
  .board-layout--top {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .business-head,
  .panel-title {
    flex-direction: column;
  }

  .metric-grid,
  .source-status-grid,
  .board-layout--top,
  .table-head {
    grid-template-columns: 1fr;
  }
}
</style>

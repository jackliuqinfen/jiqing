<template>
  <div class="command-dashboard">
    <section class="hero-band">
      <div>
        <h2>稳态指挥台</h2>
        <p>聚合审计项目、时限风险、金额变化和模块建设状态，为工程管理系统提供首页总览。</p>
      </div>
      <div class="hero-meta">
        <span>数据源：SQLite API</span>
        <strong>{{ todayText }}</strong>
      </div>
    </section>

    <section class="kpi-grid">
      <article v-for="card in kpiCards" :key="card.label" class="kpi-card">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <em>{{ card.hint }}</em>
      </article>
    </section>

    <section class="dashboard-grid">
      <article class="chart-card chart-card--wide">
        <div class="card-head">
          <h3>审计阶段分布</h3>
          <span>当前已启用模块</span>
        </div>
        <VChartPanel :spec="stageBarSpec" />
      </article>
      <article class="chart-card">
        <div class="card-head">
          <h3>项目状态构成</h3>
          <span>归档 / 在审 / 督办</span>
        </div>
        <VChartPanel :spec="statusPieSpec" />
      </article>
      <article class="chart-card chart-card--wide">
        <div class="card-head">
          <h3>送审金额观察</h3>
          <span>按项目排序 · Top 8</span>
        </div>
        <VChartPanel :spec="amountLineSpec" />
      </article>
      <article class="module-card">
        <div class="card-head">
          <h3>模块建设状态</h3>
          <span>1.0 阶段</span>
        </div>
        <div class="module-list">
          <div v-for="item in moduleStatus" :key="item.name" class="module-row">
            <span :class="item.enabled ? 'dot dot--live' : 'dot'" />
            <strong>{{ item.name }}</strong>
            <em>{{ item.status }}</em>
          </div>
        </div>
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import type { ISpec } from '@visactor/vchart/esm/core'
import VChartPanel from '@/components/VChartPanel.vue'
import { useAuditStore } from '@/store/audit'

const store = useAuditStore()

onMounted(() => {
  store.refreshAll()
})

const todayText = new Date().toLocaleDateString('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  weekday: 'short',
})

function money(value: number) {
  if (!value) return '0'
  if (value >= 100000000) return `${(value / 100000000).toFixed(2)} 亿`
  if (value >= 10000) return `${(value / 10000).toFixed(1)} 万`
  return value.toLocaleString('zh-CN')
}

const kpiCards = computed(() => [
  { label: '总项目', value: store.summary.totalProjects, hint: '审计模块实时统计' },
  { label: '在审项目', value: store.summary.inAuditProjects, hint: '一审 / 二审推进中' },
  { label: '超期督办', value: store.summary.overdueProjects, hint: '需管理层关注' },
  { label: '送审金额', value: money(store.summary.totalSubmittedAmount), hint: '全部项目合计' },
])

const stageRows = computed(() =>
  store.meta.stages.map((stage) => ({
    stage: stage.title,
    count: store.summary.stageCounts?.[stage.code] || 0,
    color: stage.color,
  }))
)

const amountRows = computed(() =>
  store.projects
    .slice(0, 8)
    .map((project, index) => ({
      name: project.projectName.length > 12 ? `${project.projectName.slice(0, 12)}...` : project.projectName,
      amount: Number(project.amount.submittedAmount || 0) / 10000,
      index: index + 1,
    }))
)

const stageBarSpec = computed<ISpec>(() => ({
  type: 'bar',
  data: [{ id: 'stage', values: stageRows.value }],
  xField: 'stage',
  yField: 'count',
  seriesField: 'stage',
  padding: { top: 18, right: 18, bottom: 42, left: 42 },
  animationAppear: { duration: 680, easing: 'cubicOut' },
  axes: [
    { orient: 'bottom', label: { autoHide: true, autoRotate: false } },
    { orient: 'left', min: 0, tick: { tickCount: 5 } },
  ],
  tooltip: { visible: true },
} as ISpec))

const statusPieSpec = computed<ISpec>(() => ({
  type: 'pie',
  data: [
    {
      id: 'status',
      values: [
        { type: '在审', value: store.summary.inAuditProjects },
        { type: '已完成', value: store.summary.completedProjects },
        { type: '超期', value: store.summary.overdueProjects },
        { type: '其他', value: Math.max(store.summary.totalProjects - store.summary.inAuditProjects - store.summary.completedProjects, 0) },
      ],
    },
  ],
  categoryField: 'type',
  valueField: 'value',
  outerRadius: 0.82,
  innerRadius: 0.56,
  legends: { visible: true, orient: 'bottom' },
  animationAppear: { duration: 760, easing: 'cubicOut' },
} as ISpec))

const amountLineSpec = computed<ISpec>(() => ({
  type: 'line',
  data: [{ id: 'amount', values: amountRows.value }],
  xField: 'name',
  yField: 'amount',
  point: { visible: true, style: { size: 7 } },
  line: { style: { lineWidth: 3 } },
  padding: { top: 20, right: 20, bottom: 58, left: 54 },
  axes: [
    { orient: 'bottom', label: { autoHide: true, autoRotate: true } },
    { orient: 'left', title: { visible: true, text: '万元' } },
  ],
  animationAppear: { duration: 820, easing: 'cubicOut' },
  tooltip: { visible: true },
} as ISpec))

const moduleStatus = [
  { name: '审计看板', status: '已启用', enabled: true },
  { name: '项目管理', status: '建设中', enabled: false },
  { name: '招投标看板', status: '建设中', enabled: false },
  { name: '财务看板', status: '建设中', enabled: false },
  { name: '资料管理', status: '规划中', enabled: false },
]
</script>

<style scoped>
.command-dashboard {
  display: grid;
  gap: var(--space-5);
}

.hero-band {
  min-height: 150px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-6);
  padding: var(--space-6);
  background: #fff;
  border: 1px solid var(--border-color);
}

.hero-band h2 {
  margin: 0 0 var(--space-2);
  font-size: var(--text-4xl);
  line-height: 1.15;
}

.hero-band p {
  max-width: 640px;
  margin: 0;
  color: var(--text-secondary);
}

.hero-meta {
  min-width: 170px;
  display: grid;
  gap: 5px;
  padding: var(--space-4);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
}

.hero-meta span,
.hero-meta strong {
  display: block;
}

.hero-meta span { color: var(--text-secondary); font-size: var(--text-xs); }
.hero-meta strong { font-size: var(--text-lg); }

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-3);
}

.kpi-card,
.chart-card,
.module-card {
  background: #fff;
  border: 1px solid var(--border-color);
}

.kpi-card {
  min-height: 118px;
  padding: var(--space-4);
  display: grid;
  align-content: space-between;
}

.kpi-card span,
.kpi-card em {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
}

.kpi-card strong {
  font-size: var(--text-3xl);
  line-height: 1.2;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, .65fr);
  gap: var(--space-4);
}

.chart-card,
.module-card {
  min-height: 338px;
  padding: var(--space-4);
}

.chart-card--wide {
  min-height: 360px;
}

.card-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.card-head h3 {
  margin: 0;
  font-size: var(--text-lg);
}

.card-head span {
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.module-list {
  display: grid;
  gap: var(--space-2);
}

.module-row {
  min-height: 46px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-3);
  padding: 0 var(--space-3);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
}

.module-row strong { font-size: var(--text-sm); }
.module-row em { color: var(--text-secondary); font-size: var(--text-xs); font-style: normal; }
.dot { width: 8px; height: 8px; background: var(--color-gray-300); }
.dot--live { background: var(--color-success); }

@media (max-width: 1080px) {
  .kpi-grid,
  .dashboard-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 720px) {
  .hero-band { align-items: flex-start; flex-direction: column; }
  .kpi-grid,
  .dashboard-grid { grid-template-columns: 1fr; }
  .chart-card,
  .chart-card--wide,
  .module-card { min-height: 300px; }
}
</style>

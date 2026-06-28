<template>
  <div class="command-dashboard">
    <section class="command-hero" aria-label="首页数据看板">
      <div class="hero-copy">
        <span class="hero-state"><i /> 系统稳态运行</span>
        <h2>稳态指挥台</h2>
        <p>面向工程管理内网的运行中枢，聚合审计吞吐、时限风险、金额口径和模块建设状态。</p>
        <div class="hero-signals">
          <span v-for="signal in heroSignals" :key="signal.label">
            <em>{{ signal.label }}</em>
            <strong>{{ signal.value }}</strong>
          </span>
        </div>
      </div>

      <div class="hero-console">
        <div class="console-date">
          <span>当前工作日历</span>
          <strong>{{ todayText }}</strong>
        </div>
        <div class="range-switch" role="group" aria-label="日期范围">
          <button
            v-for="item in rangeOptions"
            :key="item"
            type="button"
            :class="{ active: selectedRange === item }"
            @click="selectedRange = item"
          >
            {{ item }}
          </button>
        </div>
        <div class="console-health-grid">
          <article>
            <span>运行负载</span>
            <strong>{{ operationalLoad }}%</strong>
            <i :style="{ width: `${operationalLoad}%` }" />
          </article>
          <article>
            <span>风险队列</span>
            <strong>{{ riskQueue.length }}</strong>
            <i :style="{ width: `${clamp(riskQueue.length * 18, 8, 100)}%` }" />
          </article>
          <article>
            <span>完成率</span>
            <strong>{{ completionRate }}%</strong>
            <i :style="{ width: `${clamp(completionRate, 8, 100)}%` }" />
          </article>
        </div>
      </div>
    </section>

    <section class="mission-strip" aria-label="运行关注">
      <article v-for="item in missionItems" :key="item.label">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <em>{{ item.hint }}</em>
      </article>
    </section>

    <section class="kpi-grid" aria-label="核心指标">
      <article v-for="card in kpiCards" :key="card.label" class="kpi-card" :data-level="card.level">
        <div class="kpi-head">
          <span>{{ card.label }}</span>
          <em>{{ card.hint }}</em>
        </div>
        <strong>{{ card.value }}</strong>
        <div class="sparkline" aria-hidden="true">
          <i v-for="(point, index) in card.sparkline" :key="index" :style="{ height: `${point}%` }" />
        </div>
      </article>
    </section>

    <section class="dashboard-grid">
      <article class="chart-panel chart-panel--status">
        <div class="panel-head">
          <div>
            <h3>项目状态构成</h3>
            <p>未开始 / 进行中 / 延期 / 已完成 / 暂停</p>
          </div>
          <span>实时</span>
        </div>
        <div class="donut-stage">
          <VChartPanel :spec="statusDonutSpec" />
          <div class="donut-center">
            <span>总项目</span>
            <strong>{{ store.summary.totalProjects }}</strong>
            <em>完成率 {{ completionRate }}%</em>
          </div>
        </div>
      </article>

      <article class="chart-panel chart-panel--wide">
        <div class="panel-head">
          <div>
            <h3>审计阶段吞吐</h3>
            <p>按当前业务阶段统计项目数量</p>
          </div>
          <span>{{ store.meta.stages.length }} 个阶段</span>
        </div>
        <VChartPanel :spec="stageBarSpec" />
      </article>

      <article class="chart-panel chart-panel--wide">
        <div class="panel-head">
          <div>
            <h3>新增 / 完成趋势</h3>
            <p>近 6 个月项目流入与归档观察</p>
          </div>
          <span>{{ selectedRange }}</span>
        </div>
        <VChartPanel :spec="trendLineSpec" />
      </article>

      <article class="chart-panel">
        <div class="panel-head">
          <div>
            <h3>风险队列</h3>
            <p>延期与即将到期项目优先关注</p>
          </div>
          <span>{{ riskQueue.length }} 项</span>
        </div>
        <div class="risk-list">
          <div v-for="project in riskQueue" :key="project.id" class="risk-row">
            <i :class="{ urgent: project.isDelayed }" />
            <div>
              <strong>{{ project.projectName }}</strong>
              <span>{{ project.managerName || '未分配' }} · {{ project.auditDeadline || '未设期限' }}</span>
            </div>
            <em>{{ project.isDelayed ? `延期 ${project.delayDays || 0} 天` : '即将到期' }}</em>
          </div>
          <div v-if="!riskQueue.length" class="empty-risk">当前无高优先级时限风险</div>
        </div>
      </article>

      <article class="module-panel">
        <div class="panel-head">
          <div>
            <h3>模块建设状态</h3>
            <p>工程管理系统 1.0 范围</p>
          </div>
          <span>路线图</span>
        </div>
        <div class="module-list">
          <div v-for="item in moduleStatus" :key="item.name" class="module-row">
            <span :class="item.enabled ? 'dot dot--live' : 'dot'" />
            <strong>{{ item.name }}</strong>
            <em>{{ item.status }}</em>
          </div>
        </div>
      </article>

      <article class="chart-panel chart-panel--amount">
        <div class="panel-head">
          <div>
            <h3>送审金额观察</h3>
            <p>按当前项目列表排序 · Top 8</p>
          </div>
          <span>万元</span>
        </div>
        <VChartPanel :spec="amountLineSpec" />
      </article>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import type { ISpec } from '@visactor/vchart/esm/core'
import VChartPanel from '@/components/VChartPanel.vue'
import { useAuditStore } from '@/store/audit'

const store = useAuditStore()
const selectedRange = ref('本月')
const rangeOptions = ['本月', '本季度', '本年', '自定义日期']

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

function clamp(value: number, min = 0, max = 100) {
  return Math.min(Math.max(value, min), max)
}

function sparkline(seed: number, points = 8) {
  const base = Math.max(seed, 1)
  return Array.from({ length: points }, (_, index) => {
    const wave = Math.sin((index + 1) * 1.35 + base * 0.13)
    return clamp(34 + wave * 18 + ((base + index * 7) % 26), 18, 92)
  })
}

function overviewSparkline(key: string, fallbackSeed: number) {
  return store.overview.cardSparklines[key] || sparkline(fallbackSeed)
}

const completionRate = computed(() => {
  if (!store.summary.totalProjects) return 0
  return Math.round((store.summary.completedProjects / store.summary.totalProjects) * 100)
})

const operationalLoad = computed(() => {
  if (!store.summary.totalProjects) return 0
  const active = store.summary.inAuditProjects + store.summary.overdueProjects + store.summary.upcomingDueProjects
  return clamp(Math.round((active / store.summary.totalProjects) * 100), 8, 100)
})

const kpiCards = computed(() => [
  { label: '审计项目总数', value: store.summary.totalProjects, hint: '数据库实时统计', level: 'normal', sparkline: overviewSparkline('totalProjects', store.summary.totalProjects) },
  { label: '进行中项目数', value: store.summary.inAuditProjects, hint: '一审 / 二审推进中', level: 'active', sparkline: overviewSparkline('inAuditProjects', store.summary.inAuditProjects + 8) },
  { label: '已完成项目数', value: store.summary.completedProjects, hint: `完成率 ${completionRate.value}%`, level: 'success', sparkline: overviewSparkline('completedProjects', store.summary.completedProjects + 16) },
  { label: '延期项目数', value: store.summary.overdueProjects, hint: '需管理层关注', level: store.summary.overdueProjects ? 'danger' : 'normal', sparkline: overviewSparkline('overdueProjects', store.summary.overdueProjects + 24) },
  { label: '本月新增项目数', value: store.summary.monthlyNewProjects, hint: '按创建时间统计', level: 'normal', sparkline: overviewSparkline('monthlyNewProjects', store.summary.monthlyNewProjects + 32) },
  { label: '即将到期项目数', value: store.summary.upcomingDueProjects, hint: '7 天内计划完成', level: store.summary.upcomingDueProjects ? 'warning' : 'normal', sparkline: overviewSparkline('upcomingDueProjects', store.summary.upcomingDueProjects + 40) },
])

const missionItems = computed(() => [
  { label: '风险守望', value: `${store.summary.overdueProjects + store.summary.upcomingDueProjects} 项`, hint: '延期与到期提醒' },
  { label: '审计吞吐', value: `${store.summary.inAuditProjects}/${store.summary.completedProjects}`, hint: '进行中 / 已完成' },
  { label: '金额口径', value: money(store.summary.totalSubmittedAmount), hint: '累计送审金额' },
])

const heroSignals = computed(() => [
  { label: '项目池', value: `${store.summary.totalProjects} 项` },
  { label: '进行中', value: `${store.summary.inAuditProjects} 项` },
  { label: '送审金额', value: money(store.summary.totalSubmittedAmount) },
])

const stageRows = computed(() =>
  store.overview.stageDistribution.length
    ? store.overview.stageDistribution
    : store.meta.stages.map((stage) => ({
        stage: stage.title,
        stageCode: stage.code,
        count: store.summary.stageCounts?.[stage.code] || 0,
      }))
)

const statusRows = computed(() => store.overview.statusDistribution)

const trendRows = computed(() => store.overview.trendData)

const amountRows = computed(() => store.overview.amountTop)

const riskQueue = computed(() => store.overview.riskQueue)

function cssVar(name: string, fallback: string) {
  if (typeof window === 'undefined') return fallback
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback
}

function chartColors() {
  return [
    cssVar('--color-brand-500', '#4787F0'),
    '#14C9C9',
    '#00B42A',
    '#FF7D00',
    '#86909C',
  ]
}

function baseChart() {
  return {
    background: 'transparent',
    color: chartColors(),
    tooltip: { visible: true },
  }
}

const stageBarSpec = computed<ISpec>(() => ({
  ...baseChart(),
  type: 'bar',
  data: [{ id: 'stage', values: stageRows.value }],
  xField: 'stage',
  yField: 'count',
  seriesField: 'stage',
  padding: { top: 18, right: 18, bottom: 42, left: 42 },
  animationAppear: { duration: 760, easing: 'cubicOut' },
  bar: { style: { cornerRadius: [3, 3, 0, 0] } },
  axes: [
    { orient: 'bottom', label: { autoHide: true, autoRotate: false } },
    { orient: 'left', min: 0, tick: { tickCount: 5 } },
  ],
} as ISpec))

const statusDonutSpec = computed<ISpec>(() => ({
  ...baseChart(),
  type: 'pie',
  data: [{ id: 'status', values: statusRows.value }],
  categoryField: 'type',
  valueField: 'value',
  outerRadius: 0.82,
  innerRadius: 0.62,
  legends: { visible: true, orient: 'bottom' },
  label: { visible: false },
  animationAppear: { duration: 860, easing: 'cubicOut' },
} as ISpec))

const trendLineSpec = computed<ISpec>(() => ({
  ...baseChart(),
  type: 'line',
  data: [{ id: 'trend', values: trendRows.value }],
  xField: 'month',
  yField: 'count',
  seriesField: 'type',
  point: { visible: true, style: { size: 7 } },
  line: { style: { lineWidth: 3 } },
  padding: { top: 20, right: 24, bottom: 42, left: 42 },
  legends: { visible: true, orient: 'top', position: 'end' },
  axes: [
    { orient: 'bottom', label: { autoHide: true, autoRotate: false } },
    { orient: 'left', min: 0, tick: { tickCount: 5 } },
  ],
  animationAppear: { duration: 820, easing: 'cubicOut' },
} as ISpec))

const amountLineSpec = computed<ISpec>(() => ({
  ...baseChart(),
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

.command-hero {
  min-height: 196px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: var(--space-5);
  padding: var(--space-6);
  color: var(--text-primary);
  background:
    linear-gradient(135deg, rgba(71, 135, 240, .14), rgba(20, 201, 201, .08) 52%, rgba(255, 255, 255, .88)),
    var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-elevated);
  overflow: hidden;
  position: relative;
}

.command-hero::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(71, 135, 240, .12) 1px, transparent 1px),
    linear-gradient(90deg, rgba(71, 135, 240, .1) 1px, transparent 1px);
  background-size: 40px 40px;
  mask-image: linear-gradient(90deg, transparent, #000 36%, #000 100%);
}

.hero-copy,
.hero-console {
  position: relative;
  z-index: 1;
}

.hero-copy {
  display: grid;
  align-content: center;
  gap: var(--space-4);
}

.hero-state {
  width: fit-content;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.hero-state i {
  width: 8px;
  height: 8px;
  background: var(--color-success);
  box-shadow: 0 0 0 4px rgba(0, 180, 42, .16);
}

.hero-copy h2 {
  margin: 0;
  font-size: 30px;
  line-height: 1.12;
}

.hero-copy p {
  max-width: 680px;
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-md);
}

.hero-signals {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 160px));
  gap: var(--space-3);
}

.hero-signals span {
  min-height: 58px;
  display: grid;
  align-content: center;
  gap: 2px;
  padding: 0 var(--space-3);
  background: rgba(255, 255, 255, .72);
  border: 1px solid rgba(71, 135, 240, .16);
  border-radius: var(--radius-md);
}

.hero-signals em {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
}

.hero-signals strong {
  font-size: var(--text-lg);
  line-height: 1.25;
}

.hero-console {
  display: grid;
  gap: var(--space-3);
  align-content: center;
  padding: var(--space-4);
  background: rgba(255, 255, 255, .88);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-elevated);
}

.console-date span,
.console-health-grid span {
  display: block;
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.console-date strong {
  display: block;
  margin-top: 2px;
  font-size: var(--text-xl);
}

.range-switch {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0;
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.range-switch button {
  min-height: 32px;
  border: 0;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font: inherit;
  font-size: var(--text-xs);
}

.range-switch button.active {
  background: var(--color-brand-500);
  color: #fff;
}

.console-health-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-2);
}

.console-health-grid article {
  display: grid;
  gap: var(--space-2);
  min-height: 72px;
  padding: var(--space-3);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

.console-health-grid strong {
  font-size: var(--text-xl);
  line-height: 1.1;
}

.console-health-grid i {
  display: block;
  height: 6px;
  max-width: 100%;
  background: #14C9C9;
}

.mission-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}

.mission-strip article,
.kpi-card,
.chart-panel,
.module-panel {
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-elevated);
}

.mission-strip article {
  min-height: 86px;
  padding: var(--space-4);
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 2px var(--space-3);
  align-items: center;
  box-shadow: none;
}

.mission-strip span,
.mission-strip em,
.kpi-card span,
.kpi-card em,
.panel-head p,
.panel-head span,
.risk-row span,
.risk-row em,
.module-row em {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
}

.mission-strip strong {
  grid-row: span 2;
  font-size: var(--text-2xl);
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-3);
}

.kpi-card {
  min-height: 136px;
  padding: var(--space-4);
  display: grid;
  gap: var(--space-3);
  position: relative;
  overflow: hidden;
}

.kpi-card::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: var(--color-brand-500);
}

.kpi-card[data-level='success']::before { background: var(--color-success); }
.kpi-card[data-level='warning']::before { background: var(--color-warning); }
.kpi-card[data-level='danger']::before { background: var(--color-danger); }
.kpi-card[data-level='active']::before { background: #14C9C9; }

.kpi-head {
  display: grid;
  gap: 2px;
}

.kpi-card strong {
  font-size: var(--text-3xl);
  line-height: 1.1;
}

.sparkline {
  height: 28px;
  display: flex;
  align-items: end;
  gap: 3px;
}

.sparkline i {
  width: 100%;
  min-width: 4px;
  background: var(--color-brand-100);
  border-top: 2px solid var(--color-brand-500);
}

.dashboard-grid {
  display: grid;
  grid-template-columns: minmax(320px, .82fr) minmax(0, 1.2fr) minmax(320px, .8fr);
  gap: var(--space-4);
}

.chart-panel,
.module-panel {
  min-height: 352px;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chart-panel--wide {
  grid-column: span 2;
}

.chart-panel--amount {
  grid-column: span 2;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.panel-head h3 {
  margin: 0 0 2px;
  font-size: var(--text-md);
}

.panel-head > span {
  align-self: start;
  padding: 4px 8px;
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
}

.chart-panel :deep(.vchart-panel) {
  flex: 1;
  min-height: 270px;
}

.donut-stage {
  min-height: 270px;
  position: relative;
  flex: 1;
}

.donut-center {
  position: absolute;
  left: 50%;
  top: 42%;
  transform: translate(-50%, -50%);
  display: grid;
  place-items: center;
  pointer-events: none;
}

.donut-center span,
.donut-center em {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
}

.donut-center strong {
  font-size: var(--text-3xl);
  line-height: 1.1;
}

.risk-list,
.module-list {
  display: grid;
  gap: var(--space-2);
}

.risk-row {
  min-height: 52px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-3);
  padding: 0 var(--space-3);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

.risk-row i {
  width: 8px;
  height: 30px;
  background: var(--color-warning);
}

.risk-row i.urgent {
  background: var(--color-danger);
}

.risk-row strong,
.risk-row span {
  display: block;
}

.risk-row strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-sm);
}

.empty-risk {
  min-height: 160px;
  display: grid;
  place-items: center;
  color: var(--text-secondary);
  background: var(--bg-muted);
  border: 1px dashed var(--border-color);
  font-size: var(--text-sm);
}

.module-row {
  min-height: 48px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-3);
  padding: 0 var(--space-3);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

.module-row strong {
  font-size: var(--text-sm);
}

.dot {
  width: 8px;
  height: 8px;
  background: var(--color-gray-300);
}

.dot--live {
  background: var(--color-success);
  box-shadow: 0 0 0 4px rgba(0, 180, 42, .12);
}

@media (max-width: 1280px) {
  .kpi-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .dashboard-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .chart-panel--wide,
  .chart-panel--amount { grid-column: span 1; }
}

@media (max-width: 900px) {
  .command-hero { grid-template-columns: 1fr; }
  .hero-signals { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .mission-strip { grid-template-columns: 1fr; }
  .dashboard-grid { grid-template-columns: 1fr; }
}

@media (max-width: 720px) {
  .command-hero { padding: var(--space-4); }
  .hero-copy h2 { font-size: var(--text-3xl); }
  .hero-copy p { font-size: var(--text-sm); }
  .hero-console { padding: var(--space-3); }
  .range-switch { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .hero-signals { grid-template-columns: 1fr; }
  .console-health-grid { grid-template-columns: 1fr; }
  .hero-signals span,
  .console-health-grid article { padding: var(--space-2); }
  .kpi-grid { grid-template-columns: 1fr; }
  .mission-strip article { grid-template-columns: 1fr; }
  .mission-strip strong { grid-row: auto; }
  .chart-panel,
  .module-panel { min-height: 320px; }
  .panel-head {
    display: grid;
    gap: var(--space-2);
  }
  .panel-head > span {
    width: fit-content;
  }
  .risk-row {
    grid-template-columns: auto minmax(0, 1fr);
    padding: var(--space-3);
  }
  .risk-row em {
    grid-column: 2;
  }
  .donut-center {
    top: 40%;
  }
}
</style>

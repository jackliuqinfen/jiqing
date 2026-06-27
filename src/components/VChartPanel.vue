<template>
  <div ref="chartRef" class="vchart-panel" />
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { VChart } from '@visactor/vchart/esm/core'
import type { ISpec } from '@visactor/vchart/esm/core'
import { registerBrowserEnv } from '@visactor/vchart/esm/env'
import { registerBarChart } from '@visactor/vchart/esm/chart/bar'
import { registerLineChart } from '@visactor/vchart/esm/chart/line'
import { registerPieChart } from '@visactor/vchart/esm/chart/pie'
import { registerCartesianBandAxis, registerCartesianLinearAxis } from '@visactor/vchart/esm/component/axis/cartesian'
import { registerDiscreteLegend } from '@visactor/vchart/esm/component/legend'
import { registerLabel } from '@visactor/vchart/esm/component/label'
import { registerTooltip } from '@visactor/vchart/esm/component/tooltip'
import {
  registerCanvasTooltipHandler,
  registerDomTooltipHandler,
} from '@visactor/vchart/esm/plugin/components/tooltip-handler'
import { initVChartArcoTheme } from '@visactor/vchart-arco-theme'

const props = defineProps<{
  spec: ISpec
}>()

const chartRef = ref<HTMLElement | null>(null)
let chart: VChart | null = null
let resizeObserver: ResizeObserver | null = null
let themeReady = false
let registersReady = false

function ensureRegisters() {
  if (registersReady) return
  VChart.useRegisters([
    registerBrowserEnv,
    registerBarChart,
    registerLineChart,
    registerPieChart,
    registerCartesianBandAxis,
    registerCartesianLinearAxis,
    registerDiscreteLegend,
    registerLabel,
    registerTooltip,
    registerDomTooltipHandler,
    registerCanvasTooltipHandler,
  ])
  registersReady = true
}

function ensureTheme() {
  if (themeReady) return
  ensureRegisters()
  initVChartArcoTheme({ isWatchingMode: true })
  themeReady = true
}

async function renderChart() {
  if (!chartRef.value) return
  ensureTheme()
  await nextTick()
  if (!chart) {
    chart = new VChart(props.spec, { dom: chartRef.value, autoFit: true })
    await chart.renderAsync()
    resizeObserver = new ResizeObserver(() => {
      if (!chart || !chartRef.value) return
      const { width, height } = chartRef.value.getBoundingClientRect()
      if (width > 0 && height > 0) chart.resizeSync(width, height)
    })
    resizeObserver.observe(chartRef.value)
    return
  }
  await chart.updateSpec(props.spec, true)
}

onMounted(renderChart)

watch(
  () => props.spec,
  () => {
    renderChart()
  },
  { deep: true }
)

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  chart?.release()
  chart = null
})
</script>

<style scoped>
.vchart-panel {
  width: 100%;
  height: 100%;
  min-height: 240px;
}
</style>

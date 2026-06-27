<template>
  <section class="placeholder-page">
    <div class="placeholder-main">
      <span class="placeholder-icon"><t-icon :name="iconName" /></span>
      <div>
        <h2>{{ title }}</h2>
        <p>{{ description }}</p>
      </div>
    </div>
    <div class="placeholder-steps">
      <article v-for="item in roadmap" :key="item.title">
        <strong>{{ item.title }}</strong>
        <span>{{ item.text }}</span>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const title = computed(() => String(route.meta.title || '模块建设中'))
const description = computed(() => String(route.meta.description || '该业务模块已进入系统导航，功能将在后续版本逐步开放。'))
const iconName = computed(() => String(route.meta.icon || 'task'))

const roadmap = [
  { title: '业务边界', text: '确认字段、流程、权限和数据口径。' },
  { title: '数据模型', text: '设计数据库表、接口和导入策略。' },
  { title: '工作台', text: '接入稳态指挥台的统计、预警和操作入口。' },
]
</script>

<style scoped>
.placeholder-page {
  min-height: calc(100vh - 104px);
  display: grid;
  align-content: center;
  gap: var(--space-5);
  padding: var(--space-8);
  background: #fff;
  border: 1px solid var(--border-color);
}

.placeholder-main {
  display: flex;
  align-items: center;
  gap: var(--space-5);
}

.placeholder-icon {
  width: 72px;
  height: 72px;
  display: grid;
  place-items: center;
  background: var(--color-brand-50);
  color: var(--color-brand-600);
  border: 1px solid var(--color-brand-100);
  font-size: 30px;
}

.placeholder-main h2 {
  margin: 0 0 var(--space-2);
  font-size: var(--text-3xl);
}

.placeholder-main p {
  max-width: 620px;
  margin: 0;
  color: var(--text-secondary);
}

.placeholder-steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--space-3);
}

.placeholder-steps article {
  padding: var(--space-4);
  background: var(--bg-muted);
  border: 1px solid var(--border-color);
}

.placeholder-steps strong,
.placeholder-steps span {
  display: block;
}

.placeholder-steps strong { margin-bottom: var(--space-2); }
.placeholder-steps span { color: var(--text-secondary); font-size: var(--text-sm); }

@media (max-width: 760px) {
  .placeholder-page { padding: var(--space-5); }
  .placeholder-main { align-items: flex-start; flex-direction: column; }
  .placeholder-steps { grid-template-columns: 1fr; }
}
</style>

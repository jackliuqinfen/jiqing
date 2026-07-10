<template>
  <div class="money-display" :class="[`money-display--${mode}`, { 'money-display--zero-muted': mutedZero && numericValue === 0 }]">
    <template v-if="mode === 'inline'">
      <span>{{ parts.wan }}</span>
      <em>{{ parts.upper }}</em>
    </template>
    <template v-else-if="mode === 'compact'">
      <strong>{{ parts.wan }}</strong>
      <span>{{ parts.upper }}</span>
    </template>
    <template v-else>
      <dl>
        <dt>元</dt>
        <dd>{{ parts.yuan }}</dd>
        <dt>万元</dt>
        <dd>{{ parts.wan }}</dd>
        <dt>中文大写</dt>
        <dd>{{ parts.upper }}</dd>
      </dl>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { moneyParts } from '@/utils/format'

const props = withDefaults(defineProps<{
  value?: number | string | null
  mode?: 'full' | 'compact' | 'inline'
  mutedZero?: boolean
}>(), {
  value: 0,
  mode: 'full',
  mutedZero: false,
})

const numericValue = computed(() => Number(props.value || 0))
const parts = computed(() => moneyParts(numericValue.value))
</script>

<style scoped>
.money-display {
  min-width: 0;
  color: var(--text-primary);
}

.money-display--compact,
.money-display--inline {
  display: grid;
  gap: 2px;
}

.money-display--compact strong,
.money-display--inline span {
  color: var(--text-primary);
  font-size: inherit;
  font-weight: 700;
}

.money-display--compact span,
.money-display--inline em {
  overflow: hidden;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
  line-height: 1.5;
  text-overflow: ellipsis;
}

.money-display--inline {
  display: inline-grid;
}

.money-display--full dl {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 6px 12px;
  margin: 0;
}

.money-display--full dt,
.money-display--full dd {
  margin: 0;
  font-size: var(--text-xs);
  line-height: 1.6;
}

.money-display--full dt {
  color: var(--text-tertiary);
}

.money-display--full dd {
  color: var(--text-primary);
}

.money-display--zero-muted {
  color: var(--text-secondary);
}
</style>

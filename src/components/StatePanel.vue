<template>
  <div class="state-panel" :class="`state-panel--${state}`">
    <div class="state-panel__icon">
      <t-icon :name="iconName" size="20px" :class="{ 'state-panel__icon--loading': state === 'loading' }" />
    </div>
    <div class="state-panel__body">
      <strong>{{ title }}</strong>
      <p>{{ description }}</p>
      <div v-if="$slots.actions" class="state-panel__actions">
        <slot name="actions" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  state: 'loading' | 'empty' | 'error' | 'info'
  title: string
  description: string
}>()

const iconName = computed(() => {
  return {
    loading: 'refresh',
    empty: 'file-paste',
    error: 'error-circle',
    info: 'info-circle',
  }[props.state]
})
</script>

<style scoped>
.state-panel {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--space-4);
  align-items: start;
  padding: var(--space-5);
  background: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
}

.state-panel__icon {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: var(--radius-md);
  background: var(--bg-muted);
  color: var(--color-brand-ink);
}

.state-panel__body {
  min-width: 0;
  display: grid;
  gap: 6px;
}

.state-panel__body strong {
  color: var(--text-primary);
  font-size: var(--text-md);
}

.state-panel__body p {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  line-height: 1.6;
}

.state-panel__actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-top: var(--space-1);
}

.state-panel--error .state-panel__icon {
  color: var(--color-danger);
}

.state-panel--empty .state-panel__icon {
  color: var(--text-secondary);
}

.state-panel__icon--loading {
  animation: state-panel-spin 1s linear infinite;
}

@keyframes state-panel-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>

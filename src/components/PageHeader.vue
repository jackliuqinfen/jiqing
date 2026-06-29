<template>
  <header class="page-header">
    <div class="page-header__copy">
      <p v-if="eyebrow" class="page-header__eyebrow">{{ eyebrow }}</p>
      <h2 class="page-header__title">{{ title }}</h2>
      <p v-if="description" class="page-header__description">{{ description }}</p>
      <div v-if="$slots.meta" class="page-header__meta">
        <slot name="meta" />
      </div>
    </div>
    <div v-if="$slots.actions" class="page-header__actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  description?: string
  eyebrow?: string
}>()
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

.page-header__copy {
  min-width: 0;
  display: grid;
  gap: 4px;
}

.page-header__eyebrow {
  margin: 0;
  color: var(--color-brand-ink);
  font-size: var(--text-xs);
  font-weight: 600;
}

.page-header__title {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--text-2xl);
  line-height: 1.2;
  font-weight: 700;
}

.page-header__description {
  margin: 0;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  line-height: 1.6;
}

.page-header__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-1);
}

.page-header__actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-shrink: 0;
}

@media (max-width: 720px) {
  .page-header {
    flex-direction: column;
  }

  .page-header__actions {
    width: 100%;
    flex-wrap: wrap;
  }
}
</style>

<template>
  <section class="lifecycle-status" aria-label="项目生命周期状态">
    <template v-if="loading">
      <span class="lifecycle-status__muted">正在读取生命周期状态...</span>
    </template>
    <template v-else-if="snapshot">
      <div class="lifecycle-status__current">
        <span>当前阶段</span>
        <ATag size="small" variant="light" theme="primary">{{ snapshot.currentStageLabel }}</ATag>
        <em>版本 {{ snapshot.lifecycleVersion }}</em>
      </div>
      <div class="lifecycle-status__next">
        <span>下一阶段</span>
        <strong>{{ snapshot.nextTransition?.toStageLabel || '已归档' }}</strong>
        <em v-if="snapshot.nextTransition?.blockers.length">{{ snapshot.nextTransition.blockers.length }} 项待处理</em>
      </div>
      <AButton
        v-if="snapshot.nextTransition && props.canAdvance"
        size="small"
        type="primary"
        @click="emit('advance', snapshot)"
      >
        推进阶段
      </AButton>
    </template>
    <template v-else>
      <span class="lifecycle-status__muted">生命周期状态暂不可用</span>
      <AButton size="mini" type="text" @click="refresh">重试</AButton>
    </template>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { fetchProjectLifecycleSnapshot } from '@/api/projectLifecycle'
import type { ProjectLifecycleSnapshot } from '@/types/projectLifecycle'

const props = withDefaults(defineProps<{ projectId: string; canAdvance?: boolean }>(), {
  canAdvance: false,
})
const emit = defineEmits<{ advance: [snapshot: ProjectLifecycleSnapshot] }>()

const snapshot = ref<ProjectLifecycleSnapshot | null>(null)
const loading = ref(false)

async function refresh() {
  if (!props.projectId) {
    snapshot.value = null
    return
  }
  loading.value = true
  try {
    snapshot.value = await fetchProjectLifecycleSnapshot(props.projectId)
  } catch {
    snapshot.value = null
  } finally {
    loading.value = false
  }
}

watch(() => props.projectId, refresh, { immediate: true })

defineExpose({ refresh })
</script>

<style scoped>
.lifecycle-status {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 7px 9px;
  color: var(--text-primary);
  background: var(--color-brand-50);
  border: 1px solid var(--color-brand-100);
  border-radius: 6px;
}

.lifecycle-status__current,
.lifecycle-status__next {
  display: grid;
  grid-template-columns: auto auto;
  gap: 2px 6px;
  min-width: 0;
}

.lifecycle-status span,
.lifecycle-status em,
.lifecycle-status__muted {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  font-style: normal;
}

.lifecycle-status__current span,
.lifecycle-status__next span { grid-column: 1 / -1; }
.lifecycle-status__next strong { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--text-sm); }

@media (max-width: 760px) {
  .lifecycle-status { align-items: flex-start; flex-wrap: wrap; }
}
</style>

<template>
  <div class="kanban-board">
    <div ref="boardRef" id="kanban-board-wrapper" class="board-wrapper">
      <KanbanColumn
        v-for="col in columnCards"
        :key="col.id"
        :column="col"
        :cards="col.cards"
        @edit="handleEditCard"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useKanbanStore } from '@/store/kanban'
import { useAuthStore } from '@/store/auth'
import { useKanbanDrag, validateStageMove } from '@/hooks/useKanbanDrag'
import type { CostAuditItem, KanbanStage } from '@/types'
import { MessagePlugin } from 'tdesign-vue-next'
import KanbanColumn from './KanbanColumn.vue'

const store = useKanbanStore()
const authStore = useAuthStore()
const emit = defineEmits<{ edit: [item: CostAuditItem] }>()

const columnCards = computed(() => store.columnCards)
const dragDisabled = computed(() => !authStore.isAuthenticated)

function canMove(cardId: string, from: KanbanStage, to: KanbanStage): boolean {
  const card = store.itemsMap.get(cardId)
  if (!card) return false
  const result = validateStageMove(card, from, to)
  if (!result.allowed && result.reason) MessagePlugin.warning(result.reason)
  return result.allowed
}

function handleDragEnd(cardId: string, from: KanbanStage, to: KanbanStage, newIndex: number) {
  store.handleDragMove({ cardId, fromStage: from, toStage: to, newIndex, operator: '当前用户' })
}

useKanbanDrag({ disabled: dragDisabled.value, canMove, onDragEnd: handleDragEnd })

function handleEditCard(item: CostAuditItem) { emit('edit', item) }
</script>

<style scoped>
.kanban-board {
  flex: 1;
  overflow: hidden;
  padding: var(--space-4) var(--space-6);
  background: var(--bg-page);
}

.board-wrapper {
  display: flex;
  gap: var(--space-4);
  overflow-x: auto;
  overflow-y: hidden;
  padding-bottom: var(--space-3);
  height: 100%;
  align-items: flex-start;
}

.board-wrapper::-webkit-scrollbar { height: 6px; }
.board-wrapper::-webkit-scrollbar-thumb {
  background: var(--color-gray-200);
  border-radius: 3px;
  border: 2px solid var(--bg-page);
}
.board-wrapper::-webkit-scrollbar-thumb:hover { background: var(--color-gray-300); }
.board-wrapper::-webkit-scrollbar-track { background: transparent; }

@media (max-width: 900px) {
  .kanban-board { padding: var(--space-3) var(--space-4); }
  .board-wrapper { gap: var(--space-3); }
}
</style>

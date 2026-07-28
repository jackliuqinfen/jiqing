<template>
  <div
    v-if="visible"
    class="object-context-menu"
    :style="{ left: `${safeX}px`, top: `${safeY}px` }"
    role="menu"
    @pointerdown.stop
  >
    <template v-for="item in items" :key="item.key">
      <div v-if="item.divider" class="object-context-menu__divider" />
      <button
        v-else
        type="button"
        role="menuitem"
        :disabled="item.disabled"
        :class="{ 'object-context-menu__danger': item.danger }"
        @click="select(item.key)"
      >
        <AIcon :name="item.icon || 'list'" />
        <span>{{ item.label }}</span>
        <small v-if="item.shortcut">{{ item.shortcut }}</small>
      </button>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'

export type ObjectContextMenuItem = {
  key: string
  label?: string
  icon?: string
  shortcut?: string
  disabled?: boolean
  danger?: boolean
  divider?: boolean
}

const props = defineProps<{
  visible: boolean
  x: number
  y: number
  items: ObjectContextMenuItem[]
}>()

const emit = defineEmits<{
  'update:visible': [visible: boolean]
  select: [key: string]
}>()

const safeX = computed(() => Math.max(8, Math.min(props.x, window.innerWidth - 210)))
const safeY = computed(() => Math.max(8, Math.min(props.y, window.innerHeight - Math.max(80, props.items.length * 38))))

function close() {
  emit('update:visible', false)
}

function select(key: string) {
  close()
  emit('select', key)
}

onMounted(() => {
  window.addEventListener('pointerdown', close)
  window.addEventListener('blur', close)
  window.addEventListener('resize', close)
  window.addEventListener('scroll', close, true)
})

onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', close)
  window.removeEventListener('blur', close)
  window.removeEventListener('resize', close)
  window.removeEventListener('scroll', close, true)
})
</script>

<style scoped>
.object-context-menu {
  position: fixed;
  z-index: 1250;
  width: 202px;
  padding: 6px;
  background: rgba(255, 255, 255, 0.97);
  border: 1px solid rgba(128, 158, 210, 0.2);
  border-radius: var(--radius-lg);
  box-shadow: 0 16px 38px rgba(31, 54, 92, 0.17);
  backdrop-filter: blur(18px) saturate(124%);
}

.object-context-menu button {
  width: 100%;
  min-height: 34px;
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding: 0 9px;
  text-align: left;
  color: var(--text-primary);
  background: transparent;
  border: 0;
  border-radius: var(--radius-md);
  cursor: pointer;
  font: inherit;
  font-size: var(--text-sm);
}

.object-context-menu button:hover:not(:disabled) {
  color: var(--color-brand-600);
  background: var(--color-brand-50);
}

.object-context-menu button:disabled {
  opacity: 0.4;
  cursor: default;
}

.object-context-menu button small {
  color: var(--text-tertiary);
  font-size: var(--text-xs);
}

.object-context-menu__divider {
  height: 1px;
  margin: 5px 7px;
  background: var(--border-color);
}

.object-context-menu .object-context-menu__danger {
  color: var(--color-danger);
}
</style>

<template>
  <div class="workspace-tabbar" aria-label="工作区标签">
    <div class="workspace-tabbar__history">
      <button type="button" :disabled="!canGoBack" title="返回 (Alt+Left)" @click="$emit('back')">
        <AIcon name="chevron-left" />
      </button>
      <button type="button" :disabled="!canGoForward" title="前进 (Alt+Right)" @click="$emit('forward')">
        <AIcon name="chevron-right" />
      </button>
    </div>

    <div class="workspace-tabbar__tabs">
      <div
        v-for="(tab, index) in tabs"
        :key="tab.id"
        class="workspace-tab"
        :class="{ 'workspace-tab--active': tab.id === activeTabId, 'workspace-tab--dragging': draggedTabId === tab.id }"
        :draggable="tab.closable"
        @click="$emit('activate', tab.id)"
        @auxclick.middle.prevent="tab.closable && $emit('close', tab.id)"
        @contextmenu.prevent="openMenu($event, tab)"
        @dragstart="startDrag(tab.id, $event)"
        @dragover.prevent
        @drop.prevent="dropTab(index)"
        @dragend="draggedTabId = ''"
      >
        <AIcon :name="tab.icon" />
        <span :title="tab.title">{{ tab.title }}</span>
        <AIcon v-if="tab.pinned" name="pin" class="workspace-tab__pin" />
        <button
          v-else-if="tab.closable"
          type="button"
          class="workspace-tab__close"
          :aria-label="`关闭 ${tab.title}`"
          @click.stop="$emit('close', tab.id)"
        >
          ×
        </button>
      </div>
    </div>

    <button
      type="button"
      class="workspace-tabbar__restore"
      :disabled="!canRestore"
      title="恢复最近关闭的标签 (Ctrl+Shift+T)"
      @click="$emit('restore')"
    >
      <AIcon name="rollback" />
    </button>

    <div
      v-if="menu.visible"
      class="workspace-tab-menu"
      :style="{ left: `${menu.x}px`, top: `${menu.y}px` }"
      role="menu"
    >
      <button type="button" role="menuitem" @click="emitMenu('toggle-pin')">
        {{ menu.tab?.pinned ? '取消固定' : '固定标签' }}
      </button>
      <button type="button" role="menuitem" :disabled="!menu.tab?.closable" @click="emitMenu('close')">关闭标签</button>
      <button type="button" role="menuitem" @click="emitMenu('close-others')">关闭其他标签</button>
      <button type="button" role="menuitem" :disabled="!canRestore" @click="emitMenu('restore')">恢复关闭的标签</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import type { WorkspaceTab } from '@/workspace/workspaceTabs'

const props = defineProps<{
  tabs: WorkspaceTab[]
  activeTabId: string
  canRestore: boolean
}>()

const emit = defineEmits<{
  activate: [tabId: string]
  close: [tabId: string]
  closeOthers: [tabId: string]
  togglePin: [tabId: string]
  restore: []
  reorder: [tabId: string, targetIndex: number]
  back: []
  forward: []
}>()

const draggedTabId = ref('')
const menu = reactive({
  visible: false,
  x: 0,
  y: 0,
  tab: null as WorkspaceTab | null,
})

const activeTab = computed(() => props.tabs.find((tab) => tab.id === props.activeTabId))
const canGoBack = computed(() => Boolean(activeTab.value && activeTab.value.historyIndex > 0))
const canGoForward = computed(() => Boolean(
  activeTab.value
  && activeTab.value.historyIndex < activeTab.value.history.length - 1,
))

function startDrag(tabId: string, event: DragEvent) {
  draggedTabId.value = tabId
  event.dataTransfer?.setData('text/plain', tabId)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}

function dropTab(targetIndex: number) {
  if (!draggedTabId.value) return
  emit('reorder', draggedTabId.value, targetIndex)
  draggedTabId.value = ''
}

function openMenu(event: MouseEvent, tab: WorkspaceTab) {
  menu.visible = true
  menu.x = Math.min(event.clientX, window.innerWidth - 176)
  menu.y = Math.min(event.clientY, window.innerHeight - 176)
  menu.tab = tab
}

function closeMenu() {
  menu.visible = false
  menu.tab = null
}

function emitMenu(action: 'toggle-pin' | 'close' | 'close-others' | 'restore') {
  const tabId = menu.tab?.id || ''
  closeMenu()
  if (action === 'restore') {
    emit('restore')
    return
  }
  if (!tabId) return
  if (action === 'toggle-pin') emit('togglePin', tabId)
  if (action === 'close') emit('close', tabId)
  if (action === 'close-others') emit('closeOthers', tabId)
}

onMounted(() => {
  window.addEventListener('pointerdown', closeMenu)
  window.addEventListener('blur', closeMenu)
})

onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', closeMenu)
  window.removeEventListener('blur', closeMenu)
})
</script>

<style scoped>
.workspace-tabbar {
  grid-area: tabs;
  min-width: 0;
  height: 40px;
  display: flex;
  align-items: end;
  gap: 6px;
  padding: 5px 14px 0;
  background: rgba(246, 249, 254, 0.72);
  border-bottom: 1px solid rgba(128, 158, 210, 0.14);
  backdrop-filter: blur(12px) saturate(120%);
}

.workspace-tabbar__history {
  height: 30px;
  display: flex;
  align-items: center;
  gap: 2px;
  padding-bottom: 4px;
}

.workspace-tabbar__history button,
.workspace-tabbar__restore {
  width: 28px;
  height: 28px;
  display: inline-grid;
  place-items: center;
  padding: 0;
  color: var(--text-secondary);
  background: transparent;
  border: 0;
  border-radius: var(--radius-md);
  cursor: pointer;
}

.workspace-tabbar__history button:hover:not(:disabled),
.workspace-tabbar__restore:hover:not(:disabled) {
  color: var(--color-brand-600);
  background: rgba(255, 255, 255, 0.84);
}

.workspace-tabbar button:disabled {
  opacity: 0.34;
  cursor: default;
}

.workspace-tabbar__tabs {
  min-width: 0;
  flex: 1;
  display: flex;
  align-items: end;
  gap: 3px;
  overflow-x: auto;
  scrollbar-width: none;
}

.workspace-tabbar__tabs::-webkit-scrollbar {
  display: none;
}

.workspace-tab {
  min-width: 116px;
  max-width: 220px;
  height: 34px;
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 0 9px;
  color: var(--text-secondary);
  background: rgba(241, 245, 251, 0.58);
  border: 1px solid transparent;
  border-bottom: 0;
  border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  cursor: default;
  user-select: none;
}

.workspace-tab > span {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--text-sm);
}

.workspace-tab:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.68);
}

.workspace-tab--active {
  color: var(--text-primary);
  background: var(--bg-surface);
  border-color: rgba(128, 158, 210, 0.18);
  box-shadow: 0 -6px 16px rgba(54, 83, 130, 0.05);
}

.workspace-tab--dragging {
  opacity: 0.48;
}

.workspace-tab__pin {
  color: var(--color-brand-500);
  font-size: 12px;
}

.workspace-tab__close {
  width: 18px;
  height: 18px;
  display: grid;
  place-items: center;
  padding: 0;
  color: var(--text-tertiary);
  background: transparent;
  border: 0;
  border-radius: 50%;
  cursor: pointer;
  line-height: 1;
}

.workspace-tab__close:hover {
  color: var(--text-primary);
  background: var(--fill-color-2);
}

.workspace-tabbar__restore {
  margin-bottom: 4px;
}

.workspace-tab-menu {
  position: fixed;
  z-index: 1200;
  width: 168px;
  padding: 5px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(128, 158, 210, 0.2);
  border-radius: var(--radius-lg);
  box-shadow: 0 14px 34px rgba(31, 54, 92, 0.16);
  backdrop-filter: blur(16px);
}

.workspace-tab-menu button {
  width: 100%;
  min-height: 32px;
  padding: 0 10px;
  text-align: left;
  color: var(--text-primary);
  background: transparent;
  border: 0;
  border-radius: var(--radius-md);
  cursor: pointer;
}

.workspace-tab-menu button:hover:not(:disabled) {
  color: var(--color-brand-600);
  background: var(--color-brand-50);
}

@media (max-width: 760px) {
  .workspace-tabbar {
    padding-left: 8px;
    padding-right: 8px;
  }

  .workspace-tab {
    min-width: 104px;
    max-width: 160px;
  }
}
</style>

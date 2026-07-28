<template>
  <div v-if="visible" class="command-center-mask" @mousedown.self="close">
    <section class="command-center" role="dialog" aria-modal="true" aria-label="全局命令中心">
      <div class="command-center__search">
        <AIcon name="search" />
        <input
          ref="inputRef"
          v-model="keyword"
          type="search"
          placeholder="搜索项目，或输入要执行的操作"
          @keydown="handleKeydown"
        />
        <kbd>Esc</kbd>
      </div>

      <div class="command-center__body">
        <div v-if="loading" class="command-center__state">正在搜索真实项目数据...</div>
        <div v-else-if="items.length === 0" class="command-center__state">
          没有找到匹配的项目或命令
        </div>
        <button
          v-for="(item, index) in items"
          :key="item.id"
          type="button"
          class="command-item"
          :class="{ 'command-item--active': index === activeIndex }"
          @mouseenter="activeIndex = index"
          @click="execute(item)"
        >
          <span class="command-item__icon"><AIcon :name="item.icon" /></span>
          <span class="command-item__copy">
            <strong>{{ item.title }}</strong>
            <small>{{ item.description }}</small>
          </span>
          <span class="command-item__type">{{ item.typeLabel }}</span>
        </button>
      </div>

      <footer class="command-center__footer">
        <span><kbd>↑</kbd><kbd>↓</kbd> 选择</span>
        <span><kbd>Enter</kbd> 打开</span>
        <span><kbd>Ctrl</kbd><kbd>K</kbd> 搜索</span>
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { fetchProjectRecords } from '@/api/projects'

type CommandItem = {
  id: string
  title: string
  description: string
  typeLabel: string
  icon: string
  route?: string
  action?: string
}

const props = defineProps<{ visible: boolean }>()
const emit = defineEmits<{
  'update:visible': [visible: boolean]
  navigate: [route: string]
  action: [action: string]
}>()

const inputRef = ref<HTMLInputElement | null>(null)
const keyword = ref('')
const projectItems = ref<CommandItem[]>([])
const loading = ref(false)
const activeIndex = ref(0)
let searchTimer = 0
let searchRequest = 0

const commands: CommandItem[] = [
  {
    id: 'command:project-create',
    title: '上传合同创建项目',
    description: '进入项目管理并打开合同建档流程',
    typeLabel: '命令',
    icon: 'add',
    action: 'project:create',
  },
  {
    id: 'command:materials-upload',
    title: '上传项目资料',
    description: '选择项目和资料类型后上传',
    typeLabel: '命令',
    icon: 'upload',
    action: 'materials:upload',
  },
  {
    id: 'command:sync-folder',
    title: '打开本地同步目录',
    description: '仅在 Windows 桌面客户端中可用',
    typeLabel: '桌面',
    icon: 'folder',
    action: 'desktop:open-sync-folder',
  },
  {
    id: 'command:audit-board',
    title: '进入审计看板',
    description: '按审计阶段查看在办项目',
    typeLabel: '视图',
    icon: 'view-module',
    route: '/audit?mode=kanban',
  },
  {
    id: 'command:project-ledger',
    title: '进入项目台账',
    description: '查看项目主档案和生命周期信息',
    typeLabel: '视图',
    icon: 'task',
    route: '/project-management?view=ledger',
  },
]

const filteredCommands = computed(() => {
  const value = keyword.value.trim().toLowerCase()
  if (!value) return commands
  return commands.filter((item) => `${item.title} ${item.description}`.toLowerCase().includes(value))
})

const items = computed(() => [...projectItems.value, ...filteredCommands.value])

watch(
  () => props.visible,
  (visible) => {
    if (!visible) return
    keyword.value = ''
    projectItems.value = []
    activeIndex.value = 0
    nextTick(() => inputRef.value?.focus())
  },
)

watch(keyword, (value) => {
  window.clearTimeout(searchTimer)
  activeIndex.value = 0
  const trimmed = value.trim()
  if (!trimmed) {
    projectItems.value = []
    loading.value = false
    return
  }
  searchTimer = window.setTimeout(() => searchProjects(trimmed), 180)
})

watch(items, (nextItems) => {
  if (activeIndex.value >= nextItems.length) activeIndex.value = Math.max(0, nextItems.length - 1)
})

async function searchProjects(value: string) {
  const requestId = ++searchRequest
  loading.value = true
  try {
    const result = await fetchProjectRecords({ keyword: value, page: 1, pageSize: 8 })
    if (requestId !== searchRequest) return
    projectItems.value = result.data.map((project) => ({
      id: `project:${project.id}`,
      title: project.projectName,
      description: [project.projectCode, project.constructionUnit || project.contractorName, project.managerName]
        .filter(Boolean)
        .join(' · '),
      typeLabel: '项目',
      icon: 'task',
      route: `/project-management?projectId=${encodeURIComponent(project.id)}&projectName=${encodeURIComponent(project.projectName)}`,
    }))
  } catch {
    if (requestId === searchRequest) projectItems.value = []
  } finally {
    if (requestId === searchRequest) loading.value = false
  }
}

function close() {
  emit('update:visible', false)
}

function execute(item: CommandItem) {
  close()
  if (item.route) emit('navigate', item.route)
  if (item.action) emit('action', item.action)
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    close()
    return
  }
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    activeIndex.value = items.value.length ? (activeIndex.value + 1) % items.value.length : 0
    return
  }
  if (event.key === 'ArrowUp') {
    event.preventDefault()
    activeIndex.value = items.value.length
      ? (activeIndex.value - 1 + items.value.length) % items.value.length
      : 0
    return
  }
  if (event.key === 'Enter' && items.value[activeIndex.value]) {
    event.preventDefault()
    execute(items.value[activeIndex.value])
  }
}

onBeforeUnmount(() => {
  window.clearTimeout(searchTimer)
  searchRequest += 1
})
</script>

<style scoped>
.command-center-mask {
  position: fixed;
  inset: 0;
  z-index: 1300;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: min(16vh, 150px) 20px 20px;
  background: rgba(25, 38, 60, 0.18);
  backdrop-filter: blur(5px);
}

.command-center {
  width: min(680px, 100%);
  overflow: hidden;
  background: rgba(255, 255, 255, 0.97);
  border: 1px solid rgba(128, 158, 210, 0.24);
  border-radius: var(--radius-xl);
  box-shadow: 0 28px 80px rgba(31, 54, 92, 0.22);
  backdrop-filter: blur(20px) saturate(130%);
}

.command-center__search {
  height: 58px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 0 16px;
  border-bottom: 1px solid var(--border-color);
}

.command-center__search > :first-child {
  color: var(--color-brand-500);
  font-size: 20px;
}

.command-center__search input {
  min-width: 0;
  flex: 1;
  height: 100%;
  padding: 0;
  color: var(--text-primary);
  background: transparent;
  border: 0;
  outline: 0;
  font-size: var(--text-base);
}

.command-center__search input::placeholder {
  color: var(--text-tertiary);
}

kbd {
  min-width: 22px;
  height: 22px;
  display: inline-grid;
  place-items: center;
  padding: 0 6px;
  color: var(--text-tertiary);
  background: var(--fill-color-1);
  border: 1px solid var(--border-color);
  border-radius: 5px;
  box-shadow: 0 1px 0 rgba(31, 54, 92, 0.08);
  font: inherit;
  font-size: 11px;
}

.command-center__body {
  max-height: min(56vh, 520px);
  padding: 7px;
  overflow-y: auto;
}

.command-center__state {
  padding: 36px 20px;
  text-align: center;
  color: var(--text-secondary);
  font-size: var(--text-sm);
}

.command-item {
  width: 100%;
  min-height: 56px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 10px;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: var(--radius-lg);
  cursor: pointer;
}

.command-item--active,
.command-item:hover {
  background: var(--color-brand-50);
}

.command-item__icon {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  flex: 0 0 auto;
  color: var(--color-brand-600);
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid var(--color-brand-100);
  border-radius: var(--radius-md);
}

.command-item__copy {
  min-width: 0;
  flex: 1;
  display: grid;
  gap: 2px;
}

.command-item__copy strong,
.command-item__copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.command-item__copy strong {
  font-size: var(--text-sm);
}

.command-item__copy small,
.command-item__type {
  color: var(--text-secondary);
  font-size: var(--text-xs);
}

.command-item__type {
  flex: 0 0 auto;
}

.command-center__footer {
  min-height: 38px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  padding: 7px 14px;
  color: var(--text-tertiary);
  background: rgba(246, 249, 253, 0.76);
  border-top: 1px solid var(--border-color);
  font-size: var(--text-xs);
}

.command-center__footer span {
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>

import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  fetchDesktopSyncPolicy,
  fetchDesktopSyncProjects,
  getAuthToken,
  type DesktopSyncProject,
} from '@/api/system'
import { useAuthStore } from '@/store/auth'
import {
  createDesktopSyncProjectLoadCycle,
  type DesktopSyncProjectLoadInvalidation,
  type DesktopSyncProjectLoadTicket,
} from './desktopSyncLoadCycle'
import type {
  DesktopCapabilities,
  DesktopSyncState,
  JiqingDesktopBridge,
} from '@/types/desktop'
import type { DesktopSyncPolicySetting } from '@/types'

const DEFAULT_PERMISSION_MESSAGE = '资料同步权限已变化，请重新确认同步范围'

export function useDesktopSync() {
  const authStore = useAuthStore()
  const bridge = ref<JiqingDesktopBridge | null>(
    typeof window === 'undefined' ? null : window.jiqingDesktop || null,
  )
  const capabilities = ref<DesktopCapabilities | null>(null)
  const state = ref<DesktopSyncState | null>(null)
  const projects = ref<DesktopSyncProject[]>([])
  const syncPolicy = ref<(DesktopSyncPolicySetting & { enabledForCurrentUser?: boolean }) | null>(null)
  const selectedProjectRefs = ref<string[]>([])
  const loadingProjects = ref(false)
  const actionPending = ref(false)
  const startPending = ref(false)
  const errorMessage = ref('')
  const permissionMessage = ref('')
  const permissionRefreshRequired = ref(false)
  const policyDisabled = ref(false)
  const dialogOpen = ref(false)
  const projectLoadCycle = createDesktopSyncProjectLoadCycle()
  let unsubscribe: null | (() => void) = null
  let initialization: Promise<void> | null = null
  let autoStartAttemptedUserId = ''

  const isDesktop = computed(() => capabilities.value?.desktop === true)
  const isAuthenticated = computed(() => authStore.isAuthenticated && Boolean(authStore.user?.id))
  const isSyncing = computed(() => ['checking_policy', 'syncing'].includes(state.value?.status || ''))
  const projectSelectionDisabled = computed(
    () => permissionRefreshRequired.value || loadingProjects.value || policyDisabled.value,
  )
  const canStart = computed(() => Boolean(
    isDesktop.value
      && isAuthenticated.value
      && state.value?.localRoot
      && selectedProjectRefs.value.length
      && !isSyncing.value
      && !startPending.value
      && !projectSelectionDisabled.value
      && !actionPending.value,
  ))

  function currentAuthUserId(): string | null {
    if (!authStore.isAuthenticated) return null
    return authStore.user?.id || null
  }

  function isCurrentProjectLoad(loadTicket: DesktopSyncProjectLoadTicket): boolean {
    return (
      dialogOpen.value
      && projectLoadCycle.isCurrent(loadTicket, currentAuthUserId())
    )
  }

  function invalidateProjectLoads(
    reason: DesktopSyncProjectLoadInvalidation,
    { clearPermission = false } = {},
  ) {
    projectLoadCycle.invalidate(reason)
    loadingProjects.value = false
    projects.value = []
    selectedProjectRefs.value = []
    errorMessage.value = ''
    policyDisabled.value = false
    if (clearPermission) {
      permissionMessage.value = ''
      permissionRefreshRequired.value = false
    }
  }

  function applyState(nextState: DesktopSyncState) {
    state.value = nextState
    if (nextState.status !== 'permission_changed') return

    invalidateProjectLoads('permission_changed')
    permissionMessage.value = nextState.message || DEFAULT_PERMISSION_MESSAGE
    permissionRefreshRequired.value = true
  }

  async function initialize() {
    if (!bridge.value) return
    if (initialization) return initialization

    initialization = (async () => {
      try {
        const [nextCapabilities, nextState] = await Promise.all([
          bridge.value!.getCapabilities(),
          bridge.value!.getSyncState(),
        ])
        capabilities.value = nextCapabilities
        applyState(nextState)
        errorMessage.value = ''
      } catch (error) {
        capabilities.value = null
        errorMessage.value = error instanceof Error ? error.message : '桌面同步能力暂不可用'
      }
    })()

    try {
      await initialization
    } finally {
      initialization = null
    }
  }

  async function loadProjects({ afterPermissionChange = false } = {}) {
    const requestedUserId = currentAuthUserId()
    if (!bridge.value || !dialogOpen.value || !requestedUserId) return
    const loadTicket = projectLoadCycle.begin(requestedUserId)
    loadingProjects.value = true
    errorMessage.value = ''
    policyDisabled.value = false
    try {
      const policy = await fetchDesktopSyncPolicy()
      if (!isCurrentProjectLoad(loadTicket)) return
      syncPolicy.value = policy
      if (policy.enabled !== true || policy.enabledForCurrentUser === false) {
        throw new Error('本地同步未启用或当前账号无权限')
      }
      const allowedProjects = await fetchDesktopSyncProjects()
      if (!isCurrentProjectLoad(loadTicket)) return
      projects.value = allowedProjects
      const allowedRefs = new Set(allowedProjects.map((project) => project.projectRef))
      selectedProjectRefs.value = selectedProjectRefs.value.filter((projectRef) => allowedRefs.has(projectRef))
      const shouldAutoStart = Boolean(
        !afterPermissionChange
          && autoStartAttemptedUserId !== requestedUserId
          && policy.enabledByDefault
          && state.value?.localRoot
          && !isSyncing.value,
      )
      if (shouldAutoStart) {
        if (!selectedProjectRefs.value.length) {
          selectedProjectRefs.value = allowedProjects.map((project) => project.projectRef)
        }
        if (selectedProjectRefs.value.length) {
          autoStartAttemptedUserId = requestedUserId
          globalThis.setTimeout(() => {
            if (dialogOpen.value && currentAuthUserId() === requestedUserId) start()
          }, 0)
        }
      }
      if (afterPermissionChange) {
        permissionRefreshRequired.value = false
        permissionMessage.value = '同步权限范围已重新检查，请重新选择需要同步的项目。'
      }
    } catch (error) {
      if (!isCurrentProjectLoad(loadTicket)) return
      projects.value = []
      selectedProjectRefs.value = []
      syncPolicy.value = null
      const message = error instanceof Error ? error.message : '同步项目加载失败'
      errorMessage.value = message
      policyDisabled.value = message.includes('未启用') || message.includes('disabled')
      if (afterPermissionChange) permissionRefreshRequired.value = true
    } finally {
      if (isCurrentProjectLoad(loadTicket)) {
        loadingProjects.value = false
      }
    }
  }

  async function setDialogOpen(visible: boolean) {
    dialogOpen.value = visible
    if (!visible) {
      invalidateProjectLoads('dialog_close')
      return
    }

    await initialize()
    if (!dialogOpen.value || !bridge.value || !isAuthenticated.value) return
    if (permissionRefreshRequired.value) return
    await loadProjects()
  }

  async function refreshPolicy() {
    await loadProjects({ afterPermissionChange: true })
  }

  async function chooseFolder() {
    if (!bridge.value || actionPending.value) return
    actionPending.value = true
    errorMessage.value = ''
    try {
      const localRoot = await bridge.value.selectSyncFolder()
      if (localRoot) applyState(await bridge.value.getSyncState())
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '无法选择本地文件夹'
    } finally {
      actionPending.value = false
    }
  }

  function start() {
    if (!bridge.value || !canStart.value) return
    const userId = authStore.user?.id
    if (!userId) {
      errorMessage.value = '登录状态已失效，请重新登录'
      return
    }

    const desktopBridge = bridge.value
    startPending.value = true
    errorMessage.value = ''
    try {
      const authToken = getAuthToken()
      if (!authToken) throw new Error('登录状态已失效，请重新登录')
      void desktopBridge.startSync({
        authToken,
        userId,
        projectRefs: [...selectedProjectRefs.value],
      }).then(applyState).catch((error: unknown) => {
        errorMessage.value = error instanceof Error ? error.message : '无法开始同步'
      }).finally(() => {
        startPending.value = false
      })
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '无法开始同步'
      startPending.value = false
    }
  }

  async function pause() {
    if (!bridge.value || actionPending.value || (!isSyncing.value && !startPending.value)) return
    actionPending.value = true
    errorMessage.value = ''
    try {
      applyState(await bridge.value.pauseSync())
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '无法暂停同步'
    } finally {
      actionPending.value = false
    }
  }

  async function openFolder() {
    if (!bridge.value || !state.value?.localRoot || actionPending.value) return
    actionPending.value = true
    errorMessage.value = ''
    try {
      await bridge.value.openSyncFolder()
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '无法打开本地文件夹'
    } finally {
      actionPending.value = false
    }
  }

  onMounted(() => {
    if (!bridge.value) return
    unsubscribe = bridge.value.onSyncState(applyState)
    void initialize()
  })

  watch(
    () => [authStore.status, authStore.user?.id || ''] as const,
    ([nextStatus, nextUserId], [previousStatus, previousUserId]) => {
      if (nextStatus === previousStatus && nextUserId === previousUserId) return
      invalidateProjectLoads('auth_change', { clearPermission: true })
      autoStartAttemptedUserId = ''
      if (dialogOpen.value && nextStatus === 'authenticated' && nextUserId) {
        void loadProjects()
      }
    },
    { flush: 'sync' },
  )

  onBeforeUnmount(() => {
    dialogOpen.value = false
    invalidateProjectLoads('unmount')
    unsubscribe?.()
    unsubscribe = null
  })

  return {
    capabilities,
    state,
    projects,
    syncPolicy,
    selectedProjectRefs,
    loadingProjects,
    actionPending,
    startPending,
    errorMessage,
    permissionMessage,
    permissionRefreshRequired,
    policyDisabled,
    isDesktop,
    isAuthenticated,
    isSyncing,
    projectSelectionDisabled,
    canStart,
    setDialogOpen,
    refreshPolicy,
    chooseFolder,
    start,
    pause,
    openFolder,
  }
}

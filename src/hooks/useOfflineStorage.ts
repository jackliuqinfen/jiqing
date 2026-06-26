import { ref } from 'vue'
import type { CostAuditItem, DragMoveDto } from '@/types'
import type { KanbanStage } from '@/types'

const STORAGE_KEY = 'cost_audit_offline_snapshot'
const SYNC_QUEUE_KEY = 'cost_audit_sync_queue'

interface SyncAction {
  type: 'drag_move' | 'create' | 'update' | 'delete'
  payload: unknown
  timestamp: number
}

/**
 * 离线存储 hook
 *
 * 策略：
 * - 在线时每次数据变更后自动写入 LocalStorage 快照（兜底）
 * - 断网时所有操作仅写入本地队列 + 快照
 * - 联网后自动执行增量同步（逐条回放队列中的操作）
 */
export function useOfflineStorage() {
  const pendingSyncCount = ref(0)

  /** 保存数据快照到 LocalStorage */
  function saveSnapshot(items: CostAuditItem[]): void {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
    } catch (e) {
      console.warn('[OfflineStorage] 快照保存失败，可能超出存储上限', e)
    }
  }

  /** 加载数据快照 */
  function loadSnapshot(): CostAuditItem[] | null {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      return raw ? JSON.parse(raw) : null
    } catch {
      return null
    }
  }

  /** 清空快照 */
  function clearSnapshot(): void {
    localStorage.removeItem(STORAGE_KEY)
  }

  /** 追加同步队列 */
  function enqueueAction(action: Omit<SyncAction, 'timestamp'>): void {
    try {
      const raw = localStorage.getItem(SYNC_QUEUE_KEY)
      const queue: SyncAction[] = raw ? JSON.parse(raw) : []
      queue.push({ ...action, timestamp: Date.now() })
      localStorage.setItem(SYNC_QUEUE_KEY, JSON.stringify(queue))
      pendingSyncCount.value = queue.length
    } catch (e) {
      console.warn('[OfflineStorage] 同步队列写入失败', e)
    }
  }

  /** 获取同步队列 */
  function getSyncQueue(): SyncAction[] {
    try {
      const raw = localStorage.getItem(SYNC_QUEUE_KEY)
      return raw ? JSON.parse(raw) : []
    } catch {
      return []
    }
  }

  /** 清空同步队列 */
  function clearSyncQueue(): void {
    localStorage.removeItem(SYNC_QUEUE_KEY)
    pendingSyncCount.value = 0
  }

  /** 恢复队列计数 */
  function restoreCount(): void {
    pendingSyncCount.value = getSyncQueue().length
  }

  return {
    pendingSyncCount,
    saveSnapshot,
    loadSnapshot,
    clearSnapshot,
    enqueueAction,
    getSyncQueue,
    clearSyncQueue,
    restoreCount,
  }
}

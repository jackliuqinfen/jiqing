import { onMounted, onUnmounted, nextTick } from 'vue'
import Sortable from 'sortablejs'
import type { KanbanStage, CostAuditItem } from '@/types'
import { MessagePlugin } from '@/ui/message'

export interface DragCallbacks {
  /** 是否禁用拖拽（未登录只读模式） */
  disabled?: boolean
  /** 校验是否允许拖入目标列 — 返回 false 则拦截 */
  canMove: (cardId: string, from: KanbanStage, to: KanbanStage) => boolean
  /** 拖拽完成回调 */
  onDragEnd: (cardId: string, from: KanbanStage, to: KanbanStage, newIndex: number) => void
}

/**
 * 看板拖拽 hook — 封装 SortableJS
 *
 * 业务流转校验规则（前端硬编码拦截）：
 * - 跨列拖拽触发 canMove 校验
 * - 禁止报审 → 直接跳至二审/定案/归档
 * - 初审/复审可回退至「报审待受理」（补资料场景）
 * - 归档列完全禁用拖拽（sort/pull/put 全部关闭）
 * - 同列允许自由排序
 */
export function useKanbanDrag(callbacks: DragCallbacks) {
  const instances: Sortable[] = []

  function initDrag() {
    // 未登录只读模式：不初始化拖拽
    if (callbacks.disabled) return

    // 对所有未锁定的列体初始化 Sortable
    const bodies = document.querySelectorAll<HTMLElement>('.kanban-column-body')

    bodies.forEach((body) => {
      const column = body.closest<HTMLElement>('.kanban-column')
      const stage = column?.getAttribute('data-stage') as KanbanStage | undefined
      const isLocked = column?.getAttribute('data-locked') === 'true'

      if (!stage) return

      // 归档列/锁定列/只读模式：完全禁用拖拽（不创建实例）
      if (isLocked || callbacks.disabled) return

      const instance = Sortable.create(body, {
        group: {
          name: 'kanban',
          pull: true,
          put: (to, _from, dragEl) => {
            const cardId = dragEl.getAttribute('data-card-id') || ''
            const fromStage = dragEl.getAttribute('data-stage') as KanbanStage
            const toStage = to.el
              .closest<HTMLElement>('.kanban-column')
              ?.getAttribute('data-stage') as KanbanStage
            if (!toStage || !fromStage || !cardId) return false
            return callbacks.canMove(cardId, fromStage, toStage)
          },
        },
        animation: 200,
        easing: 'cubic-bezier(0.16, 1, 0.3, 1)',
        ghostClass: 'kanban-ghost',
        dragClass: 'kanban-drag',
        chosenClass: 'kanban-chosen',
        handle: '.kanban-card-handle',
        forceFallback: false,
        fallbackTolerance: 3,
        scroll: true,
        scrollSensitivity: 30,
        scrollSpeed: 10,
        bubbleScroll: true,

        onStart(evt) {
          const cardId = evt.item.getAttribute('data-card-id') || ''
          const fromStage = evt.from
            .closest<HTMLElement>('.kanban-column')
            ?.getAttribute('data-stage') as KanbanStage
          evt.item.setAttribute('data-from-stage', fromStage)
          evt.item.setAttribute('data-card-id', cardId)
        },

        onEnd(evt) {
          const cardId = evt.item.getAttribute('data-card-id') || ''
          const fromStage = evt.item.getAttribute('data-from-stage') as KanbanStage
          const toEl = evt.to.closest<HTMLElement>('.kanban-column')
          const toStage = toEl?.getAttribute('data-stage') as KanbanStage

          if (!toStage || !cardId) return

          // 同列排序
          if (fromStage === toStage) {
            callbacks.onDragEnd(cardId, fromStage, toStage, evt.newDraggableIndex ?? 0)
            return
          }

          // 跨列移动 — 再次校验
          if (!callbacks.canMove(cardId, fromStage, toStage)) {
            // Sortable 会自动回退 DOM，无需手动还原
            MessagePlugin.warning('操作不允许：当前流程阶段不可直接跳转至目标列')
            return
          }

          callbacks.onDragEnd(cardId, fromStage, toStage, evt.newDraggableIndex ?? 0)
        },
      })

      instances.push(instance)
    })
  }

  function destroy() {
    instances.forEach((inst) => inst.destroy())
    instances.length = 0
  }

  function refresh() {
    destroy()
    nextTick(() => initDrag())
  }

  onMounted(() => {
    // 延迟初始化确保 DOM 渲染完成
    setTimeout(() => initDrag(), 100)
  })

  onUnmounted(() => {
    destroy()
  })

  return { initDrag, destroy, refresh }
}

/**
 * 业务流转校验函数（纯函数，供 canMove 回调使用）
 */
export function validateStageMove(
  card: CostAuditItem,
  from: KanbanStage,
  to: KanbanStage
): { allowed: boolean; reason?: string } {
  // 归档列锁定：不可移动
  if (from === 'archived') {
    return { allowed: false, reason: '已归档项目不可移动' }
  }

  // 禁止拖入归档列（归档操作应由专门按钮触发）
  if (to === 'archived') {
    return { allowed: false, reason: '归档操作请使用归档按钮' }
  }

  // 同列允许自由排序
  if (from === to) return { allowed: true }

  // 禁止报审阶段直接拖拽至二审/定案/归档
  if (from === 'submitted') {
    if (to === 'second_audit' || to === 'conclusion') {
      return { allowed: false, reason: '报审项目需先经一审方可进入二审/定案阶段' }
    }
  }

  // 初审/复审卡片可回退至「报审待受理」（补资料场景）
  if ((from === 'first_audit' || from === 'second_audit') && to === 'submitted') {
    return { allowed: true }
  }

  // 一审可进入二审
  if (from === 'first_audit' && to === 'second_audit') {
    return { allowed: true }
  }

  // 二审可进入定案
  if (from === 'second_audit' && to === 'conclusion') {
    return { allowed: true }
  }

  // 允许一审直接进入定案（快速通道）
  if (from === 'first_audit' && to === 'conclusion') {
    return { allowed: true }
  }

  // 禁止定案回退
  if (from === 'conclusion' && to === 'submitted') {
    return { allowed: false, reason: '定案项目不可回退至报审阶段' }
  }

  // 其他未定义跳转默认拒绝
  return { allowed: false, reason: '不支持的流程跳转' }
}

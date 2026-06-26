import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  CostAuditItem,
  KanbanStage,
  KanbanColumnDef,
  FilterConditions,
  StatisticsData,
  CreateAuditItemDto,
  UpdateAuditItemDto,
  DragMoveDto,
} from '@/types'
import { fetchAllItems, createItem, updateItem, deleteItem, dragMoveItem } from '@/api/kanban'
import { isOverdue } from '@/utils/date'
import { MessagePlugin } from '@/ui/message'

// ============================================================
// 5 列标准造价审核流程定义
// ============================================================

const STAGE_CONFIG: { id: KanbanStage; title: string; locked: boolean; color: string }[] = [
  { id: 'submitted', title: '报审待受理', locked: false, color: '#0052D9' },
  { id: 'first_audit', title: '一级初审（事务所）', locked: false, color: '#ED7B2F' },
  { id: 'second_audit', title: '二级复审（业主）', locked: false, color: '#E34D59' },
  { id: 'conclusion', title: '待出具定案结论', locked: false, color: '#029CD4' },
  { id: 'archived', title: '审计办结归档', locked: true, color: '#8C8C8C' },
]

// ============================================================
// 默认筛选条件
// ============================================================

const DEFAULT_FILTER: FilterConditions = {
  keyword: '',
  contractor: '',
  priority: '',
  category: '',
  auditUnit: '',
  docStatus: '',
  onlyOverdue: false,
  onlyDisputed: false,
}

// ============================================================
// Kanban Store
// ============================================================

export const useKanbanStore = defineStore('kanban', () => {
  // ===================== 持久化业务数据 =====================

  /** 全量项目数据 Map（key = id） */
  const itemsMap = ref<Map<string, CostAuditItem>>(new Map())

  /** 看板列定义 */
  const columns = ref<KanbanColumnDef[]>(
    STAGE_CONFIG.map((s) => ({
      id: s.id,
      title: s.title,
      cardIds: [],
      locked: s.locked,
      dragOutDisabled: s.locked,
    }))
  )

  // ===================== UI 临时状态 =====================

  const loading = ref(false)
  const error = ref<string | null>(null)
  const initialized = ref(false)

  /** 筛选条件 */
  const filters = ref<FilterConditions>({ ...DEFAULT_FILTER, keyword: '', contractor: '', priority: '', category: '', auditUnit: '', docStatus: '', onlyOverdue: false, onlyDisputed: false })

  /** 编辑弹窗 */
  const editModalVisible = ref(false)
  const editModalMode = ref<'create' | 'edit'>('create')
  const editModalItem = ref<CostAuditItem | null>(null)

  // ===================== Getters =====================

  /** 所有项目列表 */
  const allItems = computed<CostAuditItem[]>(() =>
    Array.from(itemsMap.value.values())
  )

  /** 根据筛选条件过滤后的项目列表 */
  const filteredItems = computed<CostAuditItem[]>(() => {
    let list = allItems.value
    const f = filters.value

    // 模糊搜索：项目名、楼栋、结算编号
    if (f.keyword.trim()) {
      const kw = f.keyword.trim().toLowerCase()
      list = list.filter(
        (item) =>
          item.projectName.toLowerCase().includes(kw) ||
          item.sectionBuilding.toLowerCase().includes(kw) ||
          item.settlementNo.toLowerCase().includes(kw)
      )
    }

    // 经办人筛选
    if (f.contractor) {
      list = list.filter((item) => item.contractor.name === f.contractor)
    }

    // 紧急等级筛选
    if (f.priority) {
      list = list.filter((item) => item.priority === f.priority)
    }

    // 工程分类筛选
    if (f.category) {
      list = list.filter((item) => item.category === f.category)
    }

    // 审计单位筛选（一审或二审单位）
    if (f.auditUnit) {
      list = list.filter(
        (item) =>
          item.firstAudit.companyName.includes(f.auditUnit) ||
          item.secondAudit.department.includes(f.auditUnit)
      )
    }

    // 资料状态筛选
    if (f.docStatus) {
      list = list.filter((item) => item.docStatus === f.docStatus)
    }

    // 快捷筛选：超期督办
    if (f.onlyOverdue) {
      list = list.filter((item) => isOverdue(item.deadline.auditDeadline))
    }

    // 快捷筛选：争议项目
    if (f.onlyDisputed) {
      list = list.filter((item) => item.remark.dispute.trim().length > 0)
    }

    return list
  })

  /** 过滤后的项目 ID Set */
  const filteredItemIds = computed<Set<string>>(() => {
    return new Set(filteredItems.value.map((i) => i.id))
  })

  /** 各列过滤后的卡片列表（按 cardIds 顺序排列） */
  const columnCards = computed(() => {
    const visibleIds = filteredItemIds.value
    return columns.value.map((col) => {
      const allItemsById = new Map(allItems.value.map((i) => [i.id, i]))
      // 按 cardIds 顺序收集仍属于该列且通过筛选的卡片
      const ordered = col.cardIds
        .map((id) => allItemsById.get(id))
        .filter(
          (item): item is CostAuditItem =>
            !!item && item.stage === col.id && visibleIds.has(item.id)
        )
      const orderedIds = new Set(ordered.map((i) => i.id))
      // 兜底：新数据可能未出现在 cardIds 中，追加到末尾
      const remaining = filteredItems.value.filter(
        (item) => item.stage === col.id && !orderedIds.has(item.id)
      )
      return {
        ...col,
        cards: [...ordered, ...remaining],
      }
    })
  })

  /** 全局统计数据（前端纯计算，不请求后端） */
  const statistics = computed<StatisticsData>(() => {
    const items = allItems.value
    const inAudit = items.filter(
      (i) => i.stage === 'first_audit' || i.stage === 'second_audit'
    )

    const columnCounts: Record<KanbanStage, number> = {
      submitted: 0,
      first_audit: 0,
      second_audit: 0,
      conclusion: 0,
      archived: 0,
    }
    items.forEach((i) => {
      columnCounts[i.stage]++
    })

    return {
      totalProjects: items.length,
      inAuditProjects: inAudit.length,
      completedProjects: items.filter((i) => i.isArchived).length,
      overdueProjects: items.filter((i) => isOverdue(i.deadline.auditDeadline)).length,
      totalSubmittedAmount: items.reduce((s, i) => s + i.amount.submittedAmount, 0),
      totalFirstCutAmount: items.reduce((s, i) => {
        const cut = i.amount.submittedAmount - i.amount.firstAuditAmount
        return s + (cut > 0 ? cut : 0)
      }, 0),
      totalSecondCutAmount: items.reduce((s, i) => {
        const cut = i.amount.firstAuditAmount - i.amount.secondAuditAmount
        return s + (cut > 0 ? cut : 0)
      }, 0),
      columnCounts,
    }
  })

  /** 所有经办人列表（供筛选下拉） */
  const contractorOptions = computed<string[]>(() => {
    const names = new Set<string>()
    allItems.value.forEach((i) => names.add(i.contractor.name))
    return Array.from(names)
  })

  /** 所有审计单位列表（供筛选下拉） */
  const auditUnitOptions = computed<string[]>(() => {
    const units = new Set<string>()
    allItems.value.forEach((i) => {
      units.add(i.firstAudit.companyName)
      units.add(i.secondAudit.department)
    })
    return Array.from(units).filter(Boolean)
  })

  // ===================== Actions =====================

  /** 初始化：加载全量数据 */
  async function loadItems() {
    if (loading.value) return
    loading.value = true
    error.value = null

    try {
      const res = await fetchAllItems()
      if (res.success) {
        const map = new Map<string, CostAuditItem>()
        res.data.forEach((item) => map.set(item.id, item))
        itemsMap.value = map
        rebuildColumns()
        initialized.value = true
      } else {
        error.value = res.error || '加载失败'
        // 加载失败时，不标记为已初始化（将使用模拟数据降级）
        initialized.value = false
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : '未知错误'
      initialized.value = false
    } finally {
      loading.value = false
    }
  }

  /** 用模拟数据初始化 */
  function initWithMockData(items: CostAuditItem[]) {
    const map = new Map<string, CostAuditItem>()
    items.forEach((item) => map.set(item.id, item))
    itemsMap.value = map
    rebuildColumns()
    initialized.value = true
    loading.value = false
  }

  /** 根据 itemsMap 重建列卡排序，同时保留已有的列内顺序 */
  function rebuildColumns() {
    const previousOrder = new Map<KanbanStage, string[]>(
      columns.value.map((c) => [c.id, [...c.cardIds]])
    )

    columns.value = STAGE_CONFIG.map((stage) => {
      const existingIds = previousOrder.get(stage.id) ?? []
      const itemsInStage = allItems.value.filter((i) => i.stage === stage.id)
      const itemIds = new Set(itemsInStage.map((i) => i.id))

      // 保留仍存在于该列的 id 顺序
      const ordered = existingIds.filter((id) => itemIds.has(id))
      const orderedSet = new Set(ordered)
      // 兜底：未在顺序中的新项目追加到末尾
      const remaining = itemsInStage
        .filter((i) => !orderedSet.has(i.id))
        .map((i) => i.id)

      return {
        id: stage.id,
        title: stage.title,
        cardIds: [...ordered, ...remaining],
        locked: stage.locked,
        dragOutDisabled: stage.locked,
      }
    })
  }

  /**
   * 调整列内卡片顺序（用于拖拽完成后的乐观更新）
   * 返回操作前的顺序快照，便于回滚
   */
  function updateColumnOrder(
    cardId: string,
    fromStage: KanbanStage,
    toStage: KanbanStage,
    newIndex: number
  ): { fromIds: string[]; toIds: string[] } | null {
    const fromCol = columns.value.find((c) => c.id === fromStage)
    const toCol = columns.value.find((c) => c.id === toStage)
    if (!fromCol || !toCol) return null

    const previous = {
      fromIds: [...fromCol.cardIds],
      toIds: [...toCol.cardIds],
    }

    // 从源列移除
    fromCol.cardIds = fromCol.cardIds.filter((id) => id !== cardId)

    if (fromStage === toStage) {
      // 同列排序：按 newIndex 插入
      const newIds = [...fromCol.cardIds]
      newIds.splice(newIndex, 0, cardId)
      fromCol.cardIds = newIds
    } else {
      // 跨列：插入目标列 newIndex 位置
      const newIds = [...toCol.cardIds]
      newIds.splice(newIndex, 0, cardId)
      toCol.cardIds = newIds
    }

    return previous
  }

  /** 乐观更新：新建项目 */
  async function handleCreate(dto: CreateAuditItemDto) {
    // 先乐观更新本地状态
    const tempItem: CostAuditItem = {
      id: crypto.randomUUID?.() || `temp-${Date.now()}`,
      ...dto,
      isArchived: dto.stage === 'archived',
      log: {
        updateTime: new Date().toISOString(),
        operator: dto.operator,
        operateType: 'create',
      },
    }
    itemsMap.value.set(tempItem.id, tempItem)
    rebuildColumns()

    // 后台同步
    const res = await createItem(dto)
    if (!res.success) {
      // 回滚
      itemsMap.value.delete(tempItem.id)
      rebuildColumns()
      MessagePlugin.error(`创建失败: ${res.error}`)
    } else {
      // 用服务端返回的真实数据替换临时数据，并保持列内位置
      itemsMap.value.delete(tempItem.id)
      itemsMap.value.set(res.data.id, res.data)
      columns.value.forEach((col) => {
        col.cardIds = col.cardIds.map((id) => (id === tempItem.id ? res.data.id : id))
      })
      MessagePlugin.success('项目创建成功')
    }
    return res
  }

  /** 乐观更新：编辑项目 */
  async function handleUpdate(dto: UpdateAuditItemDto) {
    const original = itemsMap.value.get(dto.id)
    if (!original) return { success: false, data: null as unknown as CostAuditItem, error: '项目不存在' }

    // 乐观更新
    const optimistic: CostAuditItem = { ...original, ...dto }
    itemsMap.value.set(dto.id, optimistic)
    rebuildColumns()

    const res = await updateItem(dto)
    if (!res.success) {
      // 回滚
      itemsMap.value.set(dto.id, original)
      rebuildColumns()
      MessagePlugin.error(`更新失败: ${res.error}`)
    } else {
      itemsMap.value.set(dto.id, res.data)
      rebuildColumns()
      MessagePlugin.success('更新成功')
    }
    return res
  }

  /** 乐观更新：删除项目 */
  async function handleDelete(id: string) {
    const original = itemsMap.value.get(id)
    if (!original) return

    itemsMap.value.delete(id)
    rebuildColumns()

    const res = await deleteItem(id)
    if (!res.success) {
      if (original) itemsMap.value.set(id, original)
      rebuildColumns()
      MessagePlugin.error(`删除失败: ${res.error}`)
    } else {
      MessagePlugin.success('项目已删除')
    }
  }

  /** 拖拽移动（乐观更新） */
  async function handleDragMove(dto: DragMoveDto) {
    const card = itemsMap.value.get(dto.cardId)
    if (!card) return

    const originalStage = card.stage

    // 乐观更新：先调整列内顺序，再改 stage 字段
    const previousOrder = updateColumnOrder(dto.cardId, originalStage, dto.toStage, dto.newIndex)
    card.stage = dto.toStage
    card.isArchived = dto.toStage === 'archived'
    card.log = {
      updateTime: new Date().toISOString(),
      operator: dto.operator,
      operateType: 'drag_move',
    }

    const res = await dragMoveItem(dto)
    if (!res.success) {
      // 回滚 stage 与顺序
      card.stage = originalStage
      card.isArchived = false
      if (previousOrder) {
        const fromCol = columns.value.find((c) => c.id === originalStage)
        const toCol = columns.value.find((c) => c.id === dto.toStage)
        if (fromCol) fromCol.cardIds = previousOrder.fromIds
        if (toCol) toCol.cardIds = previousOrder.toIds
      }
      MessagePlugin.error('移动失败，已回退')
    } else {
      MessagePlugin.success('移动成功')
    }
  }

  /** 重置筛选条件 */
  function resetFilters() {
    filters.value = {
      keyword: '',
      contractor: '',
      priority: '',
      category: '',
      auditUnit: '',
      docStatus: '',
      onlyOverdue: false,
      onlyDisputed: false,
    }
  }

  /** 打开编辑弹窗 */
  function openEditModal(mode: 'create' | 'edit', item?: CostAuditItem) {
    editModalMode.value = mode
    editModalItem.value = item || null
    editModalVisible.value = true
  }

  /** 关闭编辑弹窗 */
  function closeEditModal() {
    editModalVisible.value = false
    editModalItem.value = null
  }

  return {
    // State
    itemsMap,
    columns,
    loading,
    error,
    initialized,
    filters,
    editModalVisible,
    editModalMode,
    editModalItem,

    // Getters
    allItems,
    filteredItems,
    filteredItemIds,
    columnCards,
    statistics,
    contractorOptions,
    auditUnitOptions,

    // Actions
    loadItems,
    initWithMockData,
    rebuildColumns,
    handleCreate,
    handleUpdate,
    handleDelete,
    handleDragMove,
    resetFilters,
    openEditModal,
    closeEditModal,
  }
})

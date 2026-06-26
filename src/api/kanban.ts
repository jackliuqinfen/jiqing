import { getSupabaseClient, TABLE_NAME, rowToItem, itemToRow, requireAuthForMutation } from './supabase'
import type {
  CostAuditItem,
  CreateAuditItemDto,
  UpdateAuditItemDto,
  DragMoveDto,
  BatchUpdateDto,
  ApiResponse,
} from '@/types'
import { generateUUID } from '@/utils/format'
import { todayISO } from '@/utils/date'

// ============================================================
// CRUD 操作：增 / 删 / 改 / 查 / 批量更新
// ============================================================

/**
 * 获取全量项目数据（页面初始化仅请求一次）
 */
export async function fetchAllItems(): Promise<ApiResponse<CostAuditItem[]>> {
  try {
    const client = getSupabaseClient()
    const { data, error } = await client
      .from(TABLE_NAME)
      .select('*')
      .order('updated_at', { ascending: false })

    if (error) throw error

    const items: CostAuditItem[] = (data || []).map(rowToItem)
    return { success: true, data: items }
  } catch (err) {
    const msg = err instanceof Error ? err.message : '获取数据失败'
    console.error('[API] fetchAllItems 失败:', msg)
    return { success: false, data: [], error: msg }
  }
}

/**
 * 新建项目
 */
export async function createItem(dto: CreateAuditItemDto): Promise<ApiResponse<CostAuditItem>> {
  try {
    requireAuthForMutation('新增项目')
    const client = getSupabaseClient()
    const id = generateUUID()
    const now = todayISO()

    const newItem: CostAuditItem = {
      id,
      projectName: dto.projectName,
      sectionBuilding: dto.sectionBuilding,
      settlementNo: dto.settlementNo,
      category: dto.category,
      priority: dto.priority,
      contractor: dto.contractor,
      amount: dto.amount,
      firstAudit: dto.firstAudit,
      secondAudit: dto.secondAudit,
      deadline: dto.deadline,
      docStatus: dto.docStatus,
      stage: dto.stage,
      remark: dto.remark,
      isArchived: dto.stage === 'archived',
      log: {
        updateTime: now,
        operator: dto.operator,
        operateType: 'create',
      },
    }

    const { error } = await client
      .from(TABLE_NAME)
      .insert({ id, data: newItem, updated_at: now })

    if (error) throw error

    return { success: true, data: newItem }
  } catch (err) {
    const msg = err instanceof Error ? err.message : '创建失败'
    console.error('[API] createItem 失败:', msg)
    return { success: false, data: null as unknown as CostAuditItem, error: msg }
  }
}

/**
 * 编辑项目（部分更新）
 */
export async function updateItem(dto: UpdateAuditItemDto): Promise<ApiResponse<CostAuditItem>> {
  try {
    requireAuthForMutation('编辑项目')
    const client = getSupabaseClient()

    // 先获取现有数据
    const { data: existing, error: fetchErr } = await client
      .from(TABLE_NAME)
      .select('*')
      .eq('id', dto.id)
      .single()

    if (fetchErr || !existing) {
      throw new Error('项目不存在')
    }

    const current = rowToItem(existing)
    const updated: CostAuditItem = {
      ...current,
      ...dto,
      log: {
        updateTime: todayISO(),
        operator: dto.operator,
        operateType: 'update',
      },
    }

    const { error } = await client
      .from(TABLE_NAME)
      .update({ data: updated, updated_at: new Date().toISOString() })
      .eq('id', dto.id)

    if (error) throw error

    return { success: true, data: updated }
  } catch (err) {
    const msg = err instanceof Error ? err.message : '更新失败'
    console.error('[API] updateItem 失败:', msg)
    return { success: false, data: null as unknown as CostAuditItem, error: msg }
  }
}

/**
 * 删除项目
 */
export async function deleteItem(id: string): Promise<ApiResponse<null>> {
  try {
    requireAuthForMutation('删除项目')
    const client = getSupabaseClient()
    const { error } = await client.from(TABLE_NAME).delete().eq('id', id)
    if (error) throw error
    return { success: true, data: null }
  } catch (err) {
    const msg = err instanceof Error ? err.message : '删除失败'
    console.error('[API] deleteItem 失败:', msg)
    return { success: false, data: null, error: msg }
  }
}

/**
 * 拖拽移动单个卡片
 * 更新 stage 字段并在当前列内调整排序
 */
export async function dragMoveItem(dto: DragMoveDto): Promise<ApiResponse<CostAuditItem>> {
  return updateItem({
    id: dto.cardId,
    stage: dto.toStage,
    isArchived: dto.toStage === 'archived',
    operator: dto.operator,
  } as UpdateAuditItemDto)
}

/**
 * 批量更新（多卡拖拽同步）
 *
 * 实现策略：逐个读取现有数据、合并变更字段、再写回，避免覆盖整个 JSONB。
 */
export async function batchUpdateItems(
  dto: BatchUpdateDto
): Promise<ApiResponse<null>> {
  try {
    const client = getSupabaseClient()

    const results = await Promise.allSettled(
      dto.updates.map(async (update) => {
        // 1) 读取现有数据
        const { data: existing, error: fetchErr } = await client
          .from(TABLE_NAME)
          .select('data')
          .eq('id', update.cardId)
          .single()

        if (fetchErr || !existing) {
          throw new Error(`项目不存在: ${update.cardId}`)
        }

        const currentData = existing.data as CostAuditItem
        const mergedData: CostAuditItem = {
          ...currentData,
          stage: update.toStage,
          isArchived: update.toStage === 'archived',
          log: {
            updateTime: todayISO(),
            operator: dto.operator,
            operateType: 'drag_move',
          },
        }

        // 2) 合并后写回
        const { error: updateErr } = await client
          .from(TABLE_NAME)
          .update({ data: mergedData, updated_at: new Date().toISOString() })
          .eq('id', update.cardId)

        if (updateErr) throw updateErr
      })
    )

    const failed = results.filter((r) => r.status === 'rejected')
    if (failed.length > 0) {
      console.warn(`[API] 批量更新部分失败: ${failed.length} 条`)
    }

    return { success: true, data: null }
  } catch (err) {
    const msg = err instanceof Error ? err.message : '批量更新失败'
    return { success: false, data: null, error: msg }
  }
}

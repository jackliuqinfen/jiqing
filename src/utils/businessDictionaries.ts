export type BusinessOption = {
  label: string
  value: string
  color: string
}

export const projectStatusOptions: BusinessOption[] = [
  { label: '未开始', value: 'not_started', color: 'gray' },
  { label: '待处理', value: 'pending', color: 'orange' },
  { label: '进行中', value: 'active', color: 'arcoblue' },
  { label: '已完成', value: 'completed', color: 'green' },
  { label: '已暂停', value: 'paused', color: 'red' },
  { label: '已归档', value: 'archived', color: 'gray' },
]

export const auditStageOptions: BusinessOption[] = [
  { label: '报审待受理', value: 'submitted', color: 'arcoblue' },
  { label: '一级初审', value: 'first_audit', color: 'orange' },
  { label: '二级复审', value: 'second_audit', color: 'magenta' },
  { label: '定案结论', value: 'conclusion', color: 'cyan' },
  { label: '办结归档', value: 'archived', color: 'green' },
]

export const materialStatusOptions: BusinessOption[] = [
  { label: '待补资料', value: 'missing', color: 'orange' },
  { label: '已提交', value: 'submitted', color: 'arcoblue' },
  { label: '资料齐全', value: 'complete', color: 'green' },
  { label: '资料齐全', value: 'completed', color: 'green' },
  { label: '资料齐全', value: 'confirmed', color: 'green' },
  { label: '需更正', value: 'rejected', color: 'red' },
  { label: '待处理', value: 'pending', color: 'orange' },
  { label: '待处理', value: 'not_started', color: 'orange' },
]

export const settlementStatusOptions: BusinessOption[] = [
  { label: '未结算', value: 'not_started', color: 'gray' },
  { label: '结算中', value: 'pending', color: 'orange' },
  { label: '审核中', value: 'reviewing', color: 'arcoblue' },
  { label: '已确认', value: 'approved', color: 'green' },
  { label: '已付款', value: 'paid', color: 'green' },
  { label: '已退回', value: 'rejected', color: 'red' },
]

export const variationStatusOptions: BusinessOption[] = [
  { label: '待确认', value: 'pending', color: 'orange' },
  { label: '已确认', value: 'approved', color: 'green' },
  { label: '已驳回', value: 'rejected', color: 'red' },
]

export const userStatusOptions: BusinessOption[] = [
  { label: '正常使用', value: 'active', color: 'green' },
  { label: '已停用', value: 'disabled', color: 'gray' },
]

export const optionGroupLabels: Record<string, string> = {
  category: '项目分类',
  priority: '优先级',
  stage: '审计阶段',
  status: '项目状态',
  project_status: '项目状态',
  doc_status: '资料状态',
  material_status: '资料状态',
  settlement_status: '结算状态',
  user_status: '用户状态',
  conclusion_status: '确认状态',
}

export function findBusinessOption(options: BusinessOption[], value?: string | number | null) {
  const normalized = String(value ?? '')
  return options.find((item) => item.value === normalized)
}

export function businessLabel(options: BusinessOption[], value?: string | number | null, fallback = '待确认') {
  return findBusinessOption(options, value)?.label || fallback
}

export function businessColor(options: BusinessOption[], value?: string | number | null, fallback = 'gray') {
  return findBusinessOption(options, value)?.color || fallback
}

export function optionGroupLabel(value?: string | null) {
  if (!value) return '未设置选项组'
  return optionGroupLabels[value] || value
}

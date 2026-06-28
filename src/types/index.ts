// ============================================================
// 江苏集庆·工程管理系统 — 完整 TypeScript 类型定义
// 所有业务实体、看板列、筛选条件、API 接口强类型约束
// ============================================================

// --- 枚举类型 ---

/** 看板流程阶段（5 列标准造价审核流程，一一对应看板列 ID） */
export type KanbanStage = 'submitted' | 'first_audit' | 'second_audit' | 'conclusion' | 'archived'

/** 工程分类 */
export type ProjectCategory =
  | '竣工总结算'
  | '分部结算'
  | '现场签证'
  | '工程变更'
  | '土建造价'
  | '安装造价'
  | '市政结算'
  | '分包审核'

/** 优先级 S0~S3 */
export type PriorityLevel = 'S0' | 'S1' | 'S2' | 'S3'

/** 资料状态 */
export type DocStatus = '资料齐全' | '缺图纸' | '缺变更签证' | '资料退回补件'

/** 操作类型（日志追踪） */
export type OperateType = 'create' | 'update' | 'delete' | 'drag_move'

// --- 人员信息 ---

/** 经办人/审计师信息 */
export interface StaffInfo {
  name: string           // 姓名
  phone: string          // 联系电话
  avatar?: string        // 头像 URL（首字母自动生成兜底）
}

// --- 审计主体分区 ---

/** 一审信息（第三方造价事务所） */
export interface FirstAuditInfo {
  companyName: string    // 第三方咨询单位名称
  auditor: StaffInfo     // 初审造价师
}

/** 二审信息（建设单位业主内审） */
export interface SecondAuditInfo {
  department: string     // 建设单位内审部门
  auditor: StaffInfo     // 复审工程师
}

// --- 造价核心金额 ---

/** 金额数据块（统一保留两位小数） */
export interface AmountInfo {
  contractAmount: number        // 合同金额
  submittedAmount: number       // 送审结算金额
  firstAuditAmount: number      // 一审审定金额
  secondAuditAmount: number     // 二审审定金额
  auditDifference: number       // 审减差额
  finalPayable: number          // 定案应付工程款
  paidAmount: number            // 已回款金额
}

// --- 时限管控 ---

export interface DeadlineInfo {
  submitDate: string            // 报审提交日期 ISO 8601
  auditDeadline: string         // 审计办结截止日期 ISO 8601
}

// --- 业务备注 ---

export interface BizRemark {
  dispute: string               // 结算争议
  coordination: string          // 协调记录
}

// --- 操作日志附属字段 ---

export interface AuditLog {
  updateTime: string            // 更新时间 ISO 8601
  operator: string              // 操作人
  operateType: OperateType      // 操作类型
}

// ============================================================
// 核心业务实体：工程造价结算项目
// ============================================================

export interface CostAuditItem {
  /** 结算唯一 ID（主键，UUID） */
  id: string

  /** 工程基础元数据 */
  projectName: string           // 项目全称
  sectionBuilding: string       // 分部 / 楼栋
  settlementNo: string          // 结算编号
  category: ProjectCategory     // 工程分类
  priority: PriorityLevel       // 优先级 S0~S3

  /** 施工方经办人 */
  contractor: StaffInfo

  /** 造价核心金额 */
  amount: AmountInfo

  /** 一审信息 */
  firstAudit: FirstAuditInfo

  /** 二审信息 */
  secondAudit: SecondAuditInfo

  /** 时限管控 */
  deadline: DeadlineInfo

  /** 流程状态 */
  docStatus: DocStatus          // 资料状态
  stage: KanbanStage            // 当前所处流程列

  /** 业务备注 */
  remark: BizRemark

  /** 操作日志审计字段 */
  log: AuditLog

  /** 是否已归档（归档列专用判定） */
  isArchived: boolean
}

// ============================================================
// 看板列定义
// ============================================================

export interface KanbanColumnDef {
  id: KanbanStage
  title: string
  /** 列内卡片 ID 排序列表 */
  cardIds: string[]
  /** 是否锁定不可拖入/拖出 */
  locked?: boolean
  /** 是否禁用拖出 */
  dragOutDisabled?: boolean
}

// ============================================================
// 看板筛选条件
// ============================================================

export interface FilterConditions {
  keyword: string               // 模糊搜索：项目名、楼栋、结算编号
  contractor: string            // 经办人筛选
  priority: PriorityLevel | ''  // 紧急等级
  category: ProjectCategory | ''// 工程分类
  auditUnit: string             // 审计单位筛选
  docStatus: DocStatus | ''     // 资料状态
  /** 快捷筛选标记 */
  onlyOverdue: boolean          // 只显示超期督办
  onlyDisputed: boolean         // 只显示争议项目
}

// ============================================================
// 全局统计面板数据
// ============================================================

export interface StatisticsData {
  /** 数量维度 */
  totalProjects: number         // 总报审项目
  inAuditProjects: number       // 在审项目（一审+二审）
  completedProjects: number     // 已办结项目
  overdueProjects: number       // 超期督办项目

  /** 金额维度 */
  totalSubmittedAmount: number  // 总送审金额
  totalFirstCutAmount: number   // 累计一审审减总额
  totalSecondCutAmount: number  // 累计二审审减总额

  /** 各列任务数 */
  columnCounts: Record<KanbanStage, number>
}

// ============================================================
// API 请求/响应类型
// ============================================================

export interface ApiResponse<T> {
  success: boolean
  data: T
  error?: string
}

/** 新建项目请求体 */
export interface CreateAuditItemDto {
  projectName: string
  sectionBuilding: string
  settlementNo: string
  category: ProjectCategory
  priority: PriorityLevel
  contractor: StaffInfo
  amount: AmountInfo
  firstAudit: FirstAuditInfo
  secondAudit: SecondAuditInfo
  deadline: DeadlineInfo
  docStatus: DocStatus
  stage: KanbanStage
  remark: BizRemark
  operator: string
}

/** 编辑项目请求体（部分更新） */
export type UpdateAuditItemDto = Partial<CreateAuditItemDto> & { id: string; operator: string }

/** 拖拽移动请求体 */
export interface DragMoveDto {
  cardId: string
  fromStage: KanbanStage
  toStage: KanbanStage
  newIndex: number
  operator: string
}

/** 批量更新请求体 */
export interface BatchUpdateDto {
  updates: DragMoveDto[]
  operator: string
}

// ============================================================
// Auth 认证相关类型
// ============================================================

/** 用户资料 */
export interface UserProfile {
  id: string
  email: string
  displayName: string
  username: string
  role: AdminRole
  createdAt: string
}

/** 认证会话 */
export interface AuthSession {
  accessToken: string
  refreshToken: string
  expiresAt: number
  user: UserProfile
}

/** 登录请求（账号 + 密码） */
export interface LoginDto {
  username: string
  password: string
}

/** 注册请求（仅管理员可操作） */
export interface RegisterDto {
  username: string
  password: string
  confirmPassword: string
  displayName: string
  email: string
  role: AdminRole
}

/** 认证状态 */
export type AuthStatus = 'idle' | 'loading' | 'authenticated' | 'unauthenticated'

// ============================================================
// 管理员系统类型
// ============================================================

/** 管理员角色 */
export type AdminRole = 'admin' | 'editor' | 'viewer'

/** 后台管理用户（扩展现有 UserProfile） */
export interface AdminUser {
  id: string
  userId: string
  username: string
  displayName: string
  email: string
  role: AdminRole
  isActive: boolean
  createdAt: string
  updatedAt: string
}

/** 系统设置键 */
export type SystemSettingKey = 'registration_open' | 'login_rules' | 'system_name' | 'current_theme'

/** 系统设置值类型 */
export interface RegistrationSetting {
  enabled: boolean
  requireApproval: boolean
}

export interface LoginRulesSetting {
  minPasswordLength: number
  maxLoginAttempts: number
  sessionTimeoutMinutes: number
  allowConcurrentSessions: boolean
}

export interface ThemeSetting {
  themeKey: string
  darkMode: boolean
  compactMode: boolean
  applyScope: string
  brandColor?: string
  themePackage?: string
}

export interface ThemeOption {
  id: string
  themeKey: string
  themeName: string
  packageName: string
  previewColors: string[]
  applyScope: string
  isEnabled: boolean
  isDefault: boolean
  darkModeEnabled: boolean
  compactModeEnabled: boolean
}

export interface CurrentTheme extends ThemeSetting {
  theme: ThemeOption | null
}

export type SystemSettingValue = RegistrationSetting | LoginRulesSetting | ThemeSetting | string

/** 系统设置条目 */
export interface SystemSetting {
  key: SystemSettingKey
  value: SystemSettingValue
  updatedAt: string
  updatedBy: string
}

/** 创建用户请求体（管理员操作） */
export interface CreateAdminUserDto {
  username: string
  displayName: string
  email: string
  password: string
  role: AdminRole
}

/** 更新用户请求体（管理员操作） */
export interface UpdateAdminUserDto {
  id: string
  username?: string
  displayName?: string
  email?: string
  role?: AdminRole
  isActive?: boolean
  password?: string
}

/** 管理员统计数据 */
export interface AdminStats {
  totalUsers: number
  activeUsers: number
  adminCount: number
  totalProjects: number
  recentLogins: number
}

/** 系统操作日志 */
export interface OperationLogEntry {
  id: string
  userId: string
  username: string
  role: AdminRole | ''
  action: string
  targetType: string
  targetId: string
  result: 'success' | 'failed' | string
  ipAddress: string
  userAgent: string
  detail: Record<string, unknown>
  createdAt: string
}

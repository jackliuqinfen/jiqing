/**
 * Backend-compatible project lifecycle contracts. The string extension keeps
 * older persisted stages readable while preserving autocomplete for supported stages.
 */
export type ProjectLifecycleKnownStage =
  | 'awarded'
  | 'contract_signed'
  | 'under_construction'
  | 'completed_acceptance'
  | 'pending_submission'
  | 'first_audit'
  | 'second_audit'
  | 'conclusion'
  | 'archived'

export type ProjectLifecycleStage = ProjectLifecycleKnownStage | (string & {})

export interface ProjectLifecycleBlocker {
  code: string
  field: string
  message: string
  [key: string]: unknown
}

export interface ProjectLifecycleEvent {
  id: string
  projectId: string
  fromStage: ProjectLifecycleStage
  fromStageLabel: string
  toStage: ProjectLifecycleStage
  toStageLabel: string
  transitionType: string
  reason: string
  idempotencyKey: string
  lifecycleVersion: number
  actorId: string
  actorName: string
  payload: Record<string, unknown>
  createdAt: string
}

export interface ProjectLifecycleNextTransition {
  toStage: ProjectLifecycleStage
  toStageLabel: string
  blockers: ProjectLifecycleBlocker[]
}

export interface ProjectLifecycleSnapshot {
  projectId: string
  currentStage: ProjectLifecycleStage
  currentStageLabel: string
  lifecycleVersion: number
  nextTransition: ProjectLifecycleNextTransition | null
  blockers: ProjectLifecycleBlocker[]
  recentEvents: ProjectLifecycleEvent[]
}

export interface ProjectLifecycleValidateRequest {
  toStage?: ProjectLifecycleStage
}

export interface ProjectLifecycleValidateResponse {
  currentStage: ProjectLifecycleStage
  currentStageLabel: string
  currentVersion: number
  targetStage: ProjectLifecycleStage | ''
  targetStageLabel: string
  blockers: ProjectLifecycleBlocker[]
  canTransition: boolean
}

export interface ProjectLifecycleTransitionRequest {
  toStage: ProjectLifecycleStage
  expectedVersion: number
  idempotencyKey: string
  reason?: string
}

export interface ProjectLifecycleTransitionResult {
  projectId: string
  currentStage: ProjectLifecycleStage
  currentStageLabel: string
  lifecycleVersion: number
  event: ProjectLifecycleEvent
}

export interface ProjectLifecycleTransitionResponse {
  transition: ProjectLifecycleTransitionResult
  snapshot: ProjectLifecycleSnapshot
}

export interface ProjectLifecycleErrorPayload {
  success?: false
  error?: string
  code?: string
  blockers?: ProjectLifecycleBlocker[]
  currentStage?: ProjectLifecycleStage
  currentVersion?: number
  expectedVersion?: number
  missing?: string[]
  [key: string]: unknown
}

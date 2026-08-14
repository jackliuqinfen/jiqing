export type DesktopSyncStatus =
  | 'disabled'
  | 'waiting_for_login'
  | 'checking_policy'
  | 'syncing'
  | 'paused'
  | 'completed'
  | 'partial_failure'
  | 'permission_changed'
  | 'offline'

export interface DesktopSyncState {
  status: DesktopSyncStatus
  localRoot: string
  selectedProjectRefs: string[]
  completedFiles: number
  totalFiles: number
  failedFiles: number
  bytesDownloaded: number
  lastSuccessAt: string
  message: string
}

export interface DesktopSyncStartRequest {
  authToken: string
  userId: string
  projectRefs: string[]
}

export interface DesktopCapabilities {
  desktop: true
  protocolVersion: 1
  clientVersion: string
  releaseChannel: 'development' | 'internal-test' | 'production'
}

export type DesktopUpdateStatus =
  | 'unavailable'
  | 'idle'
  | 'checking'
  | 'available'
  | 'downloading'
  | 'downloaded'
  | 'up_to_date'
  | 'error'

export interface DesktopUpdateState {
  status: DesktopUpdateStatus
  currentVersion: string
  availableVersion: string
  progressPercent: number
  canCheck: boolean
  canInstall: boolean
  lastCheckedAt: string
  message: string
}

export type DesktopWorkspaceCommand =
  | 'workspace:back'
  | 'workspace:forward'
  | 'workspace:command-center'
  | 'workspace:restore-closed-tab'

export interface JiqingDesktopBridge {
  getCapabilities(): Promise<DesktopCapabilities>
  selectSyncFolder(): Promise<string>
  getSyncState(): Promise<DesktopSyncState>
  startSync(request: DesktopSyncStartRequest): Promise<DesktopSyncState>
  pauseSync(): Promise<DesktopSyncState>
  openSyncFolder(): Promise<void>
  getUpdateState(): Promise<DesktopUpdateState>
  checkForUpdates(): Promise<DesktopUpdateState>
  installUpdate(): Promise<void>
  onSyncState(listener: (state: DesktopSyncState) => void): () => void
  onUpdateState(listener: (state: DesktopUpdateState) => void): () => void
  onWorkspaceCommand(
    listener: (command: DesktopWorkspaceCommand) => void,
  ): () => void
}

declare global {
  interface Window {
    jiqingDesktop?: JiqingDesktopBridge
  }
}

export {}

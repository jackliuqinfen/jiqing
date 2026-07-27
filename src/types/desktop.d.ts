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

export interface JiqingDesktopBridge {
  getCapabilities(): Promise<DesktopCapabilities>
  selectSyncFolder(): Promise<string>
  getSyncState(): Promise<DesktopSyncState>
  startSync(request: DesktopSyncStartRequest): Promise<DesktopSyncState>
  pauseSync(): Promise<DesktopSyncState>
  openSyncFolder(): Promise<void>
  onSyncState(listener: (state: DesktopSyncState) => void): () => void
}

declare global {
  interface Window {
    jiqingDesktop?: JiqingDesktopBridge
  }
}

export {}

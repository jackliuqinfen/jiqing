const MIN_INTERVAL_SECONDS = 60
const MAX_INTERVAL_SECONDS = 3600
const DEFAULT_INTERVAL_SECONDS = 300
const STOP_STATUSES = new Set([
  'disabled',
  'permission_changed',
  'waiting_for_login',
])

function intervalSeconds(policy) {
  const raw = Number(policy?.pollIntervalSeconds)
  if (!Number.isFinite(raw)) return DEFAULT_INTERVAL_SECONDS
  return Math.max(MIN_INTERVAL_SECONDS, Math.min(MAX_INTERVAL_SECONDS, Math.trunc(raw)))
}
function isStopStatus(status) {
  return STOP_STATUSES.has(status)
}

export class SyncScheduler {
  constructor({
    controller,
    apiClient,
    setTimeoutImpl = setTimeout,
    clearTimeoutImpl = clearTimeout,
  }) {
    if (!controller || !apiClient || typeof setTimeoutImpl !== 'function' || typeof clearTimeoutImpl !== 'function') {
      throw new Error('invalid sync scheduler configuration')
    }
    this.controller = controller
    this.apiClient = apiClient
    this.setTimeoutImpl = setTimeoutImpl
    this.clearTimeoutImpl = clearTimeoutImpl
    this.timer = null
    this.request = null
    this.running = false
  }

  isArmed() {
    return Boolean(this.request)
  }

  arm(request, state) {
    this.stop()
    if (!request || isStopStatus(state?.status)) return
    this.request = { ...request, projectRefs: [...request.projectRefs] }
    void this.scheduleFromPolicy(request.authToken)
  }

  stop() {
    if (this.timer !== null) {
      this.clearTimeoutImpl(this.timer)
      this.timer = null
    }
    this.request = null
  }

  schedule(seconds = DEFAULT_INTERVAL_SECONDS) {
    if (!this.request || this.timer !== null) return
    this.timer = this.setTimeoutImpl(() => {
      this.timer = null
      void this.run()
    }, seconds * 1000)
    this.timer?.unref?.()
  }

  async scheduleFromPolicy(token) {
    if (!this.request) return
    try {
      const policy = await this.apiClient.getPolicy(token)
      if (policy?.enabled !== true || policy?.enabledForCurrentUser === false) {
        this.stop()
        return
      }
      this.schedule(intervalSeconds(policy))
    } catch (error) {
      if (error?.code === 'waiting_for_login' || error?.code === 'permission_changed') {
        this.stop()
        return
      }
      this.schedule()
    }
  }

  async run() {
    if (!this.request || this.running) return
    if (this.controller.hasActiveSession()) {
      this.schedule()
      return
    }
    this.running = true
    try {
      const result = await this.controller.start(this.request)
      if (isStopStatus(result?.status)) {
        this.stop()
      } else {
        await this.scheduleFromPolicy(this.request.authToken)
      }
    } catch (error) {
      if (error?.code === 'waiting_for_login' || error?.code === 'permission_changed') {
        this.stop()
      } else {
        this.schedule()
      }
    } finally {
      this.running = false
    }
  }
}

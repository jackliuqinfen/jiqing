import { ref, onMounted, onUnmounted } from 'vue'

/**
 * 网络状态监听 hook
 * 断网时全局顶部提示，联网自动弹窗提示同步云端
 */
export function useNetwork() {
  const isOnline = ref(navigator.onLine)
  const showOfflineAlert = ref(false)
  const showReconnectAlert = ref(false)

  function handleOnline() {
    isOnline.value = true
    showOfflineAlert.value = false
    showReconnectAlert.value = true
    // 联网提示 3 秒后自动消失
    setTimeout(() => {
      showReconnectAlert.value = false
    }, 3000)
  }

  function handleOffline() {
    isOnline.value = false
    showOfflineAlert.value = true
    showReconnectAlert.value = false
  }

  onMounted(() => {
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
  })

  onUnmounted(() => {
    window.removeEventListener('online', handleOnline)
    window.removeEventListener('offline', handleOffline)
  })

  return {
    isOnline,
    showOfflineAlert,
    showReconnectAlert,
  }
}

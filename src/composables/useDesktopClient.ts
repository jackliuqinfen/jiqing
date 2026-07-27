import { computed, onMounted, ref } from 'vue'

import type { DesktopCapabilities } from '@/types/desktop'

export function useDesktopClient() {
  const capabilities = ref<DesktopCapabilities | null>(null)
  const capabilityError = ref('')
  const isDesktop = computed(() => capabilities.value?.desktop === true)

  onMounted(async () => {
    const bridge = window.jiqingDesktop
    if (!bridge) return

    try {
      capabilities.value = await bridge.getCapabilities()
      capabilityError.value = ''
    } catch {
      capabilities.value = null
      capabilityError.value = '桌面能力暂不可用'
    }
  })

  return {
    capabilities,
    capabilityError,
    isDesktop,
  }
}

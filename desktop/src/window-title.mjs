const APPLICATION_TITLE = '集庆工程管理'

export function desktopWindowTitle(environmentLabel = '') {
  return environmentLabel
    ? `${APPLICATION_TITLE} - ${environmentLabel}`
    : APPLICATION_TITLE
}

export function installEnvironmentTitleGuard({
  webContents,
  window,
  environmentLabel = '',
}) {
  if (!environmentLabel) return false
  const title = desktopWindowTitle(environmentLabel)
  webContents.on('page-title-updated', (event) => {
    event.preventDefault()
    window.setTitle(title)
  })
  return true
}

export const DESKTOP_TITLE_BAR_HEIGHT = 60

export function hasLiveWindowWebContents(window) {
  if (
    !window
    || typeof window.isDestroyed !== 'function'
    || window.isDestroyed()
  ) {
    return false
  }

  const { webContents } = window
  return Boolean(
    webContents
    && typeof webContents.isDestroyed === 'function'
    && !webContents.isDestroyed()
  )
}

export function createIntegratedTitleBarOptions() {
  return Object.freeze({
    titleBarStyle: 'hidden',
    titleBarOverlay: Object.freeze({
      color: '#F8FBFF',
      symbolColor: '#53627A',
      height: DESKTOP_TITLE_BAR_HEIGHT,
    }),
  })
}

export const INTEGRATED_TITLE_BAR_CSS = `
  .platform-topbar {
    -webkit-app-region: drag !important;
    padding-right: 158px !important;
  }

  .platform-topbar .topbar-brand,
  .platform-topbar .platform-nav,
  .platform-topbar .topbar-actions,
  .platform-topbar a,
  .platform-topbar button,
  .platform-topbar input,
  .platform-topbar select {
    -webkit-app-region: no-drag !important;
  }

  .login-page::before {
    content: "";
    position: fixed;
    inset: 0 148px auto 0;
    z-index: 1000;
    height: ${DESKTOP_TITLE_BAR_HEIGHT}px;
    background: transparent;
    -webkit-app-region: drag;
  }

  @media (max-width: 1180px) {
    .platform-topbar {
      padding-right: 148px !important;
    }
  }
`

import { ReactNode, createContext, useCallback, useContext, useEffect, useState } from 'react'
import clsx from 'clsx'
import Navigation from './Navigation'
import styles from './PageShell.module.css'

// Lets sidebar content close the mobile drawer (e.g. after opening a document),
// so descending into groups keeps it open. A no-op outside a sidebar drawer.
const CloseSidebarDrawerContext = createContext<() => void>(() => {})
export function useCloseSidebarDrawer() {
  return useContext(CloseSidebarDrawerContext)
}

interface PageShellProps {
  children: ReactNode
  // When true, the body has no padding and its children are full-width sections
  // (wrap each block in <PageSection>) separated by hairlines, matching the home
  // page's connected-section layout. Otherwise the body is a single padded area.
  flush?: boolean
  // When provided, render the wide two-pane variant: this persistent sidebar on
  // the left and `children` as the main column. The frame breaks out of the
  // app-wide width cap on desktop; below the breakpoint the sidebar becomes an
  // off-canvas drawer opened by a toggle button, so narrow screens can still
  // reach it while the body reads like the default shell.
  sidebar?: ReactNode
  // Label for the mobile drawer toggle button (also its accessible name).
  sidebarLabel?: ReactNode
}

// The connected one-card page frame: the embedded nav strip and the page content
// share a single hairline-bordered surface (see the home page). Pages render
// their content as children instead of their own <Navigation> + card; the
// enclosing <main> is owned by RootLayout.
function PageShell({ children, flush = false, sidebar, sidebarLabel }: PageShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const closeDrawer = useCallback(() => setDrawerOpen(false), [])

  // Close the drawer on Escape while open.
  useEffect(() => {
    if (!drawerOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeDrawer()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [drawerOpen, closeDrawer])

  if (sidebar) {
    return (
      <div className={clsx(styles.panel, styles.wide)}>
        <Navigation embedded />
        <div className={styles.split}>
          <div
            className={clsx(styles.backdrop, drawerOpen && styles.backdropOpen)}
            onClick={closeDrawer}
            aria-hidden
          />
          <aside className={clsx(styles.rail, drawerOpen && styles.railOpen)}>
            <CloseSidebarDrawerContext.Provider value={closeDrawer}>
              {sidebar}
            </CloseSidebarDrawerContext.Provider>
          </aside>
          <div className={styles.body}>
            <div className={styles.drawerToggleBar}>
              <button
                type="button"
                className={styles.drawerToggle}
                onClick={() => setDrawerOpen(true)}
                aria-expanded={drawerOpen}
              >
                <span aria-hidden>☰</span>
                {sidebarLabel}
              </button>
            </div>
            {children}
          </div>
        </div>
      </div>
    )
  }
  return (
    <div className={styles.panel}>
      <Navigation embedded />
      <div className={flush ? styles.bodyFlush : styles.body}>{children}</div>
    </div>
  )
}

// A full-width section inside a `flush` PageShell, separated from its siblings by
// an edge-to-edge hairline (the last one has none).
export function PageSection({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={clsx(styles.section, className)}>{children}</div>
}

export default PageShell

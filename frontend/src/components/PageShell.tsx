import { ReactNode, createContext, useCallback, useContext, useEffect, useState } from 'react'
import clsx from 'clsx'
import { ChevronLeft, ChevronRight, Menu } from 'lucide-react'
import Button from './Button'
import Navigation from './Navigation'
import styles from './PageShell.module.css'

// Lets sidebar content close the mobile drawer (e.g. after opening a document),
// so descending into groups keeps it open. A no-op outside a sidebar drawer.
const CloseSidebarDrawerContext = createContext<() => void>(() => {})
export function useCloseSidebarDrawer() {
  return useContext(CloseSidebarDrawerContext)
}

const OpenSidebarDrawerContext = createContext<() => void>(() => {})
export function useOpenSidebarDrawer() {
  return useContext(OpenSidebarDrawerContext)
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
  // Accessible name for the mobile drawer toggle button (and visible label for
  // the desktop bookmark tab).
  sidebarLabel?: ReactNode
  // When true, the sidebar can be toggled on desktop via a bookmark tab on the
  // left border. Open = wide two-pane (1140px), closed = centered 800px card.
  // On mobile the tab is hidden and the nav's drawer toggle is always visible.
  // Requires `onSidebarToggle`. Implies flush body.
  sidebarCloseable?: boolean
  // Whether the sidebar is currently closed (desktop). Defaults to false.
  sidebarClosed?: boolean
  // Called when the bookmark tab is clicked. Required when sidebarCloseable is
  // true; default no-op otherwise.
  onSidebarToggle?: () => void
  hideMobileSidebarToggle?: boolean
}

const noop = () => {}

// The connected one-card page frame: the embedded nav strip and the page content
// share a single hairline-bordered surface (see the home page). Pages render
// their content as children instead of their own <Navigation> + card; the
// enclosing <main> is owned by RootLayout.
function PageShell({ children, flush = false, sidebar, sidebarLabel, sidebarCloseable, sidebarClosed = false, onSidebarToggle = noop, hideMobileSidebarToggle = false }: PageShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const closeDrawer = useCallback(() => setDrawerOpen(false), [])
  const openDrawer = useCallback(() => setDrawerOpen(true), [])

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
    const closeable = sidebarCloseable === true
    const closed = closeable && sidebarClosed
    const panelClass = clsx(
      styles.panel,
      styles.wide,
      closeable && styles.ledger,
      closed && styles.ledgerClosed,
    )
    const railClass = clsx(styles.rail, closeable && styles.ledgerRail, drawerOpen && styles.railOpen)
    const bodyClass = clsx(styles.body, closeable && styles.bodyFlush)
    const drawerToggle = (!hideMobileSidebarToggle || closeable) && sidebarLabel !== undefined && (
      <Button
        variant="ghost"
        size="sm"
        className={styles.drawerToggle}
        onClick={openDrawer}
        aria-expanded={drawerOpen}
        aria-label={typeof sidebarLabel === 'string' ? sidebarLabel : undefined}
      >
        <Menu className={styles.drawerToggleGlyph} aria-hidden />
      </Button>
    )

    return (
      // data-popup-boundary: the minimized-popup rail anchors to this surface's
      // right edge (see MinimizedPopupRegion).
      <div className={panelClass} data-popup-boundary>
        <Navigation embedded leading={drawerToggle || undefined} />
        <div className={styles.split}>
          <div
            className={clsx(styles.backdrop, drawerOpen && styles.backdropOpen)}
            onClick={closeDrawer}
            aria-hidden
          />
          {closeable && (
            <button
              type="button"
              className={styles.ledgerTab}
              onClick={onSidebarToggle}
              aria-label={typeof sidebarLabel === 'string' ? sidebarLabel : undefined}
            >
              {closed
                ? <ChevronLeft className={styles.ledgerTabGlyph} aria-hidden />
                : <ChevronRight className={styles.ledgerTabGlyph} aria-hidden />}
              <span className={styles.ledgerTabLabel}>{sidebarLabel}</span>
            </button>
          )}
          <aside className={railClass}>
            <CloseSidebarDrawerContext.Provider value={closeDrawer}>
              {sidebar}
            </CloseSidebarDrawerContext.Provider>
          </aside>
          <div className={bodyClass}>
            <OpenSidebarDrawerContext.Provider value={openDrawer}>
            {children}
            </OpenSidebarDrawerContext.Provider>
          </div>
        </div>
      </div>
    )
  }
  return (
    <div className={styles.panel} data-popup-boundary>
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

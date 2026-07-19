import { ReactNode, createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import clsx from 'clsx'
import { Menu, PanelLeftOpen } from 'lucide-react'
import { isEditable } from '../utils/keyboard'
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
  // How the desktop rail sizes against the main column: 'fit' clamps the rail
  // to the main column's height (scrolling internally), so the sidebar never
  // extends the page; 'fill' pins the whole page to the viewport on desktop —
  // the document never scrolls, the rail spans the full height, and the main
  // column scrolls internally instead (below the breakpoint it behaves like
  // 'fit'). Pass explicitly whenever `sidebar` is set.
  sidebarSizing?: 'fit' | 'fill'
  // Accessible name for the mobile drawer toggle button and the desktop
  // bookmark tab.
  sidebarLabel?: string
  // Icon identifying the sidebar's content, shown on the desktop bookmark tab
  // while the sidebar is closed (the open state shows a collapse icon
  // instead). Pass when sidebarCloseable is set.
  sidebarGlyph?: ReactNode
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
function PageShell({ children, flush = false, sidebar, sidebarSizing, sidebarLabel, sidebarGlyph, sidebarCloseable, sidebarClosed = false, onSidebarToggle = noop, hideMobileSidebarToggle = false }: PageShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false)
  const closeDrawer = useCallback(() => setDrawerOpen(false), [])
  const openDrawer = useCallback(() => setDrawerOpen(true), [])

  // In 'fill' sizing the body, not the window, is the page scroller, so
  // ScrollRestoration doesn't reach it; reset it to the top on navigation the
  // way ScrollRestoration resets the window. A no-op when the body doesn't
  // scroll.
  const bodyRef = useRef<HTMLDivElement>(null)
  const { pathname } = useLocation()
  useEffect(() => {
    bodyRef.current?.scrollTo(0, 0)
  }, [pathname])

  // Close the drawer on Escape while open.
  useEffect(() => {
    if (!drawerOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeDrawer()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [drawerOpen, closeDrawer])

  // Desktop closeable sidebars: `s` toggles open/closed (same as the bookmark tab).
  useEffect(() => {
    if (sidebarCloseable !== true) return
    const onKey = (e: KeyboardEvent) => {
      if (isEditable(e.target) || e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key !== 's') return
      e.preventDefault()
      onSidebarToggle()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [sidebarCloseable, onSidebarToggle])

  if (sidebar) {
    const closeable = sidebarCloseable === true
    const closed = closeable && sidebarClosed
    const panelClass = clsx(
      styles.panel,
      styles.wide,
      sidebarSizing === 'fill' && styles.panelFill,
      closeable && styles.ledger,
      closed && styles.ledgerClosed,
    )
    const railClass = clsx(
      styles.rail,
      closeable && styles.ledgerRail,
      drawerOpen && styles.railOpen,
    )
    const bodyClass = clsx(styles.body, closeable && styles.bodyFlush)
    const drawerToggle = (!hideMobileSidebarToggle || closeable) && sidebarLabel !== undefined && (
      <Button
        variant="ghost"
        size="sm"
        className={styles.drawerToggle}
        onClick={openDrawer}
        aria-expanded={drawerOpen}
        aria-label={sidebarLabel}
      >
        <Menu className={styles.drawerToggleGlyph} aria-hidden />
      </Button>
    )

    return (
      // data-page-shell-fill: cross-file marker for RootLayout's .app, which
      // pins the frame to the viewport via :has() (CSS modules hash class
      // names, so an attribute is the clean way to match across stylesheets).
      <div className={panelClass} data-page-shell-fill={sidebarSizing === 'fill' ? '' : undefined}>
        <Navigation embedded leading={drawerToggle || undefined} />
        <div className={styles.split}>
          <div
            className={clsx(styles.backdrop, drawerOpen && styles.backdropOpen)}
            onClick={closeDrawer}
            aria-hidden
          />
          {closeable && (
            <div className={styles.ledgerTabTrack}>
              <button
                type="button"
                className={styles.ledgerTab}
                onClick={onSidebarToggle}
                aria-label={sidebarLabel}
              >
                {closed
                  ? <span className={styles.ledgerTabGlyph} aria-hidden>{sidebarGlyph}</span>
                  // Collapsing moves the panel's left edge rightward, so the
                  // right-pointing PanelLeftOpen glyph is the one that reads
                  // "collapse" here despite its lucide name.
                  : <PanelLeftOpen className={styles.ledgerTabGlyph} aria-hidden />}
              </button>
            </div>
          )}
          <aside className={railClass}>
            <div className={styles.railInner}>
              <CloseSidebarDrawerContext.Provider value={closeDrawer}>
                {sidebar}
              </CloseSidebarDrawerContext.Provider>
            </div>
          </aside>
          <div className={bodyClass} ref={bodyRef}>
            <OpenSidebarDrawerContext.Provider value={openDrawer}>
            {children}
            </OpenSidebarDrawerContext.Provider>
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

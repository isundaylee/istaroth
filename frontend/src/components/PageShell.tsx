import { ReactNode } from 'react'
import clsx from 'clsx'
import Navigation from './Navigation'
import styles from './PageShell.module.css'

interface PageShellProps {
  children: ReactNode
  // When true, the body has no padding and its children are full-width sections
  // (wrap each block in <PageSection>) separated by hairlines, matching the home
  // page's connected-section layout. Otherwise the body is a single padded area.
  flush?: boolean
}

// The connected one-card page frame: the embedded nav strip and the page content
// share a single hairline-bordered surface (see the home page). Pages render
// their content as children instead of their own <Navigation> + card; the
// enclosing <main> is owned by RootLayout.
function PageShell({ children, flush = false }: PageShellProps) {
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

import { createContext, useContext, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import Button from '../components/Button'
import styles from './MinimizedPopup.module.css'

interface MinimizedPopupContextValue {
  /** Rail node (provided by the active region) that minimized cards portal into. */
  rail: HTMLElement | null
  setRail: (element: HTMLElement | null) => void
}

const MinimizedPopupContext = createContext<MinimizedPopupContextValue>({
  rail: null,
  setRail: () => {}
})

const RAIL_MAX_WIDTH = 256 // matches the CSS `min(16rem, ...)` cap
const RAIL_GAP = 12 // gap between the content area and the rail
const RAIL_MARGIN = 8 // minimum gap from the viewport edge

/**
 * Holds the rail node set by the active ``MinimizedPopupRegion`` so minimized
 * cards anywhere in the tree (including nested popups) portal into the same rail.
 */
export function MinimizedPopupProvider({ children }: { children: ReactNode }) {
  const [rail, setRail] = useState<HTMLElement | null>(null)
  return (
    <MinimizedPopupContext.Provider value={{ rail, setRail }}>
      {children}
    </MinimizedPopupContext.Provider>
  )
}

/**
 * Wrap the answer/text area the minimized-popup rail should sit beside. The rail
 * is a ``position: sticky`` column inside this region, so it tracks the region's
 * top and sticks to the top of the screen on scroll natively — no scroll
 * handlers. Horizontally it sits just outside the region's right border when
 * there is room, otherwise inset just inside it (e.g. the wide library viewer);
 * that one choice is the only thing measured, and only on resize.
 */
export function MinimizedPopupRegion({ children, className }: { children: ReactNode; className?: string }) {
  const { setRail } = useContext(MinimizedPopupContext)
  const regionRef = useRef<HTMLDivElement>(null)
  const [inset, setInset] = useState(false)

  useLayoutEffect(() => {
    const region = regionRef.current
    if (!region) return
    const update = () => {
      const right = region.getBoundingClientRect().right
      const railWidth = Math.min(RAIL_MAX_WIDTH, window.innerWidth - 2 * RAIL_MARGIN)
      setInset(right + RAIL_GAP + railWidth > window.innerWidth - RAIL_MARGIN)
    }
    update()
    const observer = new ResizeObserver(update)
    observer.observe(region)
    observer.observe(document.documentElement)
    return () => observer.disconnect()
  }, [])

  // Outside: the track's left edge sits a gap past the region's right border.
  // Inset: the track's right edge sits a gap inside it.
  const trackStyle: CSSProperties = inset
    ? { right: `${RAIL_GAP}px` }
    : { left: '100%', marginLeft: `${RAIL_GAP}px` }

  return (
    <div ref={regionRef} className={`${styles.region}${className ? ` ${className}` : ''}`}>
      {children}
      <div className={styles.railTrack} style={trackStyle}>
        <div ref={setRail} className={styles.rail} />
      </div>
    </div>
  )
}

interface MinimizedPopupCardProps {
  eyebrow?: ReactNode
  title: ReactNode
  /** Re-open the full popup. */
  onRestore: () => void
  /** Fully dismiss the popup. */
  onClose: () => void
  expandLabel: string
  closeLabel: string
}

/** Small card shown in the rail while a popup is minimized. */
export function MinimizedPopupCard({ eyebrow, title, onRestore, onClose, expandLabel, closeLabel }: MinimizedPopupCardProps) {
  const { rail } = useContext(MinimizedPopupContext)
  if (!rail) return null
  // `data-floating-popup` keeps the popups' outside-click handlers from treating
  // a click on the card as "outside" (which would minimize other open popups).
  return createPortal(
    <div className={styles.card} data-floating-popup onMouseDown={(e) => e.stopPropagation()}>
      <button type="button" className={styles.cardBody} onClick={onRestore} title={expandLabel}>
        {eyebrow && <span className={styles.cardEyebrow}>{eyebrow}</span>}
        <span className={styles.cardTitle}>{title}</span>
      </button>
      <Button type="button" variant="icon" onClick={onClose} aria-label={closeLabel} className={styles.cardClose}>
        ×
      </Button>
    </div>,
    rail
  )
}

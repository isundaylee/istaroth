import { createContext, useCallback, useContext, useLayoutEffect, useState, type CSSProperties, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

interface MinimizedPopupContextValue {
  /** DOM node of the shared rail that minimized popup cards portal into. */
  rail: HTMLElement | null
  /** Register (or clear, with ``null``) the content element the rail anchors to. */
  registerAnchor: (element: HTMLElement | null) => void
}

const MinimizedPopupContext = createContext<MinimizedPopupContextValue>({
  rail: null,
  registerAnchor: () => {}
})

const RAIL_MAX_WIDTH = 256 // matches the CSS `min(16rem, ...)` cap
const RAIL_GAP = 12 // gap between the content area and the rail
const RAIL_MARGIN = 8 // minimum gap from the viewport edge

/** Anchor the rail just right of the answer area when there is room (otherwise
 * the top-right corner), and vertically to the top of the answer area or the
 * top of the screen, whichever is lower. Falls back to the CSS default when no
 * content element is registered. */
function computeRailStyle(anchor: HTMLElement | null): CSSProperties {
  if (!anchor) return {}
  const rect = anchor.getBoundingClientRect()
  const railWidth = Math.min(RAIL_MAX_WIDTH, window.innerWidth - 2 * RAIL_MARGIN)
  const besideLeft = rect.right + RAIL_GAP
  const left = besideLeft + railWidth <= window.innerWidth - RAIL_MARGIN
    ? besideLeft
    : window.innerWidth - railWidth - RAIL_MARGIN
  const top = Math.max(rect.top, RAIL_MARGIN)
  return { left: `${Math.round(left)}px`, right: 'auto', top: `${Math.round(top)}px` }
}

/**
 * Hosts the fixed rail that collects minimized citation/query popup cards beside
 * the answer area. Every popup keeps its own state and renders a
 * ``MinimizedPopupCard`` into this rail while minimized, so cards from
 * independent (and nested) popups stack together. The rail position follows the
 * content element registered via ``registerAnchor`` (see ``useMinimizedPopupAnchor``).
 */
export function MinimizedPopupProvider({ children }: { children: ReactNode }) {
  const [rail, setRail] = useState<HTMLDivElement | null>(null)
  const [anchor, setAnchor] = useState<HTMLElement | null>(null)
  const [style, setStyle] = useState<CSSProperties>({})

  useLayoutEffect(() => {
    let frame = 0
    const schedule = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => setStyle(computeRailStyle(anchor)))
    }
    schedule()
    window.addEventListener('resize', schedule)
    // Vertical anchor tracks the answer-area top, so follow scroll too.
    window.addEventListener('scroll', schedule, true)
    // The anchor's size/position can shift after layout settles (fonts, async
    // content); observe it (and the root for viewport-driven reflow).
    const observer = new ResizeObserver(schedule)
    observer.observe(document.documentElement)
    if (anchor) observer.observe(anchor)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', schedule)
      window.removeEventListener('scroll', schedule, true)
      observer.disconnect()
    }
  }, [anchor])

  const registerAnchor = useCallback((element: HTMLElement | null) => setAnchor(element), [])

  return (
    <MinimizedPopupContext.Provider value={{ rail, registerAnchor }}>
      {children}
      <div ref={setRail} className="minimized-popup-rail" style={style} />
    </MinimizedPopupContext.Provider>
  )
}

/** Register the content element the minimized-popup rail should anchor beside. */
export function useMinimizedPopupAnchor(): (element: HTMLElement | null) => void {
  return useContext(MinimizedPopupContext).registerAnchor
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
    <div className="minimized-popup-card" data-floating-popup onMouseDown={(e) => e.stopPropagation()}>
      <button type="button" className="minimized-popup-card__body" onClick={onRestore} title={expandLabel}>
        {eyebrow && <span className="minimized-popup-card__eyebrow">{eyebrow}</span>}
        <span className="minimized-popup-card__title">{title}</span>
      </button>
      <button type="button" className="minimized-popup-card__close" onClick={onClose} aria-label={closeLabel}>
        ×
      </button>
    </div>,
    rail
  )
}

import { createContext, useContext, useLayoutEffect, useState, type CSSProperties, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useLocation } from 'react-router-dom'

/** DOM node of the shared rail that minimized popup cards portal into. */
const MinimizedRailContext = createContext<HTMLElement | null>(null)

const RAIL_MAX_WIDTH = 256 // matches the CSS `min(16rem, ...)` cap
const RAIL_GAP = 12 // gap between the content column and the rail
const RAIL_MARGIN = 8 // minimum gap from the viewport edge

/** Anchor the rail just right of the main content column when there is room
 * (otherwise the top-right corner), and vertically to the top of the answer
 * area or the top of the screen, whichever is lower. */
function computeRailStyle(): CSSProperties {
  const main = document.querySelector('.main')
  if (!main) return {}
  const right = main.getBoundingClientRect().right
  const railWidth = Math.min(RAIL_MAX_WIDTH, window.innerWidth - 2 * RAIL_MARGIN)
  const besideLeft = right + RAIL_GAP
  const left = besideLeft + railWidth <= window.innerWidth - RAIL_MARGIN
    ? besideLeft
    : window.innerWidth - railWidth - RAIL_MARGIN
  // `.answer` is the content container on both the conversation and library
  // pages; fall back to the column top when it is absent.
  const answer = document.querySelector('.answer') ?? main
  const top = Math.max(answer.getBoundingClientRect().top, RAIL_MARGIN)
  return { left: `${Math.round(left)}px`, right: 'auto', top: `${Math.round(top)}px` }
}

/**
 * Hosts the fixed rail that collects minimized citation/query popup cards beside
 * the main content column. Every popup keeps its own state and renders a
 * ``MinimizedPopupCard`` into this rail while minimized, so cards from
 * independent (and nested) popups stack together.
 */
export function MinimizedPopupProvider({ children }: { children: ReactNode }) {
  const [rail, setRail] = useState<HTMLDivElement | null>(null)
  const [style, setStyle] = useState<CSSProperties>({})
  const { pathname } = useLocation()

  useLayoutEffect(() => {
    let frame = 0
    const schedule = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => setStyle(computeRailStyle()))
    }
    schedule()
    window.addEventListener('resize', schedule)
    // Vertical anchor tracks the answer-area top, so follow scroll too.
    window.addEventListener('scroll', schedule, true)
    // The column width can shift after layout settles (fonts, async content).
    const observer = new ResizeObserver(schedule)
    observer.observe(document.documentElement)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', schedule)
      window.removeEventListener('scroll', schedule, true)
      observer.disconnect()
    }
  }, [pathname])

  return (
    <MinimizedRailContext.Provider value={rail}>
      {children}
      <div ref={setRail} className="minimized-popup-rail" style={style} />
    </MinimizedRailContext.Provider>
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
  const rail = useContext(MinimizedRailContext)
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

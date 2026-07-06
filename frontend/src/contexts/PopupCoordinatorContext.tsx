import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type MutableRefObject,
  type ReactNode
} from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import Button from '../components/Button'
import { isEditable } from '../utils/keyboard'
import styles from './PopupCoordinator.module.css'

/** Base z-index for floating popups; each stack level sits one above the previous. */
const _POPUP_Z_BASE = 1200

export interface PopupRegistration {
  /** The popup holds a stack entry only while true (e.g. a citation popup's sticky state). */
  enabled: boolean
  /** Minimized popups keep their stack entry (and rail card) but are skipped by keyboard targeting. */
  minimized: boolean
  /** Invoked when Escape targets this popup as the topmost visible one. */
  onClose?: () => void
  /** Single-key shortcuts (e.g. ``f`` → fullscreen) delivered only while topmost and visible. */
  shortcuts?: Record<string, () => void>
}

interface PopupEntry {
  id: number
  /** Latest registration data, read at event time so entries never re-sort on data changes. */
  data: MutableRefObject<PopupRegistration>
}

interface PopupCoordinatorValue {
  /** Rail node (provided by the active region) that minimized cards portal into. */
  rail: HTMLElement | null
  setRail: (element: HTMLElement | null) => void
  /** Placement guides the rail must stick below while they render sticky (see
   * ``useRailPlacementGuide``). */
  guides: readonly HTMLElement[]
  addGuide: (element: HTMLElement) => void
  removeGuide: (element: HTMLElement) => void
  /** Open popups in stacking order (last = topmost). */
  stack: readonly PopupEntry[]
  register: (data: MutableRefObject<PopupRegistration>) => number
  unregister: (id: number) => void
  bringToFront: (id: number) => void
}

const PopupCoordinatorContext = createContext<PopupCoordinatorValue>({
  rail: null,
  setRail: () => {},
  guides: [],
  addGuide: () => {},
  removeGuide: () => {},
  stack: [],
  register: () => -1,
  unregister: () => {},
  bringToFront: () => {}
})

const RAIL_MAX_WIDTH = 256 // matches the CSS `min(16rem, ...)` cap
const RAIL_GAP = 12 // gap between the content area and the rail
const RAIL_MARGIN = 8 // minimum gap from the viewport edge

/**
 * Top-level coordinator for floating popups. Owns the cross-popup policy that
 * individual panels cannot decide locally: a stacking order (z-index and
 * raise-to-front), and a single document-level keydown listener that targets
 * only the topmost visible popup — Escape closes it, registered single-key
 * shortcuts invoke its handlers, and popups minimized to rail cards are
 * skipped, so a parked card is never dismissed by a key aimed at another
 * popup. Also holds the rail node set by the active ``MinimizedPopupRegion``
 * so minimized cards anywhere in the tree (including nested popups) portal
 * into the same rail, and the placement-guide elements
 * (``useRailPlacementGuide``) whose stuck bottoms the rail must clear. Popup
 * state, content, and outside-click handling stay with each owner.
 */
export function PopupCoordinatorProvider({ children }: { children: ReactNode }) {
  const [rail, setRail] = useState<HTMLElement | null>(null)
  const [guides, setGuides] = useState<HTMLElement[]>([])
  const [stack, setStack] = useState<PopupEntry[]>([])
  const nextIdRef = useRef(0)

  const addGuide = useCallback((element: HTMLElement) => {
    setGuides((prev) => [...prev, element])
  }, [])
  const removeGuide = useCallback((element: HTMLElement) => {
    setGuides((prev) => prev.filter((guide) => guide !== element))
  }, [])

  const register = useCallback((data: MutableRefObject<PopupRegistration>) => {
    const id = nextIdRef.current++
    setStack((prev) => [...prev, { id, data }])
    return id
  }, [])
  const unregister = useCallback((id: number) => {
    setStack((prev) => prev.filter((entry) => entry.id !== id))
  }, [])
  const bringToFront = useCallback((id: number) => {
    setStack((prev) => {
      const index = prev.findIndex((entry) => entry.id === id)
      return index === -1 || index === prev.length - 1
        ? prev
        : [...prev.slice(0, index), ...prev.slice(index + 1), prev[index]]
    })
  }, [])

  useEffect(() => {
    if (stack.length === 0) return
    const handleKeyDown = (event: KeyboardEvent) => {
      const top = [...stack].reverse().find((entry) => !entry.data.current.minimized)?.data.current
      if (!top) return
      if (event.key === 'Escape') {
        top.onClose?.()
        return
      }
      if (isEditable(event.target) || event.metaKey || event.ctrlKey || event.altKey) return
      const shortcut = top.shortcuts?.[event.key]
      if (shortcut) {
        event.preventDefault()
        shortcut()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [stack])

  const value = useMemo(
    () => ({ rail, setRail, guides, addGuide, removeGuide, stack, register, unregister, bringToFront }),
    [rail, guides, addGuide, removeGuide, stack, register, unregister, bringToFront]
  )
  return <PopupCoordinatorContext.Provider value={value}>{children}</PopupCoordinatorContext.Provider>
}

/**
 * Hold a coordinator stack entry while ``registration.enabled``. Returns the
 * popup's z-index (its stack position; unregistered popups float above the
 * whole stack, which places transient hover popups on top) and a
 * ``bringToFront`` that raises it above sibling popups.
 */
export function usePopupRegistration(registration: PopupRegistration): {
  zIndex: number
  bringToFront: () => void
} {
  const { stack, register, unregister, bringToFront } = useContext(PopupCoordinatorContext)
  const dataRef = useRef(registration)
  dataRef.current = registration
  const idRef = useRef<number | null>(null)

  const enabled = registration.enabled
  useLayoutEffect(() => {
    if (!enabled) return
    const id = register(dataRef)
    idRef.current = id
    return () => {
      unregister(id)
      idRef.current = null
    }
  }, [enabled, register, unregister])

  const raise = useCallback(() => {
    if (idRef.current !== null) bringToFront(idRef.current)
  }, [bringToFront])

  const index = stack.findIndex((entry) => entry.id === idRef.current)
  return { zIndex: _POPUP_Z_BASE + (index === -1 ? stack.length : index), bringToFront: raise }
}

/**
 * Ref callback registering an element as a vertical placement guide for the
 * minimized-card rail: while CSS renders the element sticky, the rail sticks
 * below its stuck bottom edge instead of colliding with it. Register
 * unconditionally — a guide that is not currently sticky (e.g. the navbar
 * above the mobile breakpoint) contributes nothing, so the media query in the
 * guide's own stylesheet stays the single source of truth for when it sticks.
 */
export function useRailPlacementGuide(): (element: HTMLElement | null) => void {
  const { addGuide, removeGuide } = useContext(PopupCoordinatorContext)
  const currentRef = useRef<HTMLElement | null>(null)
  return useCallback(
    (element: HTMLElement | null) => {
      if (currentRef.current) removeGuide(currentRef.current)
      currentRef.current = element
      if (element) addGuide(element)
    },
    [addGuide, removeGuide]
  )
}

/** Nearest ancestor that clips or scrolls its overflow, or null when only the
 * document scrolls. */
function _scrollParent(el: HTMLElement): HTMLElement | null {
  for (let p = el.parentElement; p; p = p.parentElement) {
    const style = window.getComputedStyle(p)
    if (style.overflowX !== 'visible' || style.overflowY !== 'visible') return p
  }
  return null
}

/** Bottom edge of a guide's stuck position (its sticky top offset plus its
 * height), or 0 while the guide is not rendered sticky. */
function _stuckBottom(guide: HTMLElement): number {
  const style = window.getComputedStyle(guide)
  const top = Number.parseFloat(style.top)
  return style.position === 'sticky' && !Number.isNaN(top)
    ? top + guide.getBoundingClientRect().height
    : 0
}

/**
 * Wrap the answer/text area the minimized-popup rail should sit beside. The rail
 * is a ``position: sticky`` column inside this region, so it tracks the region's
 * top and sticks to the top of the screen on scroll natively — no scroll
 * handlers. The stuck position clears the strictest registered placement guide
 * (sticky chrome such as the mobile navbar; see ``useRailPlacementGuide``).
 * Horizontally it hangs in the page margin just past the right border
 * of the enclosing ``[data-popup-boundary]`` surface (the page card) when there
 * is room — anchored to a visible edge rather than floating mid-gutter, since
 * the region's own right border may end well inside a wider card (the library
 * reading measure). Without room (or a boundary) it falls back to just outside
 * the region, then inset just inside it. The outside spot also only exists when
 * the region scrolls with the document: inside a scroll container (the
 * library's viewport-pinned main column), anything past the container's border
 * would become scrollable overflow — a stray horizontal scrollbar and clipped
 * cards — so the rail stays inset. This choice and the guide clearance are
 * measured only on resize.
 */
export function MinimizedPopupRegion({ children, className }: { children: ReactNode; className?: string }) {
  const { setRail, guides } = useContext(PopupCoordinatorContext)
  const regionRef = useRef<HTMLDivElement>(null)
  const [trackLeft, setTrackLeft] = useState<number | null>(null)
  const [guideBottom, setGuideBottom] = useState(0)

  useLayoutEffect(() => {
    const region = regionRef.current
    if (!region) return
    const boundary = region.closest('[data-popup-boundary]')
    const update = () => {
      const railWidth = Math.min(RAIL_MAX_WIDTH, window.innerWidth - 2 * RAIL_MARGIN)
      const regionRect = region.getBoundingClientRect()
      const edge = boundary ? boundary.getBoundingClientRect().right : regionRect.right
      setTrackLeft(
        _scrollParent(region) !== null ||
          edge + RAIL_GAP + railWidth > window.innerWidth - RAIL_MARGIN
          ? null
          : edge - regionRect.left + RAIL_GAP
      )
      setGuideBottom(Math.max(0, ...guides.map(_stuckBottom)))
    }
    update()
    const observer = new ResizeObserver(update)
    observer.observe(region)
    if (boundary) observer.observe(boundary)
    guides.forEach((guide) => observer.observe(guide))
    observer.observe(document.documentElement)
    return () => observer.disconnect()
  }, [guides])

  // Outside: the track's left edge sits a gap past the boundary's right border.
  // Inset (no room): the track's right edge sits a gap inside the region's.
  const trackStyle: CSSProperties = {
    ...(trackLeft === null ? { right: `${RAIL_GAP}px` } : { left: `${trackLeft}px` }),
    ['--rail-guide-bottom' as string]: `${guideBottom}px`
  }

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
  const { rail } = useContext(PopupCoordinatorContext)
  if (!rail) return null
  // `data-floating-popup` keeps the popups' outside-click handlers from treating
  // a click on the card as "outside" (which would minimize other open popups).
  return createPortal(
    <div className={styles.card} data-floating-popup onMouseDown={(e) => e.stopPropagation()}>
      <button type="button" className={styles.cardBody} onClick={onRestore} title={expandLabel}>
        {eyebrow && <span className={styles.cardEyebrow}>{eyebrow}</span>}
        <span className={styles.cardTitle}>{title}</span>
      </button>
      <Button type="button" variant="icon" size="xs" onClick={onClose} aria-label={closeLabel} className={styles.cardClose}>
        <X aria-hidden />
      </Button>
    </div>,
    rail
  )
}

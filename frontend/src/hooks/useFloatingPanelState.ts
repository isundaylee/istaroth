import { useCallback, useEffect, useState } from 'react'
import { calculateFloatingPlacement, type FloatingPosition } from '../utils/floatingPanel'

export interface FloatingPanelState {
  /** Last anchor position; retained after close so a re-open can reuse it. */
  position: FloatingPosition
  minimized: boolean
  fullscreen: boolean
  /** Anchor at the given rect and clear minimized/fullscreen. */
  openAtRect: (rect: DOMRect) => void
  openFullscreen: () => void
  minimize: () => void
  restore: () => void
  toggleFullscreen: () => void
  /** Clear minimized/fullscreen on close. */
  reset: () => void
}

/**
 * State machine for an anchored floating panel with minimize-to-rail and
 * fullscreen. What the panel shows — and what "open" means — stays with the
 * caller; this only owns position and the minimized/fullscreen flags.
 */
export function useFloatingPanelState(): FloatingPanelState {
  const [position, setPosition] = useState<FloatingPosition>({ top: 0, left: 0, placement: 'below' })
  const [minimized, setMinimized] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)

  const openAtRect = useCallback((rect: DOMRect) => {
    setPosition(calculateFloatingPlacement(rect))
    setMinimized(false)
    setFullscreen(false)
  }, [])
  const openFullscreen = useCallback(() => {
    setMinimized(false)
    setFullscreen(true)
  }, [])
  const minimize = useCallback(() => setMinimized(true), [])
  const restore = useCallback(() => setMinimized(false), [])
  const toggleFullscreen = useCallback(() => setFullscreen((value) => !value), [])
  const reset = useCallback(() => {
    setMinimized(false)
    setFullscreen(false)
  }, [])

  return { position, minimized, fullscreen, openAtRect, openFullscreen, minimize, restore, toggleFullscreen, reset }
}

/**
 * While ``active``, a pointerdown outside the caller's exempt area triggers
 * ``onOutside``. Clicks in any floating popup/card (incl. nested ones that
 * portal out of the caller's subtree) are always exempt via
 * ``[data-floating-popup]``. ``isExemptTarget`` must be memoized by the caller.
 *
 * ``pointerdown`` rather than ``mousedown``: on touch devices the compatibility
 * mouse events are synthesized only for clean taps on targets the browser deems
 * clickable (and not at all when a tap drifts into a scroll), so a mousedown
 * listener silently never fires there; pointerdown fires for every touch.
 */
export function useOutsidePointerDown(
  active: boolean,
  isExemptTarget: (target: HTMLElement) => boolean,
  onOutside: () => void
): void {
  useEffect(() => {
    if (!active) return
    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target as HTMLElement
      if (target.closest?.('[data-floating-popup]')) return
      if (isExemptTarget(target)) return
      onOutside()
    }
    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
  }, [active, isExemptTarget, onOutside])
}

import { useCallback, useEffect, useState } from 'react'
import { calculateFloatingPlacement, type FloatingPosition } from '../utils/floatingPanel'

export function useFloatingPanelState(): {
  position: FloatingPosition
  minimized: boolean
  fullscreen: boolean
  openAtRect(rect: DOMRect): void
  openFullscreen(): void
  minimize(): void
  restore(): void
  toggleFullscreen(): void
  reset(): void
} {
  const [position, setPosition] = useState<FloatingPosition>({ top: 0, left: 0, placement: 'below' })
  const [minimized, setMinimized] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)

  const openAtRect = useCallback((rect: DOMRect) => {
    setPosition(calculateFloatingPlacement(rect))
    setMinimized(false)
    setFullscreen(false)
  }, [])

  const openFullscreen = useCallback(() => {
    setFullscreen(true)
    setMinimized(false)
  }, [])

  const minimize = useCallback(() => setMinimized(true), [])
  const restore = useCallback(() => setMinimized(false), [])

  const toggleFullscreen = useCallback(() => {
    setFullscreen((v) => !v)
  }, [])

  const reset = useCallback(() => {
    setMinimized(false)
    setFullscreen(false)
  }, [])

  return {
    position,
    minimized,
    fullscreen,
    openAtRect,
    openFullscreen,
    minimize,
    restore,
    toggleFullscreen,
    reset
  }
}

export function useOutsideMouseDown(
  active: boolean,
  isExemptTarget: (target: HTMLElement) => boolean,
  onOutside: () => void
): void {
  useEffect(() => {
    if (!active) return

    const handleMouseDown = (e: MouseEvent) => {
      const target = e.target as HTMLElement
      if (target.closest?.('[data-floating-popup]')) return
      if (isExemptTarget(target)) return
      onOutside()
    }

    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [active, isExemptTarget, onOutside])
}

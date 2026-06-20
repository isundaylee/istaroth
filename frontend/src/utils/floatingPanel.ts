export type FloatingPlacement = 'above' | 'below'

export interface FloatingPosition {
  top: number
  left: number
  placement: FloatingPlacement
}

/**
 * Compute a viewport-aware anchor position for a floating panel from the target
 * element's rect. Picks ``above``/``below`` based on available space and clamps
 * the horizontal center so the panel stays on-screen.
 */
export function calculateFloatingPlacement(rect: DOMRect): FloatingPosition {
  const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))
  const placement: FloatingPlacement = rect.top > window.innerHeight / 2 ? 'above' : 'below'
  return {
    placement,
    top: placement === 'above'
      ? clamp(rect.top - 8, 8, window.innerHeight - 8)
      : clamp(rect.bottom + 8, 8, window.innerHeight - 8),
    left: clamp(rect.left + rect.width / 2, 140, window.innerWidth - 140)
  }
}

export type FloatingPlacement = 'above' | 'below'

/** Minimum gap kept between a floating panel and the viewport edges. */
export const FLOATING_PANEL_MARGIN = 16

/**
 * Clamp a shift so the span ``[edge + shift, edge + size + shift]`` stays within
 * ``[margin, extent - margin]`` (spans wider than that hug the leading edge).
 * Shared by the drag containment and the panel's initial viewport-fit shift.
 */
export function clampShiftIntoViewport(edge: number, size: number, desiredShift: number, extent: number): number {
  const min = FLOATING_PANEL_MARGIN - edge
  const max = Math.max(FLOATING_PANEL_MARGIN, extent - size - FLOATING_PANEL_MARGIN) - edge
  return Math.min(Math.max(desiredShift, min), max)
}

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

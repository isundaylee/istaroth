import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'
import type { FloatingPlacement } from '../utils/floatingPanel'

interface DragOffset {
  x: number
  y: number
}

interface PanelSize {
  width: number
  height: number
}

interface PointerHandleProps {
  onPointerDown: (event: React.PointerEvent<HTMLElement>) => void
}

interface UseDraggableResizableResult {
  /** Offset (in px) applied on top of the panel's anchored position. */
  offset: DragOffset
  /** Explicit size once the panel has been resized; null keeps the CSS default. */
  size: PanelSize | null
  /** True while a drag is in progress (for a grabbing cursor). */
  dragging: boolean
  /** True while a resize is in progress. */
  resizing: boolean
  /** Spread onto the grab handle (e.g. the panel header). */
  dragHandleProps: PointerHandleProps
  /** Spread onto the bottom-right resize grip. */
  resizeHandleProps: PointerHandleProps
}

const MARGIN = 16
const MIN_WIDTH = 240
const MIN_HEIGHT = 160

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

/**
 * Make a floating element draggable from a grab handle and resizable from a
 * bottom-right grip, both via pointer events (mouse, touch, and pen). ``ref``
 * points at the element being measured/moved. ``offset`` is a delta from the
 * element's anchored position and ``size`` an explicit width/height once resized;
 * both are clamped to keep the panel within the viewport. Passing a new
 * ``resetKey`` (e.g. the anchor position) restores the defaults, so reopening a
 * popup at a fresh anchor starts undragged and unsized.
 *
 * The panel is centered horizontally (``translate(-50%)``), so width grows
 * symmetrically about that center while the bottom-right grip tracks the cursor.
 * ``placement`` determines the vertical anchor: ``below`` pins the top edge, so
 * resizing height needs no offset change, while ``above`` pins the bottom edge,
 * so ``--drag-y`` is compensated to keep the top edge still as height changes.
 */
export function useDraggableResizable(
  { ref, resetKey, placement, disabled = false }:
    { ref: RefObject<HTMLElement>; resetKey: unknown; placement: FloatingPlacement; disabled?: boolean }
): UseDraggableResizableResult {
  const [offset, setOffset] = useState<DragOffset>({ x: 0, y: 0 })
  const [size, setSize] = useState<PanelSize | null>(null)
  const [dragging, setDragging] = useState(false)
  const [resizing, setResizing] = useState(false)
  const offsetRef = useRef(offset)
  offsetRef.current = offset

  useEffect(() => {
    setOffset({ x: 0, y: 0 })
    setSize(null)
  }, [resetKey])

  const onDragPointerDown = useCallback((event: React.PointerEvent<HTMLElement>) => {
    if (disabled) return
    if (event.pointerType === 'mouse' && event.button !== 0) return
    // Don't hijack pointerdowns on interactive controls living in the handle.
    if ((event.target as HTMLElement).closest('button, a, input, textarea, select')) return
    const panel = ref.current
    if (!panel) return
    event.preventDefault()

    const rect = panel.getBoundingClientRect()
    const start = offsetRef.current
    // Anchored (offset-free) edges, used to clamp the new offset into the viewport.
    const baseLeft = rect.left - start.x
    const baseTop = rect.top - start.y
    const startX = event.clientX
    const startY = event.clientY
    setDragging(true)

    const handleMove = (move: PointerEvent) => {
      const maxLeft = Math.max(MARGIN, window.innerWidth - rect.width - MARGIN)
      const maxTop = Math.max(MARGIN, window.innerHeight - rect.height - MARGIN)
      setOffset({
        x: clamp(start.x + move.clientX - startX, MARGIN - baseLeft, maxLeft - baseLeft),
        y: clamp(start.y + move.clientY - startY, MARGIN - baseTop, maxTop - baseTop)
      })
    }
    const handleUp = () => {
      setDragging(false)
      window.removeEventListener('pointermove', handleMove)
      window.removeEventListener('pointerup', handleUp)
      window.removeEventListener('pointercancel', handleUp)
    }
    window.addEventListener('pointermove', handleMove)
    window.addEventListener('pointerup', handleUp)
    window.addEventListener('pointercancel', handleUp)
  }, [disabled, ref])

  const onResizePointerDown = useCallback((event: React.PointerEvent<HTMLElement>) => {
    if (disabled) return
    if (event.pointerType === 'mouse' && event.button !== 0) return
    const panel = ref.current
    if (!panel) return
    event.preventDefault()

    const rect = panel.getBoundingClientRect()
    const startOffset = offsetRef.current
    // Edges held fixed during the resize: the horizontal center (panel is
    // centered) and the top (so the grip drags the bottom-right corner outward).
    const centerX = rect.left + rect.width / 2
    const topY = rect.top
    const startWidth = rect.width
    const startHeight = rect.height
    const startX = event.clientX
    const startY = event.clientY
    setResizing(true)

    const handleMove = (move: PointerEvent) => {
      const maxWidth = Math.max(MIN_WIDTH, 2 * Math.min(centerX - MARGIN, window.innerWidth - MARGIN - centerX))
      const maxHeight = Math.max(MIN_HEIGHT, window.innerHeight - MARGIN - topY)
      // Size tracks the cursor delta (not its absolute position) so the panel
      // doesn't jump when the grab point isn't exactly the corner. Width grows
      // symmetrically about centerX, so the right edge moves by half the width
      // delta, i.e. by the cursor delta.
      const width = clamp(startWidth + 2 * (move.clientX - startX), MIN_WIDTH, maxWidth)
      const height = clamp(startHeight + (move.clientY - startY), MIN_HEIGHT, maxHeight)
      setSize({ width, height })
      // For ``above``, the bottom is the anchored edge, so shift --drag-y to keep
      // the top still as height changes; ``below`` already pins the top.
      if (placement === 'above') setOffset({ x: startOffset.x, y: startOffset.y + (height - startHeight) })
    }
    const handleUp = () => {
      setResizing(false)
      window.removeEventListener('pointermove', handleMove)
      window.removeEventListener('pointerup', handleUp)
      window.removeEventListener('pointercancel', handleUp)
    }
    window.addEventListener('pointermove', handleMove)
    window.addEventListener('pointerup', handleUp)
    window.addEventListener('pointercancel', handleUp)
  }, [disabled, ref, placement])

  return {
    offset,
    size,
    dragging,
    resizing,
    dragHandleProps: { onPointerDown: onDragPointerDown },
    resizeHandleProps: { onPointerDown: onResizePointerDown }
  }
}

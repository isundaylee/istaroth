import { useCallback, useEffect, useRef, useState } from 'react'

interface DragOffset {
  x: number
  y: number
}

interface UseDraggableResult {
  /** Offset (in px) applied on top of the panel's anchored position. */
  offset: DragOffset
  /** True while a drag is in progress (for a grabbing cursor). */
  dragging: boolean
  /** Spread onto the grab handle (e.g. the panel header). */
  handleProps: { onPointerDown: (event: React.PointerEvent<HTMLElement>) => void }
}

const MARGIN = 16

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

/**
 * Make a floating element draggable from a grab handle via pointer events (mouse,
 * touch, and pen). The returned ``offset`` is a delta from the element's anchored
 * position and is clamped so the element stays within the viewport. Passing a new
 * ``resetKey`` (e.g. the anchor position) restores the default position, so
 * reopening a popup at a fresh anchor starts undragged. The handle's nearest
 * ``.floating-panel`` ancestor is the element being measured/moved.
 */
export function useDraggable({ resetKey, disabled = false }: { resetKey: unknown; disabled?: boolean }): UseDraggableResult {
  const [offset, setOffset] = useState<DragOffset>({ x: 0, y: 0 })
  const [dragging, setDragging] = useState(false)
  const offsetRef = useRef(offset)
  offsetRef.current = offset

  useEffect(() => setOffset({ x: 0, y: 0 }), [resetKey])

  const onPointerDown = useCallback((event: React.PointerEvent<HTMLElement>) => {
    if (disabled) return
    if (event.pointerType === 'mouse' && event.button !== 0) return
    // Don't hijack pointerdowns on interactive controls living in the handle.
    if ((event.target as HTMLElement).closest('button, a, input, textarea, select')) return
    const panel = (event.currentTarget as HTMLElement).closest('.floating-panel') as HTMLElement | null
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
  }, [disabled])

  return { offset, dragging, handleProps: { onPointerDown } }
}

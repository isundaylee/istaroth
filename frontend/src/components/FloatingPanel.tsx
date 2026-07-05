import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useT } from '../contexts/LanguageContext'
import { MinimizedPopupCard } from '../contexts/MinimizedPopupContext'
import { useDraggableResizable } from '../hooks/useDraggableResizable'
import type { FloatingPlacement } from '../utils/floatingPanel'
import { isEditable } from '../utils/keyboard'
import Button from './Button'
import styles from './FloatingPanel.module.css'

interface FloatingPanelProps {
  /** Anchor placement; ignored when ``fullscreen`` is set. */
  placement?: FloatingPlacement
  top?: number
  left?: number
  eyebrow?: ReactNode
  title: ReactNode
  /** Optional node rendered under the title (e.g. an "open full page" link). */
  topLink?: ReactNode
  /** Optional action nodes rendered before the close button. */
  actions?: ReactNode
  /** When provided, a close button is shown and Escape dismisses the panel. */
  onClose?: () => void
  /** When true, the panel is hidden and represented by a card in the side rail. */
  minimized?: boolean
  /** Re-open the full panel from its minimized card. */
  onRestore?: () => void
  fullscreen?: boolean
  /** When provided, a fullscreen toggle button is shown in the actions row and
   * the 'f' shortcut toggles fullscreen while the panel is visible. */
  onToggleFullscreen?: () => void
  /** When false, the panel is rendered ``pointer-events: none`` so it never
   * intercepts hit-testing (used for non-sticky hover popups). */
  interactive?: boolean
  bodyClassName?: string
  children: ReactNode
}

/**
 * Shared floating panel frame used by the citation popup and the proper-noun
 * selection panel. Renders the neutral surface-card look (eyebrow + title +
 * optional link + actions/close) and handles Escape dismissal. Positioning and
 * outside-click detection stay with the caller.
 */
export function FloatingPanel({
  placement = 'below',
  top,
  left,
  eyebrow,
  title,
  topLink,
  actions,
  onClose,
  minimized = false,
  onRestore,
  fullscreen = false,
  onToggleFullscreen,
  interactive = true,
  bodyClassName,
  children
}: FloatingPanelProps) {
  const t = useT()

  // Internal ref to the panel element, handed to useDraggableResizable so it can
  // measure/move/resize the panel without reaching for it via a DOM selector.
  const panelElementRef = useRef<HTMLDivElement | null>(null)

  // The header acts as a drag handle and the bottom-right grip resizes the panel,
  // for anchored (non-fullscreen, interactive) panels. Hover-only popups
  // (interactive=false) and the fullscreen view aren't draggable/resizable; the
  // offset and size reset when the panel re-anchors at a new position.
  const movable = !fullscreen && interactive && top != null
  const { offset, size, dragging, resizing, dragHandleProps, resizeHandleProps } = useDraggableResizable({
    ref: panelElementRef,
    resetKey: `${top},${left}`,
    placement,
    disabled: !movable
  })

  // Horizontal viewport-fit correction. The anchor clamp in
  // calculateFloatingPlacement assumes a narrow panel, so on small screens the
  // centered panel can overhang a viewport edge. Measure the rendered width and
  // shift the panel back inside (the drag hook applies the same containment
  // while dragging).
  const [fitX, setFitX] = useState(0)
  useLayoutEffect(() => {
    setFitX(0)
    if (fullscreen || minimized || top == null || left == null) return
    const width = panelElementRef.current?.getBoundingClientRect().width
    if (!width) return
    const margin = 8
    const minShift = margin - (left - width / 2)
    const maxShift = window.innerWidth - margin - (left + width / 2)
    setFitX(Math.min(Math.max(0, minShift), maxShift))
  }, [top, left, placement, fullscreen, minimized])

  useEffect(() => {
    if (!onClose) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  // 'f' toggles fullscreen while the panel is visible (not minimized to a rail
  // card) and the fullscreen toggle is enabled.
  useEffect(() => {
    if (!onToggleFullscreen || minimized) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (isEditable(e.target) || e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === 'f') {
        e.preventDefault()
        onToggleFullscreen()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onToggleFullscreen, minimized])

  const panelClass = [
    styles.panel,
    fullscreen ? styles.fullscreen : placement === 'above' ? styles.above : null,
    interactive ? null : styles.static,
    resizing ? styles.resizing : null,
    // Kept mounted (not unmounted) while minimized so nested popups rendered in
    // the body survive and can show their own cards.
    minimized ? styles.minimized : null
  ].filter(Boolean).join(' ')

  const style: CSSProperties | undefined = fullscreen
    ? undefined
    : {
        top: top != null ? `${top}px` : undefined,
        left: left != null ? `${left}px` : undefined,
        // Once resized, an explicit width/height replaces the default size and the
        // anchored max-height cap; otherwise the panel sizes to content up to it.
        ...(size
          ? { width: `${size.width}px`, height: `${size.height}px`, maxWidth: 'none', maxHeight: 'none' }
          : {
              maxHeight: top != null
                ? placement === 'above'
                  ? `calc(${top}px - 1rem)`
                  : `calc(100vh - ${top}px - 1rem)`
                : undefined
            }),
        // Folded into the centering transform via CSS custom properties so the
        // fit correction and a drag shift the panel without overwriting its
        // `translate(-50% ...)` base.
        ['--fit-x' as string]: `${fitX}px`,
        ['--drag-x' as string]: `${offset.x}px`,
        ['--drag-y' as string]: `${offset.y}px`
      }

  const headerClass = [
    styles.header,
    movable ? styles.headerDraggable : null,
    dragging ? styles.headerDragging : null
  ].filter(Boolean).join(' ')

  // Portalled to body so the fixed-positioned panel is anchored to the viewport
  // even when rendered inside another panel: an ancestor with `transform`
  // (the centering on `.floating-panel`) would otherwise become its containing
  // block and `overflow: hidden` would clip it. `data-floating-popup` lets
  // outside-click handlers recognise clicks landing in any (nested) popup.
  return createPortal(
    <>
      {minimized && onRestore && onClose && (
        <MinimizedPopupCard
          eyebrow={eyebrow}
          title={title}
          onRestore={onRestore}
          onClose={onClose}
          expandLabel={t('common.expand')}
          closeLabel={t('common.close')}
        />
      )}
    <div
      ref={panelElementRef}
      className={panelClass}
      style={style}
      data-floating-popup
      onMouseDown={(e) => e.stopPropagation()}
    >
      <div
        className={headerClass}
        {...(movable ? dragHandleProps : {})}
      >
        <div className={styles.heading}>
          {eyebrow && <p className={styles.eyebrow}>{eyebrow}</p>}
          <h3 className={styles.title}>{title}</h3>
          {topLink}
        </div>
        {(actions || onToggleFullscreen || onClose) && (
          <div className={styles.actions}>
            {actions}
            {onToggleFullscreen && (
              <Button
                type="button"
                variant="icon"
                onClick={onToggleFullscreen}
                title={fullscreen ? t('citation.exitFullscreen') : t('citation.enterFullscreen')}
              >
                {fullscreen ? '⧉' : '⛶'}
              </Button>
            )}
            {onClose && (
              <Button
                type="button"
                variant="icon"
                onClick={onClose}
                aria-label={t('common.close')}
              >
                ×
              </Button>
            )}
          </div>
        )}
      </div>
      <div className={`${styles.body}${bodyClassName ? ` ${bodyClassName}` : ''}`}>
        {children}
      </div>
      {movable && (
        <div
          className={styles.resizeHandle}
          aria-hidden="true"
          {...resizeHandleProps}
        />
      )}
    </div>
    </>,
    document.body
  )
}

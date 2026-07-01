import { useCallback, useEffect, useRef, type CSSProperties, type ReactNode, type Ref } from 'react'
import { createPortal } from 'react-dom'
import { useT } from '../contexts/LanguageContext'
import { MinimizedPopupCard } from '../contexts/MinimizedPopupContext'
import { useDraggableResizable } from '../hooks/useDraggableResizable'
import type { FloatingPlacement } from '../utils/floatingPanel'
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
  /** When provided, a fullscreen toggle button is shown in the actions row. */
  onToggleFullscreen?: () => void
  /** When false, the panel is rendered ``pointer-events: none`` so it never
   * intercepts hit-testing (used for non-sticky hover popups). */
  interactive?: boolean
  bodyClassName?: string
  children: ReactNode
  panelRef?: Ref<HTMLDivElement>
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
  children,
  panelRef
}: FloatingPanelProps) {
  const t = useT()

  // Internal ref to the panel element, forwarded to the caller's `panelRef` and
  // handed to useDraggableResizable so it can measure/move/resize the panel
  // without reaching for it via a DOM selector.
  const panelElementRef = useRef<HTMLDivElement | null>(null)
  const setPanelRef = useCallback((node: HTMLDivElement | null) => {
    panelElementRef.current = node
    if (typeof panelRef === 'function') panelRef(node)
    else if (panelRef) (panelRef as { current: HTMLDivElement | null }).current = node
  }, [panelRef])

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

  useEffect(() => {
    if (!onClose) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

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
        // Folded into the centering transform via CSS custom properties so a drag
        // shifts the panel without overwriting its `translate(-50% ...)` base.
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
      ref={setPanelRef}
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

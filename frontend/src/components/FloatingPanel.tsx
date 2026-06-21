import { useCallback, useEffect, useRef, type CSSProperties, type ReactNode, type Ref } from 'react'
import { createPortal } from 'react-dom'
import { useT } from '../contexts/LanguageContext'
import { MinimizedPopupCard } from '../contexts/MinimizedPopupContext'
import { useDraggable } from '../hooks/useDraggable'
import type { FloatingPlacement } from '../utils/floatingPanel'

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
  // handed to useDraggable so it can measure/move the panel without reaching for
  // it via a DOM selector.
  const panelElementRef = useRef<HTMLDivElement | null>(null)
  const setPanelRef = useCallback((node: HTMLDivElement | null) => {
    panelElementRef.current = node
    if (typeof panelRef === 'function') panelRef(node)
    else if (panelRef) (panelRef as { current: HTMLDivElement | null }).current = node
  }, [panelRef])

  // The header acts as a drag handle for anchored (non-fullscreen, interactive)
  // panels. Hover-only popups (interactive=false) and the fullscreen view aren't
  // draggable; the offset resets when the panel re-anchors at a new position.
  const draggable = !fullscreen && interactive && top != null
  const { offset, dragging, handleProps } = useDraggable({ ref: panelElementRef, resetKey: `${top},${left}`, disabled: !draggable })

  useEffect(() => {
    if (!onClose) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const className = [
    'floating-panel',
    fullscreen ? 'floating-panel--fullscreen' : `floating-panel--${placement}`,
    interactive ? '' : 'floating-panel--static',
    // Kept mounted (not unmounted) while minimized so nested popups rendered in
    // the body survive and can show their own cards.
    minimized ? 'floating-panel--minimized' : ''
  ].filter(Boolean).join(' ')

  const style: CSSProperties | undefined = fullscreen
    ? undefined
    : {
        top: top != null ? `${top}px` : undefined,
        left: left != null ? `${left}px` : undefined,
        maxHeight: top != null
          ? placement === 'above'
            ? `calc(${top}px - 1rem)`
            : `calc(100vh - ${top}px - 1rem)`
          : undefined,
        // Folded into the centering transform via CSS custom properties so a drag
        // shifts the panel without overwriting its `translate(-50% ...)` base.
        ['--drag-x' as string]: `${offset.x}px`,
        ['--drag-y' as string]: `${offset.y}px`
      }

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
      className={className}
      style={style}
      data-floating-popup
      onMouseDown={(e) => e.stopPropagation()}
    >
      <div
        className={[
          'floating-panel__header',
          draggable ? 'floating-panel__header--draggable' : '',
          dragging ? 'floating-panel__header--dragging' : ''
        ].filter(Boolean).join(' ')}
        {...(draggable ? handleProps : {})}
      >
        <div className="floating-panel__heading">
          {eyebrow && <p className="floating-panel__eyebrow">{eyebrow}</p>}
          <h3 className="floating-panel__title">{title}</h3>
          {topLink}
        </div>
        {(actions || onToggleFullscreen || onClose) && (
          <div className="floating-panel__actions">
            {actions}
            {onToggleFullscreen && (
              <button
                type="button"
                className="floating-panel__action-btn"
                onClick={onToggleFullscreen}
                title={fullscreen ? t('citation.exitFullscreen') : t('citation.enterFullscreen')}
              >
                {fullscreen ? '⧉' : '⛶'}
              </button>
            )}
            {onClose && (
              <button
                type="button"
                className="floating-panel__close"
                onClick={onClose}
                aria-label={t('common.close')}
              >
                ×
              </button>
            )}
          </div>
        )}
      </div>
      <div className={`floating-panel__body${bodyClassName ? ` ${bodyClassName}` : ''}`}>
        {children}
      </div>
    </div>
    </>,
    document.body
  )
}

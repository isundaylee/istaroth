import { useEffect, type CSSProperties, type ReactNode, type Ref } from 'react'
import { useT } from '../contexts/LanguageContext'
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
  fullscreen?: boolean
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
  fullscreen = false,
  bodyClassName,
  children,
  panelRef
}: FloatingPanelProps) {
  const t = useT()

  useEffect(() => {
    if (!onClose) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const className = fullscreen
    ? 'floating-panel floating-panel--fullscreen'
    : `floating-panel floating-panel--${placement}`

  const style: CSSProperties | undefined = fullscreen
    ? undefined
    : {
        top: top != null ? `${top}px` : undefined,
        left: left != null ? `${left}px` : undefined,
        maxHeight: top != null
          ? placement === 'above'
            ? `calc(${top}px - 1rem)`
            : `calc(100vh - ${top}px - 1rem)`
          : undefined
      }

  return (
    <div
      ref={panelRef}
      className={className}
      style={style}
      onMouseDown={(e) => e.stopPropagation()}
    >
      <div className="floating-panel__header">
        <div className="floating-panel__heading">
          {eyebrow && <p className="floating-panel__eyebrow">{eyebrow}</p>}
          <h3 className="floating-panel__title">{title}</h3>
          {topLink}
        </div>
        {(actions || onClose) && (
          <div className="floating-panel__actions">
            {actions}
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
  )
}

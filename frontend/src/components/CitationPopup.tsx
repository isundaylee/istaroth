import { forwardRef, useEffect, useRef } from 'react'
import type { CitationResponse } from '../types/api'
import { useTranslation } from '../contexts/LanguageContext'
import { FloatingPanel } from './FloatingPanel'
import type { FloatingPlacement } from '../utils/floatingPanel'

interface CitationPopupProps {
  /** File title (the "Source" eyebrow is added by the shared frame). */
  title: string
  /** Plain content shown in the hover popup (and as a fallback while the cited chunk loads). */
  content?: string
  /** The cited chunk; its start/end offsets locate the cited span within the full text. */
  citedChunk?: CitationResponse
  /** Full file text; when present the whole document is rendered with the cited span highlighted. */
  fullText?: string
  isSticky?: boolean
  isFullscreen?: boolean
  placement: FloatingPlacement
  top: number
  left: number
  onClose?: () => void
  onLoadFullText?: () => void
  isLoadingFullText?: boolean
  onToggleFullscreen?: () => void
}

const CitationPopup = forwardRef<HTMLDivElement, CitationPopupProps>(
  (
    {
      title,
      content,
      citedChunk,
      fullText,
      isSticky = false,
      isFullscreen = false,
      placement,
      top,
      left,
      onClose,
      onLoadFullText,
      isLoadingFullText = false,
      onToggleFullscreen
    },
    ref
  ) => {
    const { t } = useTranslation()
    const citedRef = useRef<HTMLSpanElement>(null)

    // Keep the cited span in view as the cited chunk loads and again once the full text expands.
    useEffect(() => {
      if (!isSticky || !citedRef.current) return
      const el = citedRef.current
      const timer = setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' }), 100)
      return () => clearTimeout(timer)
    }, [isSticky, citedChunk, fullText])

    // The fullscreen toggle is rendered by FloatingPanel via onToggleFullscreen; actions only adds "Load full text".
    const actions = isSticky && onLoadFullText && citedChunk && fullText == null && (
      <button
        onClick={onLoadFullText}
        disabled={isLoadingFullText}
        className="floating-panel__action-btn"
        title={t.citation.loadAllChunks}
      >
        {isLoadingFullText ? t.citation.loadingButton : t.citation.loadAllChunks}
      </button>
    )

    const citedSpan = (text: string) => (
      <span ref={citedRef} className="citation-cited" title={t.citation.current}>
        {text}
      </span>
    )

    const body = isSticky && citedChunk ? (
      <div style={{ whiteSpace: 'pre-wrap' }}>
        {fullText != null ? (
          <>
            {fullText.slice(0, citedChunk.start_index)}
            {citedSpan(fullText.slice(citedChunk.start_index, citedChunk.end_index))}
            {fullText.slice(citedChunk.end_index)}
          </>
        ) : (
          citedSpan(citedChunk.content)
        )}
      </div>
    ) : (
      <div style={{ whiteSpace: 'pre-wrap' }}>{content}</div>
    )

    return (
      <FloatingPanel
        panelRef={ref}
        placement={placement}
        top={top}
        left={left}
        fullscreen={isFullscreen}
        onToggleFullscreen={isSticky ? onToggleFullscreen : undefined}
        interactive={isSticky}
        eyebrow={t.citation.source}
        title={title}
        actions={actions}
        onClose={isSticky ? onClose : undefined}
        bodyClassName="citation-popup-content"
      >
        {body}
      </FloatingPanel>
    )
  }
)

CitationPopup.displayName = 'CitationPopup'

export default CitationPopup

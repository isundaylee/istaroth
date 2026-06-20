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
    const citedRef = useRef<HTMLDivElement>(null)

    // Keep the cited span in view as the cited chunk loads and again once the full text expands.
    useEffect(() => {
      if (!isSticky || !citedRef.current) return
      const el = citedRef.current
      const timer = setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' }), 100)
      return () => clearTimeout(timer)
    }, [isSticky, citedChunk, fullText])

    // The cited region is rendered as a block marked with a left accent bar and a "cited" badge.
    const citedBlock = (text: string) => (
      <div ref={citedRef} className="citation-cited">
        <div className="citation-cited-label">{t.citation.current}</div>
        {text}
      </div>
    )

    // Dashed gap button (top/bottom); clicking either loads the entire file text.
    const loadGap = (label: string) => onLoadFullText && (
      <button
        onClick={onLoadFullText}
        disabled={isLoadingFullText}
        className="citation-gap"
      >
        {isLoadingFullText ? t.citation.loadingButton : label}
      </button>
    )

    const body = isSticky && citedChunk ? (
      <div style={{ whiteSpace: 'pre-wrap' }}>
        {fullText != null ? (() => {
          // Trim newlines at the cut points so the surrounding context sits flush against the bar.
          const before = fullText.slice(0, citedChunk.start_index).replace(/\n+$/, '')
          const after = fullText.slice(citedChunk.end_index).replace(/^\n+/, '')
          return (
            <>
              {before && <div className="citation-context">{before}</div>}
              {citedBlock(fullText.slice(citedChunk.start_index, citedChunk.end_index).trim())}
              {after && <div className="citation-context">{after}</div>}
            </>
          )
        })() : (
          <>
            {citedChunk.chunk_index > 0 && loadGap(t.citation.loadPrevious)}
            {citedBlock(citedChunk.content)}
            {citedChunk.chunk_index < citedChunk.total_chunks - 1 && loadGap(t.citation.loadNext)}
          </>
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

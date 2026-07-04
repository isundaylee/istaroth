import { useEffect, useRef, type ReactNode } from 'react'
import type { CitationResponse } from '../types/api'
import { useTranslation } from '../contexts/LanguageContext'
import { isEditable } from '../utils/keyboard'
import { FloatingPanel } from './FloatingPanel'
import type { FloatingPlacement } from '../utils/floatingPanel'
import { SelectableAnswer } from './SelectableAnswer'
import Button from './Button'
import citationStyles from './CitationPopup.module.css'

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
  minimized?: boolean
  onRestore?: () => void
  placement: FloatingPlacement
  top: number
  left: number
  onClose?: () => void
  onLoadFullText?: () => void
  isLoadingFullText?: boolean
  onToggleFullscreen?: () => void
  /** "Open in library" link rendered in the header by FloatingPanel. */
  topLink?: ReactNode
}

function CitationPopup(
  {
    title,
    content,
    citedChunk,
    fullText,
    isSticky = false,
    isFullscreen = false,
    minimized = false,
    onRestore,
    placement,
    top,
    left,
    onClose,
    onLoadFullText,
    isLoadingFullText = false,
    onToggleFullscreen,
    topLink
  }: CitationPopupProps
) {
  const { t } = useTranslation()
  const citedRef = useRef<HTMLDivElement>(null)

  // Keep the cited span in view as the cited chunk loads and again once the full text expands.
  useEffect(() => {
    if (!isSticky || !citedRef.current) return
    const el = citedRef.current
    const timer = setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' }), 100)
    return () => clearTimeout(timer)
  }, [isSticky, citedChunk, fullText])

  // 'e' loads the full context, scoped to this popup while it's sticky and
  // visible (not minimized to a rail card). 'f' fullscreen toggle is handled
  // by the shared FloatingPanel frame.
  useEffect(() => {
    if (!isSticky || minimized) return
    const handleKeyDown = (e: KeyboardEvent) => {
      if (isEditable(e.target) || e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === 'e' && onLoadFullText && !isLoadingFullText) {
        e.preventDefault()
        onLoadFullText()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isSticky, minimized, onLoadFullText, isLoadingFullText])

  // The cited region is rendered as a block marked with a left accent bar and a "cited" badge.
  const citedBlock = (text: string) => (
    <div ref={citedRef} className={citationStyles.cited}>
      <div className={citationStyles.citedLabel}>{t.citation.current}</div>
      {text}
    </div>
  )

  // Gap button (top/bottom); clicking either loads the entire file text.
  const loadGap = () => onLoadFullText && (
    <Button
      variant="secondary"
      size="sm"
      onClick={onLoadFullText}
      disabled={isLoadingFullText}
      className={citationStyles.gap}
    >
      {isLoadingFullText ? t.citation.loadingButton : t.citation.loadAllChunks}
    </Button>
  )

  const body = isSticky && citedChunk ? (
    <SelectableAnswer resetKey={citedChunk.file_id + ':' + citedChunk.chunk_index}>
      <div style={{ whiteSpace: 'pre-wrap' }}>
        {fullText != null ? (() => {
          // Trim newlines at the cut points so the surrounding context sits flush against the bar.
          const before = fullText.slice(0, citedChunk.start_index).replace(/\n+$/, '')
          const after = fullText.slice(citedChunk.end_index).replace(/^\n+/, '')
          return (
            <>
              {before && <div className={citationStyles.context}>{before}</div>}
              {citedBlock(fullText.slice(citedChunk.start_index, citedChunk.end_index).trim())}
              {after && <div className={citationStyles.context}>{after}</div>}
            </>
          )
        })() : (
          <>
            {citedChunk.chunk_index > 0 && loadGap()}
            {citedBlock(citedChunk.content)}
            {citedChunk.chunk_index < citedChunk.total_chunks - 1 && loadGap()}
          </>
        )}
      </div>
    </SelectableAnswer>
  ) : (
    <div style={{ whiteSpace: 'pre-wrap' }}>{content}</div>
  )

  return (
    <FloatingPanel
      placement={placement}
      top={top}
      left={left}
      fullscreen={isFullscreen}
      onToggleFullscreen={isSticky ? onToggleFullscreen : undefined}
      interactive={isSticky}
      minimized={isSticky ? minimized : false}
      onRestore={isSticky ? onRestore : undefined}
      eyebrow={t.citation.source}
      title={title}
      topLink={isSticky ? topLink : undefined}
      onClose={isSticky ? onClose : undefined}
      bodyClassName={citationStyles.popupContent}
    >
      {body}
    </FloatingPanel>
  )
}

export default CitationPopup

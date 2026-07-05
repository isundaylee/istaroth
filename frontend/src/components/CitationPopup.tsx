import { useEffect, useRef } from 'react'
import type { CitationResponse } from '../types/api'
import { useTranslation } from '../contexts/LanguageContext'
import { useLibraryProperNouns } from '../hooks/useLibraryProperNouns'
import { buildLibraryFilePath } from '../utils/library'
import { AppLink } from './AppLink'
import { FloatingPanel } from './FloatingPanel'
import type { FloatingPlacement } from '../utils/floatingPanel'
import Button from './Button'
import HighlightedMarkdown from './HighlightedMarkdown'
import SelectableAnswer from './SelectableAnswer'
import citationStyles from './CitationPopup.module.css'
import panelStyles from './FloatingPanel.module.css'

interface StickyCitationBodyProps {
  /** The cited chunk; its start/end offsets locate the cited span within the full text. */
  citedChunk: CitationResponse
  /** Full file text; when present the whole document is rendered with the cited span highlighted. */
  fullText?: string
  onLoadFullText?: () => void
  isLoadingFullText: boolean
}

/**
 * Sticky popup body: the cited document rendered as markdown (like the library
 * file viewer) with proper nouns for the cited file highlighted.
 */
function StickyCitationBody({ citedChunk, fullText, onLoadFullText, isLoadingFullText }: StickyCitationBodyProps) {
  const { t } = useTranslation()
  const citedRef = useRef<HTMLDivElement>(null)
  const properNouns = useLibraryProperNouns(citedChunk.file_info.category, String(citedChunk.file_info.id))

  // Keep the cited span in view as the cited chunk loads and again once the full text expands.
  useEffect(() => {
    if (!citedRef.current) return
    const el = citedRef.current
    const timer = setTimeout(() => el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' }), 100)
    return () => clearTimeout(timer)
  }, [citedChunk, fullText])

  // The cited region is rendered as a block marked with a left accent bar and a "cited" badge.
  const citedBlock = (text: string) => (
    <div ref={citedRef} className={citationStyles.cited}>
      <div className={citationStyles.citedLabel}>{t.citation.current}</div>
      <HighlightedMarkdown content={text} properNouns={properNouns} />
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

  if (fullText == null) {
    return (
      <>
        {citedChunk.chunk_index > 0 && loadGap()}
        {citedBlock(citedChunk.content)}
        {citedChunk.chunk_index < citedChunk.total_chunks - 1 && loadGap()}
      </>
    )
  }

  // Chunk offsets fall on newline boundaries (the splitter cuts at \n\n / \n),
  // so the three slices render as markdown without cutting through block
  // constructs. Trim newlines at the cut points so the surrounding context sits
  // flush against the bar.
  const before = fullText.slice(0, citedChunk.start_index).replace(/\n+$/, '')
  const after = fullText.slice(citedChunk.end_index).replace(/^\n+/, '')
  return (
    <>
      {before && (
        <div className={citationStyles.context}>
          <HighlightedMarkdown content={before} properNouns={properNouns} />
        </div>
      )}
      {citedBlock(fullText.slice(citedChunk.start_index, citedChunk.end_index).trim())}
      {after && (
        <div className={citationStyles.context}>
          <HighlightedMarkdown content={after} properNouns={properNouns} />
        </div>
      )}
    </>
  )
}

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
  /** Identity of the displayed citation; clears any text selection inside the sticky popup when it changes. */
  selectionResetKey?: unknown
}

function CitationPopup({
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
  selectionResetKey
}: CitationPopupProps) {
  const { t } = useTranslation()

  const body = isSticky && citedChunk ? (
    <StickyCitationBody
      citedChunk={citedChunk}
      fullText={fullText}
      onLoadFullText={onLoadFullText}
      isLoadingFullText={isLoadingFullText}
    />
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
      // 'e' loads the full context; the coordinator delivers it only while this
      // popup is the topmost visible one ('f'/Escape route the same way).
      shortcuts={isSticky && onLoadFullText ? { e: () => { if (!isLoadingFullText) onLoadFullText() } } : undefined}
      interactive={isSticky}
      minimized={isSticky ? minimized : false}
      onRestore={isSticky ? onRestore : undefined}
      eyebrow={t.citation.source}
      title={title}
      topLink={isSticky && citedChunk ? (
        <AppLink
          className={panelStyles.topLink}
          to={buildLibraryFilePath(citedChunk.file_info)}
          target="_blank"
          rel="noopener noreferrer"
        >
          {t.citation.openInLibrary}
        </AppLink>
      ) : null}
      onClose={isSticky ? onClose : undefined}
      bodyClassName={citationStyles.popupContent}
    >
      {/* Selecting text in the sticky popup opens the shared search/ask toolbar;
          hover popups stay non-interactive (hit-test transparent). */}
      {isSticky ? <SelectableAnswer resetKey={selectionResetKey}>{body}</SelectableAnswer> : body}
    </FloatingPanel>
  )
}

export default CitationPopup

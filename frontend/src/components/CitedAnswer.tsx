import { useState, useEffect, useMemo, useCallback } from 'react'
import type { Components } from 'react-markdown'
import { useT } from '../contexts/LanguageContext'
import { useCitations } from '../hooks/useCitations'
import { useFloatingPanelState, useOutsidePointerDown } from '../hooks/useFloatingPanelState'
import type { CitationResponse } from '../types/api'
import { preprocessCitationsForDisplay, formatCitationId, parseCitationId } from '../utils/citations'
import CitationList from './CitationList'
import CitationPopup from './CitationPopup'
import HighlightedMarkdown from './HighlightedMarkdown'
import SelectableAnswer from './SelectableAnswer'

interface CitedAnswerProps {
  content: string
  /** Proper nouns to highlight within the rendered answer (citation links are left untouched). */
  properNouns?: string[]
  /** Typography scale for the selectable answer container. */
  answerSize?: 'base' | 'sm'
  children?: (props: { answer: React.ReactNode; citationList: React.ReactNode }) => React.ReactNode
}

interface CitationContentData {
  title: string
  content: string
  fileId: string
  chunkIndexWithPrefix?: string
  /** The cited chunk (when loaded), used to locate the cited span within the full text. */
  citedChunk?: CitationResponse
  /** Full file text, fetched on demand for the sticky popup. */
  fullText?: string
}

function CitedAnswer({ content, properNouns, answerSize, children }: CitedAnswerProps) {
  const [hoveredCitation, setHoveredCitation] = useState<string | null>(null)
  const [stickyCitation, setStickyCitation] = useState<string | null>(null)
  const { position, minimized, fullscreen, openAtRect, openFullscreen, minimize, restore, toggleFullscreen, reset } =
    useFloatingPanelState()
  const t = useT()

  // Preprocess content to convert XML citations to markdown links with document:chunk numbering
  // Also extract unique cited works in the same pass
  const preprocessResult = useMemo(() => preprocessCitationsForDisplay(content), [content])
  const processedContent = preprocessResult.processedText
  const uniqueCitedWorks = preprocessResult.uniqueFileIds

  const { citationCache, loadingCitations, fileTextCache, loadingFiles, fetchCitationsBatch, fetchFileText, getCitedWorkInfo } =
    useCitations(uniqueCitedWorks)

  const handleCitationHover = useCallback((e: React.MouseEvent<HTMLElement>, citationId: string) => {
    // Don't show hover popup if any citation is sticky
    if (stickyCitation) return

    const citationRect = e.currentTarget.getBoundingClientRect()

    setHoveredCitation(citationId)

    // Fetch citation content if not already cached
    fetchCitationsBatch([citationId])

    openAtRect(citationRect)
  }, [stickyCitation, fetchCitationsBatch, openAtRect])

  // Global mouse move handler to check if mouse has left all instances of the hovered citation
  useEffect(() => {
    const handleGlobalMouseMove = (e: MouseEvent) => {
      // Don't clear hover if any citation is sticky or no citation is hovered
      if (stickyCitation || !hoveredCitation) return

      // Find all elements with the same citation ID (there might be multiple instances)
      const hoveredElements = document.querySelectorAll(`[data-citation-id="${hoveredCitation}"]`)
      if (hoveredElements.length === 0) return

      // Check if mouse is still over any of the hovered citation elements
      const elementUnderMouse = document.elementFromPoint(e.clientX, e.clientY)
      const isOverAnyCitation = Array.from(hoveredElements).some(element =>
        element.contains(elementUnderMouse) || element === elementUnderMouse
      )

      if (!isOverAnyCitation) {
        setHoveredCitation(null)
      }
    }

    document.addEventListener('mousemove', handleGlobalMouseMove)
    return () => document.removeEventListener('mousemove', handleGlobalMouseMove)
  }, [stickyCitation, hoveredCitation])

  const handleCitationClick = useCallback((e: React.MouseEvent<HTMLElement>, citationId: string) => {
    e.preventDefault()
    e.stopPropagation()

    const citationRect = e.currentTarget.getBoundingClientRect()

    // Fetch citation content if not already cached
    fetchCitationsBatch([citationId])

    // Toggle sticky state
    if (stickyCitation === citationId && !minimized) {
      setStickyCitation(null)
      reset()
    } else {
      openAtRect(citationRect) // Re-anchor and re-open fully when (re)clicking a citation
      setStickyCitation(citationId)
      setHoveredCitation(null) // Clear hover when making sticky
    }
  }, [stickyCitation, minimized, fetchCitationsBatch, openAtRect, reset])

  const handleCitationListClick = useCallback((e: React.MouseEvent<HTMLElement>, citationId: string) => {
    e.preventDefault()
    e.stopPropagation()

    // Fetch citation content if not already cached
    fetchCitationsBatch([citationId])

    // Always open fullscreen when clicking from citation list
    // Position doesn't matter for fullscreen popups
    setStickyCitation(citationId)
    openFullscreen()
    setHoveredCitation(null) // Clear hover when making sticky
  }, [fetchCitationsBatch, openFullscreen])

  const handleCloseSticky = useCallback(() => {
    setStickyCitation(null)
    reset()
  }, [reset])

  // Minimize the sticky popup (instead of closing) when clicking outside it. The
  // popup keeps its state and collapses to a card in the side rail; full close
  // happens via that card. Clicks landing in any floating popup/card are ignored,
  // as are clicks on citation links (they toggle the popup themselves).
  const isCitationTarget = useCallback(
    (target: HTMLElement) => Boolean(target.closest?.('[data-citation-id]')),
    []
  )
  useOutsidePointerDown(stickyCitation !== null && !minimized, isCitationTarget, minimize)

  const getSourceContent = (citationId: string): CitationContentData => {
    const { fileId, chunkIndex } = parseCitationId(citationId)
    const chunkIndexWithPrefix = `ck${chunkIndex}`
    const cached = citationCache[citationId]
    const loading = loadingCitations.has(citationId)

    if (cached) {
      if ('error' in cached) {
        // This is a cached error
        return {
          title: fileId,
          content: `${t('citation.error')}: ${cached.error}`,
          fileId,
          chunkIndexWithPrefix
        }
      } else {
        // This is a successful response
        return {
          title: cached.file_info.title,
          content: cached.content,
          fileId,
          chunkIndexWithPrefix,
          citedChunk: cached
        }
      }
    } else if (loading) {
      return {
        title: fileId,
        content: t('citation.loading'),
        fileId,
        chunkIndexWithPrefix
      }
    } else {
      return {
        title: fileId,
        content: `${t('citation.notLoaded')} ${chunkIndexWithPrefix}.`,
        fileId,
        chunkIndexWithPrefix
      }
    }
  }

  const getStickyContent = (citationId: string): CitationContentData => (
    // Reuse the source-content resolution (title, cited chunk, loading/error fallback) and
    // attach the full file text once it has been fetched for this file.
    { ...getSourceContent(citationId), fullText: fileTextCache[parseCitationId(citationId).fileId] }
  )

  // Custom components for ReactMarkdown - memoized to prevent recreation on every render
  const components: Components = useMemo(() => ({
    a: ({ href, children }) => {
      // Check if this is a citation link
      if (href?.includes('istaroth.markdown/citation/')) {
        // Extract file_id and chunk_index from URL
        const match = href.match(/citation\/([^\/]+)\/(\d+)/)
        if (match) {
          const citationId = formatCitationId(match[1], parseInt(match[2], 10))
          const isHovered = hoveredCitation === citationId

          return (
            <sup
              data-citation-id={citationId}
              // Hover preview only for real mouse pointers. A tap on iOS Safari
              // first dispatches the compatibility mouseenter, and when that
              // handler visibly changes content (the hover popup appearing)
              // Safari treats the tap as hover-only and cancels the click — so
              // the sticky popup never opened on touch, leaving an
              // un-minimizable hover popup instead.
              onPointerEnter={(e) => { if (e.pointerType === 'mouse') handleCitationHover(e, citationId) }}
              onClick={(e) => handleCitationClick(e, citationId)}
              style={{
                color: 'var(--color-primary-text)',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                textDecoration: 'none',
                padding: '2px 4px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: isHovered || stickyCitation === citationId ? 'var(--color-citation-link-hover-bg)' : 'transparent'
              }}
            >
              [{children}]
            </sup>
          )
        }
      }

      // Regular link - render normally
      return <a href={href}>{children}</a>
    }
  }), [hoveredCitation, stickyCitation, handleCitationHover, handleCitationClick])

  const displayedCitation = stickyCitation || hoveredCitation
  const isSticky = stickyCitation !== null
  const popupData = displayedCitation
    ? (isSticky ? getStickyContent(displayedCitation) : getSourceContent(displayedCitation))
    : null

  // The answer comes pre-wired for selection: selecting text (or clicking a
  // highlighted proper noun) opens the search/ask toolbar on every consumer.
  const answer = (
    <SelectableAnswer resetKey={content} size={answerSize}>
      {displayedCitation && popupData && (
        <CitationPopup
          title={popupData.title}
          content={popupData.content}
          citedChunk={isSticky ? popupData.citedChunk : undefined}
          fullText={isSticky ? popupData.fullText : undefined}
          isSticky={isSticky}
          isFullscreen={fullscreen}
          minimized={minimized}
          onRestore={restore}
          placement={position.placement}
          top={position.top}
          left={position.left}
          onClose={handleCloseSticky}
          onLoadFullText={isSticky ? () => fetchFileText(popupData.fileId) : undefined}
          isLoadingFullText={isSticky ? loadingFiles.has(popupData.fileId) : false}
          onToggleFullscreen={isSticky ? toggleFullscreen : undefined}
          selectionResetKey={displayedCitation}
        />
      )}
      <HighlightedMarkdown content={processedContent} properNouns={properNouns} components={components} />
    </SelectableAnswer>
  )

  const citationList = uniqueCitedWorks.length > 0 && (
    <CitationList
      fileIds={uniqueCitedWorks}
      loadingCitations={loadingCitations}
      getFileInfo={getCitedWorkInfo}
      onOpenCitation={handleCitationListClick}
    />
  )

  if (children) {
    return <div style={{ position: 'relative' }}>{children({ answer, citationList: citationList ?? null })}</div>
  }

  return (
    <div style={{ position: 'relative' }} data-citation-container>
      {answer}
      {citationList && (
        <div style={{
          marginTop: '1rem',
          paddingTop: '0.75rem',
          borderTop: '1px solid var(--color-border-divider)'
        }}>
          {citationList}
        </div>
      )}
    </div>
  )
}

export default CitedAnswer

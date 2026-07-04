import { useState, useEffect, useMemo, useCallback } from 'react'
import type { Components } from 'react-markdown'
import { useT } from '../contexts/LanguageContext'
import type { CitationResponse } from '../types/api'
import { buildLibraryFilePath } from '../utils/library'
import { HighlightedMarkdown } from './HighlightedMarkdown'
import CitationPopup from './CitationPopup'
import { CitationList } from './CitationList'
import { preprocessCitationsForDisplay, formatCitationId, parseCitationId } from '../utils/citations'
import { useFloatingPanelState, useOutsideMouseDown } from '../hooks/useFloatingPanelState'
import { useCitations } from '../hooks/useCitations'

interface CitationRendererProps {
  content: string
  /** Proper nouns to highlight within the rendered answer (citation links are left untouched). */
  properNouns?: string[]
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

function CitationRenderer({ content, properNouns, children }: CitationRendererProps) {
  const [hoveredCitation, setHoveredCitation] = useState<string | null>(null)
  const [stickyCitation, setStickyCitation] = useState<string | null>(null)
  const floatingState = useFloatingPanelState()
  const { minimized, fullscreen, position } = floatingState
  const t = useT()

  // Preprocess content to convert XML citations to markdown links with document:chunk numbering
  // Also extract unique cited works in the same pass
  const preprocessResult = useMemo(() => preprocessCitationsForDisplay(content), [content])
  const processedContent = preprocessResult.processedText
  const uniqueCitedWorks = preprocessResult.uniqueFileIds

  const {
    citationCache,
    loadingCitations,
    fileTextCache,
    loadingFiles,
    fetchCitationsBatch,
    fetchFileText,
    getCitedWorkInfo
  } = useCitations(uniqueCitedWorks)

  // Get title for a cited work (from cache if available, otherwise use fileId)

  const handleCitationHover = useCallback((e: React.MouseEvent<HTMLElement>, citationId: string) => {
    // Don't show hover popup if any citation is sticky
    if (stickyCitation) return

    setHoveredCitation(citationId)
    fetchCitationsBatch([citationId])
    floatingState.openAtRect(e.currentTarget.getBoundingClientRect())
  }, [stickyCitation, fetchCitationsBatch, floatingState])

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

    fetchCitationsBatch([citationId])
    floatingState.openAtRect(e.currentTarget.getBoundingClientRect())

    // Toggle sticky state
    if (stickyCitation === citationId && !minimized) {
      setStickyCitation(null)
    } else {
      setStickyCitation(citationId)
      floatingState.restore() // Re-open fully when (re)clicking a citation
      setHoveredCitation(null) // Clear hover when making sticky
    }
  }, [stickyCitation, minimized, fetchCitationsBatch, floatingState])

  const handleCitationListClick = useCallback((e: React.MouseEvent<HTMLElement>, citationId: string) => {
    e.preventDefault()
    e.stopPropagation()

    fetchCitationsBatch([citationId])
    setStickyCitation(citationId)
    floatingState.openFullscreen()
    setHoveredCitation(null)
  }, [fetchCitationsBatch, floatingState])

  const handleCloseSticky = useCallback(() => {
    setStickyCitation(null)
    floatingState.reset()
  }, [floatingState])

  const isStickyActive = stickyCitation !== null && !minimized
  const isExemptTarget = useCallback((target: HTMLElement) =>
    !!(target.closest?.('[data-citation-id]')), [])
  useOutsideMouseDown(isStickyActive, isExemptTarget, floatingState.minimize)

  const getSourceContent = (citationId: string): CitationContentData => {
    const { fileId, chunkIndex } = parseCitationId(citationId)
    const chunkIndexWithPrefix = `ck${chunkIndex}`
    const cached = citationCache[citationId]
    const loading = loadingCitations.has(citationId)

    if (cached) {
      if ('error' in cached) {
        return {
          title: fileId,
          content: `${t('citation.error')}: ${cached.error}`,
          fileId,
          chunkIndexWithPrefix
        }
      } else {
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
              onMouseEnter={(e) => handleCitationHover(e, citationId)}
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

  // Open-in-library link for the sticky popup
  const topLink = isSticky && popupData
    ? ((): React.ReactNode => {
        const citedWork = getCitedWorkInfo(popupData.fileId)
        if (!citedWork) return null
        return (
          <a
            href={buildLibraryFilePath(citedWork.file_info)}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e: React.MouseEvent) => {
              e.stopPropagation()
              window.open(buildLibraryFilePath(citedWork.file_info), '_blank', 'noopener,noreferrer')
            }}
            title={t('citation.openInLibrary')}
          >
            {t('citation.openInLibrary')}
          </a>
        )
      })()
    : undefined

  const answer = (
    <>
      {displayedCitation && popupData && (
        <CitationPopup
          title={popupData.title}
          content={popupData.content}
          citedChunk={isSticky ? popupData.citedChunk : undefined}
          fullText={isSticky ? popupData.fullText : undefined}
          isSticky={isSticky}
          isFullscreen={fullscreen}
          minimized={minimized}
          onRestore={floatingState.restore}
          placement={position.placement}
          top={position.top}
          left={position.left}
          onClose={handleCloseSticky}
          onLoadFullText={isSticky ? () => fetchFileText(popupData.fileId) : undefined}
          isLoadingFullText={isSticky ? loadingFiles.has(popupData.fileId) : false}
          onToggleFullscreen={isSticky ? floatingState.toggleFullscreen : undefined}
          topLink={topLink}
        />
      )}
      <HighlightedMarkdown content={processedContent} properNouns={properNouns} components={components} />
    </>
  )

  const citationList = (
    <CitationList
      uniqueCitedWorks={uniqueCitedWorks}
      loadingCitations={loadingCitations}
      getCitedWorkInfo={getCitedWorkInfo}
      onCitationListClick={handleCitationListClick}
    />
  )

  if (children) {
    return <div style={{ position: 'relative' }}>{children({ answer, citationList })}</div>
  }

  return (
    <div style={{ position: 'relative' }} data-citation-container>
      {answer}
      {uniqueCitedWorks.length > 0 && citationList}
    </div>
  )
}

export default CitationRenderer

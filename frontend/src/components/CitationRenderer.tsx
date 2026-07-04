import { useState, useRef, useEffect, useMemo, useCallback } from 'react'
import type { Components } from 'react-markdown'
import { useTranslation, useT } from '../contexts/LanguageContext'
import type { CitationResponse, LibraryFileInfo, LibraryFileResponse } from '../types/api'
import { buildLibraryFilePath } from '../utils/library'
import CitationPopup from './CitationPopup'
import HighlightedMarkdown from './HighlightedMarkdown'
import { preprocessCitationsForDisplay, formatCitationId, parseCitationId } from '../utils/citations'
import { calculateFloatingPlacement, type FloatingPosition } from '../utils/floatingPanel'

interface CitationRendererProps {
  content: string
  /** Proper nouns to highlight within the rendered answer (citation links are left untouched). */
  properNouns?: string[]
  children?: (props: { answer: React.ReactNode; citationList: React.ReactNode }) => React.ReactNode
}

type CachedCitation = CitationResponse | { error: string }

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
  const [isMinimized, setIsMinimized] = useState<boolean>(false)
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false)
  const [popupPosition, setPopupPosition] = useState<FloatingPosition>({ top: 0, left: 0, placement: 'below' })
  const [citationCache, setCitationCache] = useState<Record<string, CachedCitation>>({})
  const [loadingCitations, setLoadingCitations] = useState<Set<string>>(new Set())
  // Full file text keyed by fileId, fetched on demand to render the whole document around the cited span.
  const [fileTextCache, setFileTextCache] = useState<Record<string, string>>({})
  const [loadingFiles, setLoadingFiles] = useState<Set<string>>(new Set())
  const { language } = useTranslation()
  const t = useT()
  const popupRef = useRef<HTMLDivElement>(null)

  // Preprocess content to convert XML citations to markdown links with document:chunk numbering
  // Also extract unique cited works in the same pass
  const preprocessResult = useMemo(() => preprocessCitationsForDisplay(content), [content])
  const processedContent = preprocessResult.processedText
  const uniqueCitedWorks = preprocessResult.uniqueFileIds

  // Calculate viewport-aware anchor position for the popup from the citation rect.
  const calculatePopupPosition = useCallback((citationRect: DOMRect): FloatingPosition =>
    calculateFloatingPlacement(citationRect), [])

  // Batch function to fetch multiple citations in a single request
  const fetchCitationsBatch = useCallback(async (citationIds: string[]) => {
    // Filter out already cached or loading citations
    const citationsToFetch = citationIds.filter(
      id => !citationCache[id] && !loadingCitations.has(id)
    )

    if (citationsToFetch.length === 0) {
      return
    }

    // Parse citation IDs into (file_id, chunk_index) pairs
    const citations = citationsToFetch.map(citationId => {
      const { fileId, chunkIndex } = parseCitationId(citationId)
      return [fileId, chunkIndex] as [string, number]
    })

    // Mark all as loading
    setLoadingCitations(prev => {
      const newSet = new Set(prev)
      citationsToFetch.forEach(id => newSet.add(id))
      return newSet
    })

    try {
      const response = await fetch('/api/citations/batch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          language: language.toUpperCase(),
          citations,
        }),
      })

      if (response.ok) {
        const data: { successes: CitationResponse[], errors: Array<{file_id: string, chunk_index: number, error: string}> } = await response.json()

        // Update cache with successes
        setCitationCache(prev => {
          const newCache = { ...prev }
          data.successes.forEach(citation => {
            const citationId = formatCitationId(citation.file_id, citation.chunk_index)
            newCache[citationId] = citation
          })
          return newCache
        })

        // Update cache with errors
        setCitationCache(prev => {
          const newCache = { ...prev }
          data.errors.forEach(error => {
            const citationId = formatCitationId(error.file_id, error.chunk_index)
            newCache[citationId] = { error: error.error }
          })
          return newCache
        })
      } else {
        // HTTP error - mark all as failed
        const errorMessage = `${t('citation.fetchFailed')} (${response.status}): ${response.statusText}`
        console.error(errorMessage)
        setCitationCache(prev => {
          const newCache = { ...prev }
          citationsToFetch.forEach(citationId => {
            newCache[citationId] = { error: errorMessage }
          })
          return newCache
        })
      }
    } catch (error) {
      // Network error - mark all as failed
      const errorMessage = `${t('citation.networkError')}: ${error instanceof Error ? error.message : 'Unknown error'}`
      console.error(errorMessage)
      setCitationCache(prev => {
        const newCache = { ...prev }
        citationsToFetch.forEach(citationId => {
          newCache[citationId] = { error: errorMessage }
        })
        return newCache
      })
    } finally {
      // Clear loading state for all
      setLoadingCitations(prev => {
        const newSet = new Set(prev)
        citationsToFetch.forEach(id => newSet.delete(id))
        return newSet
      })
    }
  }, [citationCache, loadingCitations, language, t])

  // Fetch the entire file text for a cited work so the sticky popup can render the
  // full document (no chunk overlap) with the cited span highlighted.
  const fetchFileText = useCallback(async (fileId: string) => {
    if (fileTextCache[fileId] || loadingFiles.has(fileId)) return

    // file_info (category/id) comes from any already-loaded chunk for this file.
    const cached = Object.values(citationCache).find(
      (value): value is CitationResponse => !('error' in value) && value.file_id === fileId
    )
    if (!cached) return
    const { category, id } = cached.file_info

    setLoadingFiles(prev => new Set(prev).add(fileId))
    try {
      const response = await fetch(
        `/api/library/file/${encodeURIComponent(category)}/${encodeURIComponent(id)}?language=${language.toUpperCase()}`
      )
      if (!response.ok) {
        console.error(`${t('citation.fetchFailed')} (${response.status}): ${response.statusText}`)
        return
      }
      const data: LibraryFileResponse = await response.json()
      setFileTextCache(prev => ({ ...prev, [fileId]: data.content }))
    } catch (error) {
      console.error(`${t('citation.networkError')}: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setLoadingFiles(prev => {
        const newSet = new Set(prev)
        newSet.delete(fileId)
        return newSet
      })
    }
  }, [fileTextCache, loadingFiles, citationCache, language, t])

  // Prefetch citations for all unique file IDs to get titles immediately
  useEffect(() => {
    const citationIds = uniqueCitedWorks.map(fileId => formatCitationId(fileId, 0))
    fetchCitationsBatch(citationIds)
  }, [uniqueCitedWorks, fetchCitationsBatch])

  const handleCitationHover = useCallback((e: React.MouseEvent<HTMLElement>, citationId: string) => {
    // Don't show hover popup if any citation is sticky
    if (stickyCitation) return

    const citationRect = e.currentTarget.getBoundingClientRect()

    setHoveredCitation(citationId)

    // Fetch citation content if not already cached
    fetchCitationsBatch([citationId])

    // Calculate optimal position to avoid going off-screen
    const position = calculatePopupPosition(citationRect)
    setPopupPosition(position)
  }, [stickyCitation, fetchCitationsBatch, calculatePopupPosition])

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

    // Calculate optimal position to avoid going off-screen
    const position = calculatePopupPosition(citationRect)
    setPopupPosition(position)

    // Toggle sticky state
    if (stickyCitation === citationId && !isMinimized) {
      setStickyCitation(null)
    } else {
      setStickyCitation(citationId)
      setIsMinimized(false) // Re-open fully when (re)clicking a citation
      setHoveredCitation(null) // Clear hover when making sticky
    }
  }, [stickyCitation, isMinimized, fetchCitationsBatch, calculatePopupPosition])

  const handleCitationListClick = useCallback((e: React.MouseEvent<HTMLElement>, citationId: string) => {
    e.preventDefault()
    e.stopPropagation()

    // Fetch citation content if not already cached
    fetchCitationsBatch([citationId])

    // Always open fullscreen when clicking from citation list
    // Position doesn't matter for fullscreen popups
    setStickyCitation(citationId)
    setIsMinimized(false)
    setIsFullscreen(true)
    setHoveredCitation(null) // Clear hover when making sticky
  }, [fetchCitationsBatch])

  const handleCloseSticky = useCallback(() => {
    setStickyCitation(null)
    setIsMinimized(false)
    setIsFullscreen(false)
  }, [])

  // Minimize the sticky popup (instead of closing) when clicking outside it. The
  // popup keeps its state and collapses to a card in the side rail; full close
  // happens via that card. Clicks landing in any floating popup/card are ignored.
  useEffect(() => {
    if (!stickyCitation || isMinimized) return

    const handleMouseDown = (e: MouseEvent) => {
      if (popupRef.current?.contains(e.target as Node)) return
      if ((e.target as HTMLElement).closest?.('[data-citation-id]')) return
      if ((e.target as HTMLElement).closest?.('[data-floating-popup]')) return
      setIsMinimized(true)
    }

    document.addEventListener('mousedown', handleMouseDown)
    return () => document.removeEventListener('mousedown', handleMouseDown)
  }, [stickyCitation, isMinimized])

  const handleToggleFullscreen = useCallback(() => {
    setIsFullscreen(!isFullscreen)
  }, [isFullscreen])

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


  // Get file info for a cited work (from cache if available)
  const getCitedWorkInfo = useCallback((fileId: string): LibraryFileInfo | null => {
    // Try to find any cached chunk for this file to get the file info
    const cachedChunk = Object.entries(citationCache)
      .find(([key]) => key.startsWith(`${fileId}:`))

    if (cachedChunk && !('error' in cachedChunk[1])) {
      const citation = cachedChunk[1] as CitationResponse
      return citation.file_info
    }

    return null
  }, [citationCache])

  // Get title for a cited work (from cache if available, otherwise use fileId)
  const getCitedWorkTitle = useCallback((fileId: string): string => {
    const fileInfo = getCitedWorkInfo(fileId)
    if (fileInfo) {
      return fileInfo.title
    }
    return fileId
  }, [getCitedWorkInfo])

  const displayedCitation = stickyCitation || hoveredCitation
  const isSticky = stickyCitation !== null
  const popupData = displayedCitation
    ? (isSticky ? getStickyContent(displayedCitation) : getSourceContent(displayedCitation))
    : null

  const answer = (
    <>
      {displayedCitation && popupData && (
        <CitationPopup
          ref={popupRef}
          title={popupData.title}
          content={popupData.content}
          citedChunk={isSticky ? popupData.citedChunk : undefined}
          fullText={isSticky ? popupData.fullText : undefined}
          isSticky={isSticky}
          isFullscreen={isFullscreen}
          minimized={isMinimized}
          onRestore={() => setIsMinimized(false)}
          placement={popupPosition.placement}
          top={popupPosition.top}
          left={popupPosition.left}
          onClose={handleCloseSticky}
          onLoadFullText={isSticky ? () => fetchFileText(popupData.fileId) : undefined}
          isLoadingFullText={isSticky ? loadingFiles.has(popupData.fileId) : false}
          onToggleFullscreen={isSticky ? handleToggleFullscreen : undefined}
        />
      )}
      <HighlightedMarkdown content={processedContent} properNouns={properNouns} components={components} />
    </>
  )

  const citationList = uniqueCitedWorks.length > 0 && (
    <>
      <h3 style={{ marginBottom: '0.75rem' }}>{t('citation.list.title')}</h3>
      <ul style={{
        listStyle: 'none',
        padding: 0,
        margin: 0
      }}>
        {uniqueCitedWorks.map((fileId, index) => {
          const title = getCitedWorkTitle(fileId)
          const isLoading = loadingCitations.has(formatCitationId(fileId, 0))
          const fileInfo = getCitedWorkInfo(fileId)

          const handleLibraryLinkClick = (e: React.MouseEvent<HTMLElement>) => {
            e.preventDefault()
            e.stopPropagation()
            if (fileInfo) {
              const url = buildLibraryFilePath(fileInfo)
              window.open(url, '_blank', 'noopener,noreferrer')
            }
          }

          return (
            <li
              key={fileId}
              style={{
                marginBottom: '0.25rem',
                borderRadius: 'var(--radius-sm)',
                transition: 'background-color 0.15s ease',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                minWidth: 0
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--color-surface-secondary)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'transparent'
              }}
            >
              <span
                  style={{
                    color: 'var(--color-primary-text)',
                    textDecoration: 'none',
                    fontSize: 'var(--font-base)',
                  fontWeight: 400,
                  cursor: 'pointer',
                  flex: 1,
                  minWidth: 0,
                  wordBreak: 'break-all',
                  overflowWrap: 'anywhere'
                }}
                onClick={(e) => handleCitationListClick(e, formatCitationId(fileId, 0))}
              >
                {isLoading ? t('citation.loading') : `${index + 1}. ${title}`}
              </span>
              {fileInfo && (
                <a
                  href={buildLibraryFilePath(fileInfo)}
                  onClick={handleLibraryLinkClick}
                      style={{
                        color: 'var(--color-citation-lib-link)',
                        textDecoration: 'none',
                        display: 'inline-flex',
                        alignItems: 'center',
                    cursor: 'pointer',
                    padding: '4px 6px',
                    borderRadius: 'var(--radius-sm)',
                    transition: 'background-color 0.15s ease, color 0.15s ease',
                    flexShrink: 0
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--color-citation-lib-hover)'
                    e.currentTarget.style.color = 'var(--color-primary-text)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent'
                    e.currentTarget.style.color = 'var(--color-citation-lib-link)'
                  }}
                  title={t('citation.openInLibrary')}
                  aria-label={t('citation.openInLibrary')}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                    <polyline points="15 3 21 3 21 9" />
                    <line x1="10" y1="14" x2="21" y2="3" />
                  </svg>
                </a>
              )}
            </li>
          )
        })}
      </ul>
    </>
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

export default CitationRenderer

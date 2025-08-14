import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import { useTranslation, useT } from '../contexts/LanguageContext'
import type { CitationResponse } from '../types/api'
import CitationPopup from './CitationPopup'

interface CitationRendererProps {
  content: string
}

type CachedCitation = CitationResponse | { error: string }

interface CitationContentData {
  title: string
  chunks: CitationResponse[]
  content: string
  fileId: string
  chunkIndexWithPrefix?: string
  currentChunkIndexWithPrefix?: string
}

function CitationRenderer({ content }: CitationRendererProps) {
  const [hoveredCitation, setHoveredCitation] = useState<string | null>(null)
  const [stickyCitation, setStickyCitation] = useState<string | null>(null)
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false)
  const [popupPosition, setPopupPosition] = useState({ top: 0, left: 0, width: 500, height: 300 })
  const [citationCache, setCitationCache] = useState<Record<string, CachedCitation>>({})
  const [loadingCitations, setLoadingCitations] = useState<Set<string>>(new Set())
  const { language } = useTranslation()
  const t = useT()
  const popupRef = useRef<HTMLDivElement>(null)

  // Preprocess content to convert [[file_id:chunk_index]] to markdown links with document:chunk numbering
  const preprocessContent = (text: string): string => {
    const citationPattern = /\[\[([^:]+):ck(\d+)\]\]/g
    const fileIdToDocIndex = new Map<string, number>()
    let match
    let documentCounter = 0

    // First pass: assign document indices to unique file IDs in order of appearance
    citationPattern.lastIndex = 0  // Reset regex state
    while ((match = citationPattern.exec(text)) !== null) {
      const fileId = match[1]
      if (!fileIdToDocIndex.has(fileId)) {
        documentCounter++
        fileIdToDocIndex.set(fileId, documentCounter)
      }
    }

    // Second pass: replace citations with document_index:chunk_index format
    return text.replace(citationPattern, (_, fileId, chunkIndex) => {
      const docIndex = fileIdToDocIndex.get(fileId)!
      return `[${docIndex}:${chunkIndex}](http://istaroth.markdown/citation/${fileId}/${chunkIndex})`
    })
  }

  const handleCitationHover = (e: React.MouseEvent<HTMLElement>, citationId: string) => {
    // Don't show hover popup if any citation is sticky
    if (stickyCitation) return

    const citationRect = e.currentTarget.getBoundingClientRect()

    setHoveredCitation(citationId)

    // Fetch citation content if not already cached
    fetchCitation(citationId)

    // Calculate optimal position to avoid going off-screen
    const position = calculatePopupPosition(citationRect)
    setPopupPosition(position)
  }

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

  const handleCitationClick = (e: React.MouseEvent<HTMLElement>, citationId: string) => {
    e.preventDefault()
    e.stopPropagation()

    const citationRect = e.currentTarget.getBoundingClientRect()

    // Fetch citation content if not already cached
    fetchCitation(citationId)

    // Calculate optimal position to avoid going off-screen
    const position = calculatePopupPosition(citationRect)
    setPopupPosition(position)

    // Toggle sticky state
    if (stickyCitation === citationId) {
      setStickyCitation(null)
    } else {
      setStickyCitation(citationId)
      setHoveredCitation(null) // Clear hover when making sticky
    }
  }

  const handleCloseSticky = () => {
    setStickyCitation(null)
    setIsFullscreen(false)
  }

  const handleToggleFullscreen = () => {
    setIsFullscreen(!isFullscreen)
  }

  // Calculate optimal popup position and size to avoid going off-screen
  const calculatePopupPosition = (citationRect: DOMRect) => {
    // Default popup dimensions
    const defaultWidth = 500
    const defaultHeight = 300
    const minWidth = 300
    const minHeight = 200 // Increased to ensure enough space for content
    const margin = 10

    // Available viewport space
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight

    // Initial position: below and centered on citation
    const preferredTop = citationRect.bottom + 5
    const preferredCenterX = citationRect.left + (citationRect.width / 2)

    // Calculate maximum available width
    const maxAvailableWidth = viewportWidth - (2 * margin)
    const popupWidth = Math.max(minWidth, Math.min(defaultWidth, maxAvailableWidth))

    // Calculate horizontal position (try to center, but stay within bounds)
    let left = preferredCenterX - (popupWidth / 2)
    if (left < margin) {
      left = margin
    } else if (left + popupWidth > viewportWidth - margin) {
      left = viewportWidth - margin - popupWidth
    }

    // Calculate vertical position and height
    let top = preferredTop
    let height = defaultHeight

    // Check if popup fits below citation
    const spaceBelow = viewportHeight - preferredTop - margin
    const spaceAbove = citationRect.top - margin

    if (spaceBelow >= minHeight) {
      // Popup fits below citation
      top = preferredTop
      height = Math.max(minHeight, Math.min(defaultHeight, spaceBelow))
    } else if (spaceAbove >= minHeight) {
      // Not enough space below, try above citation
      height = Math.max(minHeight, Math.min(defaultHeight, spaceAbove))
      top = citationRect.top - height - 5
    } else {
      // Very constrained space - use the larger of the two spaces
      if (spaceBelow > spaceAbove) {
        top = preferredTop
        height = Math.max(minHeight, spaceBelow)
      } else {
        height = Math.max(minHeight, spaceAbove)
        top = citationRect.top - height - 5
      }
    }

    return {
      top,
      left,
      width: popupWidth,
      height
    }
  }


  // Generic function to fetch citation content
  const fetchCitation = async (citationId: string) => {
    if (citationCache[citationId] || loadingCitations.has(citationId)) {
      return
    }

    const [fileId, chunkIndexWithPrefix] = citationId.split(':')
    const chunkIndex = chunkIndexWithPrefix.replace('ck', '')

    setLoadingCitations(prev => new Set(prev).add(citationId))

    try {
      const response = await fetch(`/api/citations/${fileId}/${chunkIndex}?language=${language.toUpperCase()}`)

      if (response.ok) {
        const data: CitationResponse = await response.json()
        setCitationCache(prev => ({ ...prev, [citationId]: data }))
      } else {
        // Cache the error to prevent repeated requests
        const errorMessage = `${t('citation.fetchFailed')} (${response.status}): ${response.statusText}`
        console.error(errorMessage)
        setCitationCache(prev => ({ ...prev, [citationId]: { error: errorMessage } }))
      }
    } catch (error) {
      // Cache network errors as well
      const errorMessage = `${t('citation.networkError')}: ${error instanceof Error ? error.message : 'Unknown error'}`
      console.error(errorMessage)
      setCitationCache(prev => ({ ...prev, [citationId]: { error: errorMessage } }))
    } finally {
      setLoadingCitations(prev => {
        const newSet = new Set(prev)
        newSet.delete(citationId)
        return newSet
      })
    }
  }



  const getSourceContent = (citationId: string): CitationContentData => {
    const [fileId, chunkIndexWithPrefix] = citationId.split(':')
    const cached = citationCache[citationId]
    const loading = loadingCitations.has(citationId)

    if (cached) {
      if ('error' in cached) {
        // This is a cached error
        return {
          title: `${t('citation.source')}: ${fileId}`,
          chunks: [],
          content: `${t('citation.error')}: ${cached.error}`,
          fileId,
          chunkIndexWithPrefix
        }
      } else {
        // This is a successful response
        return {
          title: `${t('citation.source')}: ${cached.metadata.filename || fileId}`,
          chunks: [],
          content: cached.content,
          fileId,
          chunkIndexWithPrefix
        }
      }
    } else if (loading) {
      return {
        title: `${t('citation.source')}: ${fileId}`,
        chunks: [],
        content: t('citation.loading'),
        fileId,
        chunkIndexWithPrefix
      }
    } else {
      return {
        title: `${t('citation.source')}: ${fileId}`,
        chunks: [],
        content: `${t('citation.notLoaded')} ${chunkIndexWithPrefix}.`,
        fileId,
        chunkIndexWithPrefix
      }
    }
  }

  const getStickyContent = (citationId: string): CitationContentData => {
    const [fileId, chunkIndexWithPrefix] = citationId.split(':')

    // Get all chunks for this file from the citation cache
    const fileChunks = Object.entries(citationCache)
      .filter(([key, value]) => key.startsWith(`${fileId}:`) && !('error' in value))
      .map(([_, value]) => value as CitationResponse)
      .sort((a, b) => a.metadata.chunk_index - b.metadata.chunk_index)

    if (fileChunks.length > 0) {
      return {
        title: `${t('citation.source')}: ${fileChunks[0].metadata.filename || fileId}`,
        chunks: fileChunks,
        content: '',
        fileId,
        currentChunkIndexWithPrefix: chunkIndexWithPrefix
      }
    }

    return getSourceContent(citationId)
  }

  // Custom components for ReactMarkdown
  const components: Components = {
    a: ({ href, children }) => {
      // Check if this is a citation link
      if (href?.includes('istaroth.markdown/citation/')) {
        // Extract file_id and chunk_index from URL
        const match = href.match(/citation\/([^\/]+)\/(\d+)/)
        if (match) {
          const citationId = `${match[1]}:${match[2]}`
          const isHovered = hoveredCitation === citationId

          return (
            <sup
              data-citation-id={citationId}
              onMouseEnter={(e) => handleCitationHover(e, citationId)}
              onClick={(e) => handleCitationClick(e, citationId)}
              style={{
                color: stickyCitation === citationId ? '#2c7cd6' : '#5594d9',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                textDecoration: 'none',
                padding: '2px 4px',
                borderRadius: '3px',
                backgroundColor: isHovered || stickyCitation === citationId ? 'rgba(52, 152, 219, 0.15)' : 'transparent'
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
  }

  const processedContent = preprocessContent(content)

  const displayedCitation = stickyCitation || hoveredCitation
  const isSticky = stickyCitation !== null

  return (
    <div style={{ position: 'relative' }} data-citation-container>
      {displayedCitation && (
        <CitationPopup
          ref={popupRef}
          title={isSticky ? getStickyContent(displayedCitation).title : getSourceContent(displayedCitation).title}
          content={isSticky ? undefined : getSourceContent(displayedCitation).content}
          chunks={isSticky ? getStickyContent(displayedCitation).chunks : undefined}
          fileId={isSticky ? getStickyContent(displayedCitation).fileId : undefined}
          currentChunkIndex={isSticky ? getStickyContent(displayedCitation).currentChunkIndexWithPrefix : undefined}
          isSticky={isSticky}
          isFullscreen={isFullscreen}
          onClose={handleCloseSticky}
          onLoadChunk={isSticky ? fetchCitation : undefined}
          onToggleFullscreen={isSticky ? handleToggleFullscreen : undefined}
          loadingCitations={loadingCitations}
          style={{
            top: `${popupPosition.top}px`,
            left: `${popupPosition.left}px`,
            width: `${popupPosition.width}px`,
            height: `${popupPosition.height}px`
          }}
        />
      )}

      <ReactMarkdown components={components}>{processedContent}</ReactMarkdown>
    </div>
  )
}

export default CitationRenderer

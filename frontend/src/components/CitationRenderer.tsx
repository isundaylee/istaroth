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

function CitationRenderer({ content }: CitationRendererProps) {
  const [hoveredCitation, setHoveredCitation] = useState<string | null>(null)
  const [stickyCitation, setStickyCitation] = useState<string | null>(null)
  const [popupPosition, setPopupPosition] = useState({ top: 0, left: 0 })
  const [citationCache, setCitationCache] = useState<Record<string, CachedCitation>>({})
  const [loadingCitations, setLoadingCitations] = useState<Set<string>>(new Set())
  const { language } = useTranslation()
  const t = useT()
  const popupRef = useRef<HTMLDivElement>(null)

  // Preprocess content to convert [[file_id:chunk_index]] to markdown links with document:chunk numbering
  const preprocessContent = (text: string): string => {
    const citationPattern = /\[\[([^:]+):(\d+)\]\]/g
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
    fetchCitationContent(citationId)

    // Calculate position relative to viewport (for fixed positioning)
    const viewportTop = citationRect.bottom + 5
    const viewportCenterX = citationRect.left + (citationRect.width / 2)

    setPopupPosition({
      top: viewportTop,
      left: viewportCenterX
    })
  }

  const handleCitationLeave = () => {
    // Don't clear hover if any citation is sticky
    if (stickyCitation) return
    setHoveredCitation(null)
  }

  const handleCitationClick = (e: React.MouseEvent<HTMLElement>, citationId: string) => {
    e.preventDefault()
    e.stopPropagation()

    const citationRect = e.currentTarget.getBoundingClientRect()

    // Fetch citation content if not already cached
    fetchCitationContent(citationId)

    // Calculate position relative to viewport (for fixed positioning)
    const viewportTop = citationRect.bottom + 5
    const viewportCenterX = citationRect.left + (citationRect.width / 2)

    setPopupPosition({
      top: viewportTop,
      left: viewportCenterX
    })

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
  }

  // Adjust popup position if it goes off-screen
  useEffect(() => {
    if (hoveredCitation && popupRef.current) {
      const popup = popupRef.current
      const popupWidth = popup.offsetWidth
      const popupHeight = popup.offsetHeight

      // Center the popup horizontally on the citation
      let adjustedLeft = popupPosition.left - (popupWidth / 2)
      let adjustedTop = popupPosition.top

      // Check if popup goes off left edge of viewport
      if (adjustedLeft < 10) {
        adjustedLeft = 10
      }

      // Check if popup goes off right edge of viewport
      if (adjustedLeft + popupWidth > window.innerWidth - 10) {
        adjustedLeft = window.innerWidth - 10 - popupWidth
      }

      // Check if popup goes off bottom edge of viewport
      if (adjustedTop + popupHeight > window.innerHeight - 20) {
        // Show above the citation instead
        adjustedTop = popupPosition.top - popupHeight - 35
      }

      // Apply the calculated position
      popup.style.left = `${adjustedLeft}px`
      popup.style.top = `${adjustedTop}px`
    }
  }, [hoveredCitation, popupPosition])

  // Fetch citation content from backend
  const fetchCitationContent = async (citationId: string) => {
    if (citationCache[citationId] || loadingCitations.has(citationId)) {
      return
    }

    const [fileId, chunkIndex] = citationId.split(':')

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

  const getSourceContent = (citationId: string) => {
    const [fileId, chunkIndex] = citationId.split(':')
    const cached = citationCache[citationId]
    const loading = loadingCitations.has(citationId)

    if (cached) {
      if ('error' in cached) {
        // This is a cached error
        return {
          title: `${t('citation.source')}: ${fileId}`,
          content: `${t('citation.error')}: ${cached.error}`
        }
      } else {
        // This is a successful response
        return {
          title: `${t('citation.source')}: ${cached.metadata.filename || fileId}`,
          content: cached.content
        }
      }
    } else if (loading) {
      return {
        title: `${t('citation.source')}: ${fileId}`,
        content: t('citation.loading')
      }
    } else {
      return {
        title: `${t('citation.source')}: ${fileId}`,
        content: `${t('citation.notLoaded')} ${chunkIndex}.`
      }
    }
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
              onMouseLeave={handleCitationLeave}
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
          title={getSourceContent(displayedCitation).title}
          content={getSourceContent(displayedCitation).content}
          isSticky={isSticky}
          onClose={handleCloseSticky}
          style={{
            top: `${popupPosition.top}px`,
            left: `${popupPosition.left}px`
          }}
        />
      )}

      <ReactMarkdown components={components}>{processedContent}</ReactMarkdown>
    </div>
  )
}

export default CitationRenderer

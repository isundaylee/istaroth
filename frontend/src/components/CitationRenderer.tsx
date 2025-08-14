import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import CitationPopup from './CitationPopup'

interface CitationRendererProps {
  content: string
}

function CitationRenderer({ content }: CitationRendererProps) {
  const [hoveredCitation, setHoveredCitation] = useState<string | null>(null)
  const [popupPosition, setPopupPosition] = useState({ top: 0, left: 0 })
  const popupRef = useRef<HTMLDivElement>(null)

  // Preprocess content to convert [[file_id:chunk_index]] to markdown links
  const preprocessContent = (text: string): string => {
    // Convert [[file_id:chunk_index]] to [chunk_index](http://istaroth.markdown/citation/file_id/chunk_index)
    return text.replace(/\[\[([^:]+):(\d+)\]\]/g, '[$2](http://istaroth.markdown/citation/$1/$2)')
  }

  const handleCitationHover = (e: React.MouseEvent<HTMLElement>, citationId: string) => {
    const citationRect = e.currentTarget.getBoundingClientRect()
    const container = e.currentTarget.closest('[data-citation-container]')
    const containerRect = container?.getBoundingClientRect()

    if (!containerRect) return

    setHoveredCitation(citationId)

    // Calculate position relative to the container
    const relativeTop = citationRect.bottom - containerRect.top + 5
    const relativeCenterX = citationRect.left + (citationRect.width / 2) - containerRect.left

    setPopupPosition({
      top: relativeTop,
      left: relativeCenterX
    })
  }

  // Adjust popup position if it goes off-screen
  useEffect(() => {
    if (hoveredCitation && popupRef.current) {
      const popup = popupRef.current
      const containerEl = popup.closest('[data-citation-container]')

      if (!containerEl) return

      const containerRect = containerEl.getBoundingClientRect()
      const popupWidth = popup.offsetWidth
      const popupHeight = popup.offsetHeight

      // Center the popup horizontally on the citation
      let adjustedLeft = popupPosition.left - (popupWidth / 2)
      let adjustedTop = popupPosition.top

      // Check if popup goes off left edge of viewport
      const absoluteLeft = containerRect.left + adjustedLeft
      if (absoluteLeft < 10) {
        adjustedLeft = 10 - containerRect.left
      }

      // Check if popup goes off right edge of viewport
      const absoluteRight = containerRect.left + adjustedLeft + popupWidth
      if (absoluteRight > window.innerWidth - 10) {
        adjustedLeft = window.innerWidth - 10 - popupWidth - containerRect.left
      }

      // Check if popup goes off bottom edge of viewport
      const absoluteBottom = containerRect.top + adjustedTop + popupHeight
      if (absoluteBottom > window.innerHeight - 20) {
        // Show above the citation instead
        adjustedTop = popupPosition.top - popupHeight - 35
      }

      // Apply the calculated position
      popup.style.left = `${adjustedLeft}px`
      popup.style.top = `${adjustedTop}px`
    }
  }, [hoveredCitation, popupPosition])

  // Placeholder text for demonstration
  const getSourceContent = (citationId: string) => {
    const [fileId, chunkIndex] = citationId.split(':')
    return {
      title: `Source: ${fileId}`,
      content: `This is placeholder text for the source content from file "${fileId}" at chunk index ${chunkIndex}. In the actual implementation, this would show the original text content that was retrieved from the RAG system.

The content would include the full context around the quoted passage, helping users understand where the information came from and verify its accuracy.

This popup provides transparency about the AI's sources and allows users to trace information back to its origin.`
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
              onMouseLeave={() => setHoveredCitation(null)}
              style={{
                color: '#5594d9',
                // fontSize: '0.8em',
                fontWeight: 500,
                cursor: 'help',
                transition: 'all 0.15s ease',
                textDecoration: isHovered ? 'underline' : 'none',
                padding: '0 1px'
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

  return (
    <div style={{ position: 'relative' }} data-citation-container>
      <ReactMarkdown components={components}>{processedContent}</ReactMarkdown>

      {hoveredCitation && (
        <CitationPopup
          ref={popupRef}
          title={getSourceContent(hoveredCitation).title}
          content={getSourceContent(hoveredCitation).content}
          style={{
            top: `${popupPosition.top}px`,
            left: `${popupPosition.left}px`,
          }}
        />
      )}
    </div>
  )
}

export default CitationRenderer

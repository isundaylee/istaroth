import { forwardRef, useEffect, useRef } from 'react'
import type { CitationResponse } from '../types/api'
import { useTranslation } from '../contexts/LanguageContext'
import { FloatingPanel } from './FloatingPanel'
import type { FloatingPlacement } from '../utils/floatingPanel'

interface CitationPopupProps {
  /** File title (the "Source" eyebrow is added by the shared frame). */
  title: string
  content?: string
  chunks?: CitationResponse[]
  fileId?: string
  currentChunkIndex: number
  isSticky?: boolean
  isFullscreen?: boolean
  placement: FloatingPlacement
  top: number
  left: number
  onClose?: () => void
  onLoadChunk?: (citationId: string) => void
  onLoadAllChunks?: (fileId: string) => void
  onToggleFullscreen?: () => void
  loadingCitations?: Set<string>
}

const CitationPopup = forwardRef<HTMLDivElement, CitationPopupProps>(
  (
    {
      title,
      content,
      chunks,
      fileId,
      currentChunkIndex,
      isSticky = false,
      isFullscreen = false,
      placement,
      top,
      left,
      onClose,
      onLoadChunk,
      onLoadAllChunks,
      onToggleFullscreen,
      loadingCitations
    },
    ref
  ) => {
    const { t } = useTranslation()
    const contentRef = useRef<HTMLDivElement>(null)
    const previousChunkIdsRef = useRef<Set<string>>(new Set())

    const isLoadingAllChunks = fileId && loadingCitations
      ? Array.from(loadingCitations).some(id => id.startsWith(`${fileId}:`))
      : false

    // Scroll to newly loaded chunk when chunks array changes
    useEffect(() => {
      if (chunks && chunks.length > 0 && contentRef.current) {
        const currentChunkIds = new Set(chunks.map(c => c.chunk_index.toString()))
        const newChunkIds = [...currentChunkIds].filter(id => !previousChunkIdsRef.current.has(id))

        if (newChunkIds.length > 0) {
          const firstNewChunkId = newChunkIds[0]
          const chunkElement = contentRef.current.querySelector(`[data-chunk-id="chunk-${firstNewChunkId}"]`)
          if (chunkElement) {
            setTimeout(() => {
              chunkElement.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' })
            }, 100)
          }
        }

        previousChunkIdsRef.current = currentChunkIds
      }
    }, [chunks])

    const actions = isSticky && (
      <>
        {onLoadAllChunks && fileId && chunks && chunks.length > 0 && (
          <button
            onClick={() => onLoadAllChunks(fileId)}
            disabled={isLoadingAllChunks}
            className="floating-panel__action-btn"
            title={t.citation.loadAllChunks}
          >
            {isLoadingAllChunks ? t.citation.loadingButton : t.citation.loadAllChunks}
          </button>
        )}
        {onToggleFullscreen && (
          <button
            onClick={onToggleFullscreen}
            className="floating-panel__action-btn"
            title={isFullscreen ? t.citation.exitFullscreen : t.citation.enterFullscreen}
          >
            {isFullscreen ? '⧉' : '⛶'}
          </button>
        )}
      </>
    )

    const body = isSticky && chunks && fileId ? (
      <div ref={contentRef}>
        {onLoadChunk && chunks.length > 0 && chunks[0].chunk_index > 0 && (() => {
          const prevId = `${fileId}:ck${chunks[0].chunk_index - 1}`
          return (
            <button
              onClick={() => onLoadChunk(prevId)}
              disabled={loadingCitations?.has(prevId)}
              className="citation-gap"
            >
              {loadingCitations?.has(prevId) ? t.citation.loadingButton : t.citation.loadPrevious}
            </button>
          )
        })()}

        {chunks.map((chunk, index) => {
          const nextChunk = chunks[index + 1]
          const gapSize = nextChunk ? nextChunk.chunk_index - chunk.chunk_index - 1 : 0
          const isCited = chunk.chunk_index === currentChunkIndex
          // Expand the gap from the side nearer the cited chunk (cited is never inside a gap).
          const gapLoadIndex = currentChunkIndex <= chunk.chunk_index
            ? chunk.chunk_index + 1
            : (nextChunk ? nextChunk.chunk_index - 1 : 0)
          const gapStartId = `${fileId}:ck${gapLoadIndex}`

          return (
            <div key={chunk.chunk_index} data-chunk-id={`chunk-${chunk.chunk_index}`}>
              <div style={{
                borderLeft: `3px solid ${isCited ? 'var(--color-primary)' : 'transparent'}`,
                paddingLeft: '12px'
              }}>
                {isCited && (
                  <div style={{
                    display: 'inline-block',
                    marginBottom: '6px',
                    padding: '2px 8px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'var(--color-citation-label-bg)',
                    color: 'var(--color-primary-dark)',
                    fontSize: 'var(--font-xs)'
                  }}>
                    {t.citation.current}
                  </div>
                )}
                <div style={{ whiteSpace: 'pre-wrap' }}>{chunk.content}</div>
              </div>

              {nextChunk && (gapSize > 0 && onLoadChunk ? (
                <button
                  onClick={() => onLoadChunk(gapStartId)}
                  disabled={loadingCitations?.has(gapStartId)}
                  className="citation-gap"
                >
                  {loadingCitations?.has(gapStartId)
                    ? t.citation.loadingButton
                    : `⋯ ${gapSize} ${t.citation.chunksHidden}`}
                </button>
              ) : (
                <hr className="citation-divider" />
              ))}
            </div>
          )
        })}

        {onLoadChunk && chunks.length > 0 && chunks[chunks.length - 1].chunk_index < chunks[chunks.length - 1].total_chunks - 1 && (() => {
          const nextId = `${fileId}:ck${chunks[chunks.length - 1].chunk_index + 1}`
          return (
            <button
              onClick={() => onLoadChunk(nextId)}
              disabled={loadingCitations?.has(nextId)}
              className="citation-gap"
            >
              {loadingCitations?.has(nextId) ? t.citation.loadingButton : t.citation.loadNext}
            </button>
          )
        })()}
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

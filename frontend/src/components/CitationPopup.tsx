import { forwardRef, useEffect, useRef } from 'react'
import type { CitationResponse } from '../types/api'
import { useTranslation } from '../contexts/LanguageContext'
import { FloatingPanel } from './FloatingPanel'
import type { FloatingPlacement } from '../utils/floatingPanel'

interface MainLoadButtonProps {
  onClick: () => void
  disabled?: boolean
  loading?: boolean
  block?: boolean
  children: React.ReactNode
}

const MainLoadButton = ({ onClick, disabled = false, loading = false, block = false, children }: MainLoadButtonProps) => {
  const { t } = useTranslation()

  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`floating-panel__action-btn${block ? ' floating-panel__action-btn--block' : ''}`}
    >
      {loading ? t.citation.loadingButton : children}
    </button>
  )
}

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

    const actions = isSticky && onLoadAllChunks && fileId && chunks && chunks.length > 0 && (
      <button
        onClick={() => onLoadAllChunks(fileId)}
        disabled={isLoadingAllChunks}
        className="floating-panel__action-btn"
        title={t.citation.loadAllChunks}
      >
        {isLoadingAllChunks ? t.citation.loadingButton : t.citation.loadAllChunks}
      </button>
    )

    const body = isSticky && chunks && fileId ? (
      <div ref={contentRef}>
        {onLoadChunk && chunks.length > 0 && chunks[0].chunk_index > 0 && (
          <div style={{ marginBottom: '12px' }}>
            <MainLoadButton
              block
              onClick={() => {
                const prevChunkIndex = chunks[0].chunk_index - 1
                onLoadChunk(`${fileId}:ck${prevChunkIndex}`)
              }}
              loading={loadingCitations?.has(`${fileId}:ck${chunks[0]?.chunk_index - 1}`)}
            >
              {t.citation.loadPrevious}
            </MainLoadButton>
          </div>
        )}

        {chunks.map((chunk, index) => {
          const currentChunkNum = chunk.chunk_index
          const nextChunk = chunks[index + 1]
          const nextChunkNum = nextChunk ? nextChunk.chunk_index : null
          const hasGap = nextChunkNum !== null && nextChunkNum !== currentChunkNum + 1

          return (
            <div key={chunk.chunk_index} data-chunk-id={`chunk-${chunk.chunk_index}`}>
              <div style={{ marginBottom: index < chunks.length - 1 || hasGap ? '16px' : '0' }}>
                <div style={{
                  fontSize: 'var(--font-xs)',
                  color: 'var(--color-text-secondary)',
                  marginBottom: '4px',
                  fontWeight: chunk.chunk_index === currentChunkIndex ? 'bold' : 'normal',
                  background: 'var(--color-citation-label-bg)',
                  padding: '4px 8px',
                  borderRadius: 'var(--radius-sm)',
                  textAlign: 'right',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center'
                }}>
                  <span>
                    {chunk.chunk_index === currentChunkIndex && (
                      <span style={{
                        color: 'var(--color-primary-dark)',
                        fontSize: 'var(--font-xs)',
                        fontWeight: 'normal',
                        marginRight: '8px'
                      }}>
                        {t.citation.current}
                      </span>
                    )}
                  </span>
                  <span>
                    {t.citation.chunk} {chunk.chunk_index}
                  </span>
                </div>
                <div style={{ whiteSpace: 'pre-wrap' }}>{chunk.content}</div>
              </div>

              {hasGap && onLoadChunk && (
                <div style={{ margin: '16px 0', color: 'var(--color-text-muted)' }}>
                  {(() => {
                    const gapSize = nextChunkNum! - currentChunkNum - 1
                    const firstMissingIndex = currentChunkNum + 1
                    const lastMissingIndex = nextChunkNum! - 1

                    if (gapSize === 1) {
                      return (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <div style={{ fontSize: 'var(--font-lg)', fontWeight: 'bold', textAlign: 'center', flex: 1 }}>⋯</div>
                          <div style={{ padding: '0 8px' }}>
                            <MainLoadButton
                              onClick={() => onLoadChunk(`${fileId}:ck${firstMissingIndex}`)}
                              loading={loadingCitations?.has(`${fileId}:ck${firstMissingIndex}`)}
                            >
                              {t.citation.loadChunk} {firstMissingIndex}
                            </MainLoadButton>
                          </div>
                          <div style={{ fontSize: 'var(--font-lg)', fontWeight: 'bold', textAlign: 'center', flex: 1 }}>⋯</div>
                        </div>
                      )
                    }
                    return (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <div style={{ padding: '0 8px' }}>
                          <MainLoadButton
                            onClick={() => onLoadChunk(`${fileId}:ck${firstMissingIndex}`)}
                            loading={loadingCitations?.has(`${fileId}:ck${firstMissingIndex}`)}
                          >
                            {t.citation.loadChunkUp} {firstMissingIndex}
                          </MainLoadButton>
                        </div>
                        <div style={{ fontSize: 'var(--font-lg)', fontWeight: 'bold', textAlign: 'center', flex: 1 }}>⋯</div>
                        <div style={{ padding: '0 8px' }}>
                          <MainLoadButton
                            onClick={() => onLoadChunk(`${fileId}:ck${lastMissingIndex}`)}
                            loading={loadingCitations?.has(`${fileId}:ck${lastMissingIndex}`)}
                          >
                            {t.citation.loadChunkDown} {lastMissingIndex}
                          </MainLoadButton>
                        </div>
                      </div>
                    )
                  })()}
                </div>
              )}
            </div>
          )
        })}

        {onLoadChunk && chunks.length > 0 && chunks[chunks.length - 1].chunk_index < chunks[chunks.length - 1].total_chunks - 1 && (
          <div style={{ marginTop: '12px' }}>
            <MainLoadButton
              block
              onClick={() => {
                const nextChunkIndex = chunks[chunks.length - 1].chunk_index + 1
                onLoadChunk(`${fileId}:ck${nextChunkIndex}`)
              }}
              loading={loadingCitations?.has(`${fileId}:ck${chunks[chunks.length - 1]?.chunk_index + 1}`)}
            >
              {t.citation.loadNext}
            </MainLoadButton>
          </div>
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

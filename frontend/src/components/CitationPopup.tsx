import { forwardRef, useEffect, useRef } from 'react'
import type { CitationResponse } from '../types/api'

interface LoadButtonProps {
  onClick: () => void
  disabled?: boolean
  loading?: boolean
  children: React.ReactNode
  style?: React.CSSProperties
}

const LoadButton = ({ onClick, disabled = false, loading = false, children, style }: LoadButtonProps) => (
  <button
    onClick={onClick}
    disabled={disabled || loading}
    style={{
      padding: '4px 8px',
      background: '#f8f9fa',
      border: '1px solid #dee2e6',
      borderRadius: '4px',
      cursor: disabled || loading ? 'default' : 'pointer',
      fontSize: '0.7rem',
      color: '#495057',
      transition: 'background-color 0.15s ease',
      opacity: disabled || loading ? 0.6 : 1,
      ...style
    }}
    onMouseEnter={(e) => {
      if (!disabled && !loading) {
        e.currentTarget.style.backgroundColor = '#e9ecef'
      }
    }}
    onMouseLeave={(e) => {
      if (!disabled && !loading) {
        e.currentTarget.style.backgroundColor = '#f8f9fa'
      }
    }}
  >
    {loading ? '载入中...' : children}
  </button>
)

interface MainLoadButtonProps {
  onClick: () => void
  disabled?: boolean
  loading?: boolean
  children: React.ReactNode
}

const MainLoadButton = ({ onClick, disabled = false, loading = false, children }: MainLoadButtonProps) => (
  <button
    onClick={onClick}
    disabled={disabled || loading}
    style={{
      width: '100%',
      padding: '6px 12px',
      background: '#f8f9fa',
      border: '1px solid #dee2e6',
      borderRadius: '4px',
      cursor: disabled || loading ? 'default' : 'pointer',
      fontSize: '0.8rem',
      color: '#495057',
      transition: 'background-color 0.15s ease',
      opacity: disabled || loading ? 0.6 : 1
    }}
    onMouseEnter={(e) => {
      if (!disabled && !loading) {
        e.currentTarget.style.backgroundColor = '#e9ecef'
      }
    }}
    onMouseLeave={(e) => {
      if (!disabled && !loading) {
        e.currentTarget.style.backgroundColor = '#f8f9fa'
      }
    }}
  >
    {loading ? '载入中...' : children}
  </button>
)

interface CitationPopupProps {
  title: string
  content?: string
  chunks?: CitationResponse[]
  fileId?: string
  currentChunkIndex?: string
  isSticky?: boolean
  isFullscreen?: boolean
  onClose?: () => void
  onLoadChunk?: (citationId: string) => void
  onToggleFullscreen?: () => void
  loadingCitations?: Set<string>
  style?: React.CSSProperties
}

const CitationPopup = forwardRef<HTMLDivElement, CitationPopupProps>(
  ({
    title,
    content,
    chunks,
    fileId,
    currentChunkIndex,
    isSticky = false,
    isFullscreen = false,
    onClose,
    onLoadChunk,
    onToggleFullscreen,
    loadingCitations,
    style
  }, ref) => {
    const contentRef = useRef<HTMLDivElement>(null)
    const previousChunkIdsRef = useRef<Set<string>>(new Set())

    // Scroll to newly loaded chunk when chunks array changes
    useEffect(() => {
      if (chunks && chunks.length > 0 && contentRef.current) {
        const currentChunkIds = new Set(chunks.map(c => c.metadata.chunk_index.toString()))

        // Find chunks that are new (not in previous set)
        const newChunkIds = [...currentChunkIds].filter(id => !previousChunkIdsRef.current.has(id))

        if (newChunkIds.length > 0) {
          // Scroll to the first new chunk found
          const firstNewChunkId = newChunkIds[0]
          const chunkElement = contentRef.current.querySelector(`[data-chunk-id="chunk-${firstNewChunkId}"]`)

          if (chunkElement) {
            // Small delay to ensure DOM is updated
            setTimeout(() => {
              chunkElement.scrollIntoView({
                behavior: 'smooth',
                block: 'nearest',
                inline: 'nearest'
              })
            }, 100)
          }
        }

        // Update previous chunk IDs
        previousChunkIdsRef.current = currentChunkIds
      }
    }, [chunks])
    return (
      <div
        ref={ref}
        style={{
          position: 'fixed',
          background: 'white',
          border: '1px solid #ddd',
          borderRadius: isFullscreen ? '0' : '8px',
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
          maxWidth: isFullscreen ? 'none' : '500px',
          minWidth: isFullscreen ? 'none' : '300px',
          width: isFullscreen ? '100vw' : 'auto',
          height: isFullscreen ? '100vh' : 'auto',
          top: isFullscreen ? 0 : undefined,
          left: isFullscreen ? 0 : undefined,
          right: isFullscreen ? 0 : undefined,
          bottom: isFullscreen ? 0 : undefined,
          zIndex: isFullscreen ? 1001 : 1000,
          animation: 'fadeIn 0.2s ease',
          pointerEvents: 'auto',
          ...(isFullscreen ? {} : style)
        }}
      >
        <div
          style={{
            padding: '12px 16px',
            background: '#3498db',
            color: 'white',
            fontWeight: 600,
            fontSize: '0.9rem',
            borderRadius: '8px 8px 0 0',
            position: 'relative',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}
        >
          <span>{title}</span>
          {isSticky && (
            <div style={{ display: 'flex', gap: '4px' }}>
              {/* Fullscreen toggle button */}
              {onToggleFullscreen && (
                <button
                  onClick={onToggleFullscreen}
                  style={{
                    background: 'rgba(255, 255, 255, 0.2)',
                    border: 'none',
                    color: 'white',
                    borderRadius: '25%',
                    width: '22px',
                    height: '22px',
                    lineHeight: '22px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '12px',
                    fontWeight: 'bold',
                    transition: 'background-color 0.15s ease',
                    flexShrink: 0
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.3)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.2)'
                  }}
                  title={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
                >
                  {isFullscreen ? '⧉' : '⛶'}
                </button>
              )}

              {/* Close button */}
              {onClose && (
                <button
                  onClick={onClose}
                  style={{
                    background: 'rgba(255, 255, 255, 0.2)',
                    border: 'none',
                    color: 'white',
                    borderRadius: '25%',
                    width: '22px',
                    height: '22px',
                    lineHeight: '22px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '16px',
                    fontWeight: 'bold',
                    transition: 'background-color 0.15s ease',
                    paddingBottom: '1px',
                    flexShrink: 0
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.3)'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.2)'
                  }}
                  title="Close"
                >
                  ×
                </button>
              )}
            </div>
          )}
        </div>
        {isSticky && chunks && fileId && currentChunkIndex ? (
          // Sticky mode with multiple chunks and load buttons
          <div style={{
            display: isFullscreen ? 'flex' : 'block',
            flexDirection: isFullscreen ? 'column' : undefined,
            height: isFullscreen ? 'calc(100vh - 60px)' : 'auto'
          }}>
            {/* Load previous button */}
            {onLoadChunk && chunks && chunks.length > 0 && chunks[0].metadata.chunk_index > 0 && (
              <div style={{ padding: '8px 16px', borderBottom: '1px solid #eee' }}>
                <MainLoadButton
                  onClick={() => {
                    const firstChunk = chunks[0]
                    const prevChunkIndex = firstChunk.metadata.chunk_index - 1
                    const prevCitationId = `${fileId}:ck${prevChunkIndex}`
                    onLoadChunk(prevCitationId)
                  }}
                  loading={loadingCitations?.has(`${fileId}:ck${chunks[0]?.metadata.chunk_index - 1}`)}
                >
                  ↑ 载入上一段
                </MainLoadButton>
              </div>
            )}

            {/* Chunks content */}
            <div
              ref={contentRef}
              style={{
                padding: '16px',
                maxHeight: isFullscreen ? 'calc(100vh - 120px)' : '300px',
                overflowY: 'auto',
                fontSize: '0.9rem',
                lineHeight: 1.6,
                color: '#333',
                scrollbarWidth: 'thin',
                scrollbarColor: '#3498db transparent',
                flex: isFullscreen ? 1 : 'none'
              }}
              className="citation-popup-content"
            >
              {chunks.map((chunk, index) => {
                const currentChunkNum = chunk.metadata.chunk_index
                const nextChunk = chunks[index + 1]
                const nextChunkNum = nextChunk ? nextChunk.metadata.chunk_index : null
                const hasGap = nextChunkNum !== null && nextChunkNum !== currentChunkNum + 1

                return (
                  <div key={chunk.metadata.chunk_index} data-chunk-id={`chunk-${chunk.metadata.chunk_index}`}>
                    <div style={{ marginBottom: index < chunks.length - 1 || hasGap ? '16px' : '0' }}>
                      <div style={{
                        fontSize: '0.75rem',
                        color: '#666',
                        marginBottom: '4px',
                        fontWeight: chunk.metadata.chunk_index === currentChunkIndex ? 'bold' : 'normal',
                        background: chunk.metadata.chunk_index === currentChunkIndex ? '#e3f2fd' : 'transparent',
                        padding: '2px 6px',
                        borderRadius: '3px'
                      }}>
                        {chunk.metadata.chunk_index}
                      </div>
                      <div style={{ whiteSpace: 'pre-wrap' }}>{chunk.content}</div>
                    </div>

                    {/* Show ellipsis and load button(s) if there's a gap to the next chunk */}
                    {hasGap && onLoadChunk && (
                      <div style={{
                        margin: '16px 0',
                        color: '#999'
                      }}>
                        {(() => {
                          const gapSize = nextChunkNum! - currentChunkNum - 1
                          const firstMissingIndex = currentChunkNum + 1
                          const lastMissingIndex = nextChunkNum! - 1

                          if (gapSize === 1) {
                            return (
                              <div style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '12px'
                              }}>
                                <div style={{
                                  fontSize: '1.2rem',
                                  fontWeight: 'bold',
                                  textAlign: 'center',
                                  flex: 1
                                }}>
                                  ⋯
                                </div>
                                <div style={{ padding: '0 8px' }}>
                                  <MainLoadButton
                                    onClick={() => {
                                      const missingCitationId = `${fileId}:ck${firstMissingIndex}`
                                      onLoadChunk(missingCitationId)
                                    }}
                                    loading={loadingCitations?.has(`${fileId}:ck${firstMissingIndex}`)}
                                  >
                                    载入段落 {firstMissingIndex}
                                  </MainLoadButton>
                                </div>
                                <div style={{
                                  fontSize: '1.2rem',
                                  fontWeight: 'bold',
                                  textAlign: 'center',
                                  flex: 1
                                }}>
                                  ⋯
                                </div>
                              </div>
                            )
                          } else {
                            return (
                              <div style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '12px'
                              }}>
                                <div style={{ padding: '0 8px' }}>
                                  <MainLoadButton
                                    onClick={() => {
                                      const missingCitationId = `${fileId}:ck${firstMissingIndex}`
                                      onLoadChunk(missingCitationId)
                                    }}
                                    loading={loadingCitations?.has(`${fileId}:ck${firstMissingIndex}`)}
                                  >
                                    ↑ 载入段落 {firstMissingIndex}
                                  </MainLoadButton>
                                </div>
                                <div style={{
                                  fontSize: '1.2rem',
                                  fontWeight: 'bold',
                                  textAlign: 'center',
                                  flex: 1
                                }}>
                                  ⋯
                                </div>
                                <div style={{ padding: '0 8px' }}>
                                  <MainLoadButton
                                    onClick={() => {
                                      const missingCitationId = `${fileId}:ck${lastMissingIndex}`
                                      onLoadChunk(missingCitationId)
                                    }}
                                    loading={loadingCitations?.has(`${fileId}:ck${lastMissingIndex}`)}
                                  >
                                    ↓ 载入段落 {lastMissingIndex}
                                  </MainLoadButton>
                                </div>
                              </div>
                            )
                          }
                        })()}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            {/* Load next button */}
            {onLoadChunk && chunks && chunks.length > 0 && chunks[chunks.length - 1].metadata.chunk_index < chunks[chunks.length - 1].total_chunks - 1 && (
              <div style={{ padding: '8px 16px', borderTop: '1px solid #eee' }}>
                <MainLoadButton
                  onClick={() => {
                    const lastChunk = chunks[chunks.length - 1]
                    const nextChunkIndex = lastChunk.metadata.chunk_index + 1
                    const nextCitationId = `${fileId}:ck${nextChunkIndex}`
                    onLoadChunk(nextCitationId)
                  }}
                  loading={loadingCitations?.has(`${fileId}:ck${chunks[chunks.length - 1]?.metadata.chunk_index + 1}`)}
                >
                  ↓ 载入下一段
                </MainLoadButton>
              </div>
            )}
          </div>
        ) : (
          // Non-sticky mode with single content
          <div
            style={{
              padding: '16px',
              maxHeight: '300px',
              overflowY: 'auto',
              fontSize: '0.9rem',
              lineHeight: 1.6,
              color: '#333',
              whiteSpace: 'pre-wrap',
              scrollbarWidth: 'thin',
              scrollbarColor: '#3498db transparent'
            }}
            className="citation-popup-content"
          >
            {content}
          </div>
        )}
      </div>
    )
  }
)

CitationPopup.displayName = 'CitationPopup'

export default CitationPopup

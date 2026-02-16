import { forwardRef, useEffect, useRef } from 'react'
import type { CitationResponse } from '../types/api'
import { useTranslation } from '../contexts/LanguageContext'

interface MainLoadButtonProps {
  onClick: () => void
  disabled?: boolean
  loading?: boolean
  children: React.ReactNode
}

const MainLoadButton = ({ onClick, disabled = false, loading = false, children }: MainLoadButtonProps) => {
  const { t } = useTranslation()

  return (
  <button
    onClick={onClick}
    disabled={disabled || loading}
    style={{
      width: '100%',
      padding: '6px 12px',
      background: '#f8f9fa',
      border: '1px solid #dee2e6',
      borderRadius: 'var(--radius-md)',
      cursor: disabled || loading ? 'default' : 'pointer',
      fontSize: 'var(--font-sm)',
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
    {loading ? t.citation.loadingButton : children}
  </button>
  )
}

interface CitationPopupProps {
  title: string
  content?: string
  chunks?: CitationResponse[]
  fileId?: string
  currentChunkIndex: number
  isSticky?: boolean
  isFullscreen?: boolean
  onClose?: () => void
  onLoadChunk?: (citationId: string) => void
  onLoadAllChunks?: (fileId: string) => void
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
    onLoadAllChunks,
    onToggleFullscreen,
    loadingCitations,
    style
  }, ref) => {
    const { t } = useTranslation()
    const contentRef = useRef<HTMLDivElement>(null)
    const previousChunkIdsRef = useRef<Set<string>>(new Set())

    // Check if any chunks for this file are currently loading
    const isLoadingAllChunks = fileId && loadingCitations
      ? Array.from(loadingCitations).some(id => id.startsWith(`${fileId}:`))
      : false

    // Handle Escape key to close popup
    useEffect(() => {
      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape' && onClose) {
          onClose()
        }
      }

      document.addEventListener('keydown', handleKeyDown)
      return () => document.removeEventListener('keydown', handleKeyDown)
    }, [onClose])

    // Scroll to newly loaded chunk when chunks array changes
    useEffect(() => {
      if (chunks && chunks.length > 0 && contentRef.current) {
        const currentChunkIds = new Set(chunks.map(c => c.chunk_index.toString()))

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
          borderRadius: isFullscreen ? '0' : 'var(--radius-md)',
          boxShadow: 'var(--shadow)',
          width: isFullscreen ? '100vw' : 'auto',
          maxWidth: isFullscreen ? '800px' : undefined,
          height: isFullscreen ? '100vh' : 'auto',
          top: isFullscreen ? 0 : undefined,
          left: isFullscreen ? '50%' : undefined,
          right: isFullscreen ? undefined : undefined,
          bottom: isFullscreen ? 0 : undefined,
          transform: isFullscreen ? 'translateX(-50%)' : undefined,
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
            fontSize: 'var(--font-sm)',
            borderRadius: 'var(--radius-md) var(--radius-md) 0 0',
            position: 'relative',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}
        >
          <span>{title}</span>
          {isSticky && (
            <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
              {/* Load All Chunks button */}
              {onLoadAllChunks && fileId && chunks && chunks.length > 0 && (
                <button
                  onClick={() => onLoadAllChunks(fileId)}
                  disabled={isLoadingAllChunks}
                  style={{
                    background: 'rgba(255, 255, 255, 0.2)',
                    border: 'none',
                    color: 'white',
                    borderRadius: 'var(--radius-md)',
                    padding: '4px 8px',
                    cursor: isLoadingAllChunks ? 'default' : 'pointer',
                    fontSize: 'var(--font-xs)',
                    fontWeight: 'normal',
                    transition: 'background-color 0.15s ease',
                    flexShrink: 0,
                    opacity: isLoadingAllChunks ? 0.6 : 1
                  }}
                  onMouseEnter={(e) => {
                    if (!isLoadingAllChunks) {
                      e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.3)'
                    }
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.2)'
                  }}
                  title={t.citation.loadAllChunks}
                >
                  {isLoadingAllChunks ? t.citation.loadingButton : t.citation.loadAllChunks}
                </button>
              )}

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
                    fontSize: 'var(--font-sm)',
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
                  title={isFullscreen ? t.citation.exitFullscreen : t.citation.enterFullscreen}
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
                    fontSize: 'var(--font-base)',
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
                  title={t.citation.close}
                >
                  ×
                </button>
              )}
            </div>
          )}
        </div>
        {isSticky && chunks && fileId ? (
          // Sticky mode with multiple chunks and load buttons
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            height: isFullscreen ? 'calc(100vh - 60px)' : 'calc(100% - 60px)',
            overflow: 'hidden'
          }}>
            {/* Load previous button */}
            {onLoadChunk && chunks && chunks.length > 0 && chunks[0].chunk_index > 0 && (
              <div style={{ padding: '8px 16px', borderBottom: '1px solid #eee', flexShrink: 0 }}>
                <MainLoadButton
                  onClick={() => {
                    const firstChunk = chunks[0]
                    const prevChunkIndex = firstChunk.chunk_index - 1
                    const prevCitationId = `${fileId}:ck${prevChunkIndex}`
                    onLoadChunk(prevCitationId)
                  }}
                  loading={loadingCitations?.has(`${fileId}:ck${chunks[0]?.chunk_index - 1}`)}
                >
                  {t.citation.loadPrevious}
                </MainLoadButton>
              </div>
            )}

            {/* Chunks content */}
            <div
              ref={contentRef}
              style={{
                padding: '16px',
                maxHeight: isFullscreen ? 'calc(100vh - 120px)' : undefined,
                height: isFullscreen ? undefined : 'auto',
                overflowY: 'auto',
                fontSize: 'var(--font-sm)',
                lineHeight: 1.6,
                color: '#333',
                scrollbarWidth: 'thin',
                scrollbarColor: '#3498db transparent',
                flex: isFullscreen ? 1 : 1
              }}
              className="citation-popup-content"
            >
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
                        color: '#666',
                        marginBottom: '4px',
                        fontWeight: chunk.chunk_index === currentChunkIndex ? 'bold' : 'normal',
                        background: '#e3f2fd',
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
                              color: '#1976d2',
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
                                  fontSize: 'var(--font-lg)',
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
                                    {t.citation.loadChunk} {firstMissingIndex}
                                  </MainLoadButton>
                                </div>
                                <div style={{
                                  fontSize: 'var(--font-lg)',
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
                                    {t.citation.loadChunkUp} {firstMissingIndex}
                                  </MainLoadButton>
                                </div>
                                <div style={{
                                  fontSize: 'var(--font-lg)',
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
                                    {t.citation.loadChunkDown} {lastMissingIndex}
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
            {onLoadChunk && chunks && chunks.length > 0 && chunks[chunks.length - 1].chunk_index < chunks[chunks.length - 1].total_chunks - 1 && (
              <div style={{ padding: '8px 16px', borderTop: '1px solid #eee', flexShrink: 0 }}>
                <MainLoadButton
                  onClick={() => {
                    const lastChunk = chunks[chunks.length - 1]
                    const nextChunkIndex = lastChunk.chunk_index + 1
                    const nextCitationId = `${fileId}:ck${nextChunkIndex}`
                    onLoadChunk(nextCitationId)
                  }}
                  loading={loadingCitations?.has(`${fileId}:ck${chunks[chunks.length - 1]?.chunk_index + 1}`)}
                >
                  {t.citation.loadNext}
                </MainLoadButton>
              </div>
            )}
          </div>
        ) : (
          // Non-sticky mode with single content
          <div
            style={{
              padding: '16px',
              height: 'calc(100% - 60px)',
              overflowY: 'auto',
              fontSize: 'var(--font-sm)',
              lineHeight: 1.6,
              color: '#333',
              whiteSpace: 'pre-wrap',
              scrollbarWidth: 'thin',
              scrollbarColor: '#3498db transparent',
              boxSizing: 'border-box'
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

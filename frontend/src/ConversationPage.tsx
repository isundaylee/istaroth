import { useState, useEffect } from 'react'
import { Link, useLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import html2canvas from 'html2canvas'
import { useT } from './contexts/LanguageContext'
import QueryForm from './QueryForm'
import Card from './components/Card'
import Navigation from './components/Navigation'
import CitationRenderer from './components/CitationRenderer'
import type { ConversationResponse } from './types/api'

interface LoaderData {
  conversation: ConversationResponse
}

export async function conversationPageLoader({ params }: LoaderFunctionArgs): Promise<LoaderData> {
  const { id } = params
  if (!id) {
    throw new Response('Invalid conversation ID', { status: 400 })
  }

  const res = await fetch(`/api/conversations/${id}`)
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}))
    throw new Response(errorData.error || 'Failed to load conversation', { status: res.status })
  }

  const conversationData = (await res.json()) as ConversationResponse
  return { conversation: conversationData }
}

function ConversationPage() {
  const t = useT()
  const { conversation } = useLoaderData() as LoaderData
  const [exporting, setExporting] = useState(false)
  const [exportedImage, setExportedImage] = useState<string | null>(null)
  const [copyButtonText, setCopyButtonText] = useState('')

  useEffect(() => {
    setCopyButtonText(t('conversation.shareLink'))
  }, [t])

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const copyCurrentUrl = () => {
    navigator.clipboard.writeText(window.location.href).then(() => {
      setCopyButtonText(t('common.copied'))
      setTimeout(() => setCopyButtonText(t('conversation.shareLink')), 2000)
    }).catch(() => {
      setCopyButtonText(t('common.copyFailed'))
      setTimeout(() => setCopyButtonText(t('conversation.shareLink')), 2000)
    })
  }

  const exportPageAsPNG = async () => {
    setExporting(true)

    try {
      const element = document.querySelector('.conversation-content') as HTMLElement
      if (!element) {
        throw new Error(t('conversation.errors.notFound'))
      }

      const canvas = await html2canvas(element, {
        useCORS: true,
        scale: 2,
        scrollX: 0,
        scrollY: 0,
        backgroundColor: '#f5f5f5',
        x: -20,
        y: -20,
        width: element.scrollWidth + 40,
        height: element.scrollHeight + 40
      } as any)

      const dataURL = canvas.toDataURL()
      setExportedImage(dataURL)
    } catch (error) {
      console.error('导出PNG失败:', error)
      alert(t('conversation.errors.exportFailed'))
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="app">
      <Navigation />
      <main className="main">

        <QueryForm currentQuestion={conversation.question} />

        <div className="conversation-content">
          <Card borderColor="green">
            <h3>
              {t('conversation.question')}: <span style={{ fontWeight: 'normal' }}>{conversation.question}</span>
            </h3>
          </Card>

          <Card borderColor="blue">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <h3>{t('conversation.answer')}:</h3>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button onClick={copyCurrentUrl} className="share-button">
                  {copyButtonText}
                </button>
                <button
                  onClick={exportPageAsPNG}
                  className="export-button"
                  disabled={exporting}
                >
                  {exporting ? t('conversation.exporting') : t('conversation.export')}
                </button>
              </div>
            </div>

            {exportedImage && (
              <div style={{
                marginTop: '1rem',
                marginBottom: '1rem',
                display: 'flex',
                justifyContent: 'center'
              }}>
                <div style={{
                  border: '1px solid #ddd',
                  borderRadius: '4px',
                  padding: '1rem',
                  backgroundColor: 'white',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
                  display: 'inline-block',
                  textAlign: 'center'
                }}>
                  <img
                    src={exportedImage}
                    alt={t('conversation.exportImage.alt')}
                    style={{
                      width: '50vw',
                      maxWidth: '400px',
                      height: 'auto',
                      borderRadius: '4px',
                      display: 'block',
                      marginBottom: '0.75rem'
                    }}
                  />
                  <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'center' }}>
                    <button
                      onClick={() => {
                        const link = document.createElement('a')
                        link.download = `istaroth-conversation-${conversation.uuid}-${Date.now()}.png`
                        link.href = exportedImage
                        link.click()
                      }}
                      className="share-button"
                      style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem' }}
                    >
                      {t('common.download')}
                    </button>
                    <button
                      onClick={() => setExportedImage(null)}
                      className="export-button"
                      style={{ fontSize: '0.8rem', padding: '0.25rem 0.5rem' }}
                    >
                      {t('common.close')}
                    </button>
                  </div>
                </div>
              </div>
            )}

            <div className="answer">
              <CitationRenderer content={conversation.answer} />
            </div>
          </Card>

          <div className="conversation-footer">
            <div className="conversation-meta">
              <p>{t('conversation.metadata.conversation')} #{conversation.uuid}</p>
              <p>{t('conversation.metadata.time')}: {formatDate(conversation.created_at)}</p>
              <p>{t('conversation.metadata.language')}: {conversation.language}</p>
              <p>{t('conversation.metadata.model')}: {conversation.model}</p>
              {conversation.generation_time_seconds && <p>{t('conversation.metadata.generationTime')}: {conversation.generation_time_seconds.toFixed(2)}{t('conversation.metadata.seconds')}</p>}
            </div>
            <Link to="/" className="back-link">
              ← {t('common.back')}
            </Link>
          </div>
        </div>
      </main>
    </div>
  )
}

export default ConversationPage

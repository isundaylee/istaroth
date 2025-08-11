import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import html2canvas from 'html2canvas'
import { useT, useTranslation } from './contexts/LanguageContext'
import QueryForm from './QueryForm'
import Card from './components/Card'
import LanguageSwitcher from './components/LanguageSwitcher'

interface ConversationResponse {
  uuid: string
  question: string
  answer: string
  model: string | null
  k: number
  created_at: number
  generation_time_seconds: number | null
}

interface ErrorResponse {
  error: string
}

function ConversationPage() {
  const { id } = useParams<{ id: string }>()
  const { language } = useTranslation()
  const t = useT()
  const [conversation, setConversation] = useState<ConversationResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [exportedImage, setExportedImage] = useState<string | null>(null)
  const [copyButtonText, setCopyButtonText] = useState('')

  useEffect(() => {
    setCopyButtonText(t('conversation.shareLink'))
  }, [t])

  useEffect(() => {
    const fetchConversation = async () => {
      if (!id) {
        setError(t('conversation.errors.invalidId'))
        setLoading(false)
        return
      }

      try {
        const res = await fetch(`/api/conversations/${id}`)
        const data = await res.json()

        if (res.ok) {
          const conversationData = data as ConversationResponse
          if (!conversationData) {
            throw new Error(t('conversation.errors.emptyData'))
          }
          setConversation(conversationData)
        } else {
          const errorData = data as ErrorResponse
          setError(errorData.error || t('conversation.errors.loadFailed'))
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : t('query.errors.noConnection'))
      } finally {
        setLoading(false)
      }
    }

    fetchConversation()
  }, [id])

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
    if (!conversation) return

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

  if (loading) {
    return (
      <div className="app">
        <main className="main">
          <div className="loading">{t('common.loading')}</div>
        </main>
      </div>
    )
  }

  if (error) {
    return (
      <div className="app">
        <main className="main">
          <div className="error">
            <h3>{t('common.error')}</h3>
            <p>{error}</p>
            <Link to="/" className="back-link">
              {t('common.back')}
            </Link>
          </div>
        </main>
      </div>
    )
  }


  return (
    <div className="app">
      <main className="main">
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          padding: '0.5rem 0 1rem 0'
        }}>
          <LanguageSwitcher />
        </div>

        <QueryForm />

        <div className="conversation-content">
          <Card borderColor="green">
            <h3>
              {t('conversation.question')}: <span style={{ fontWeight: 'normal' }}>{conversation!.question}</span>
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
                        link.download = `istaroth-conversation-${conversation!.uuid}-${Date.now()}.png`
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
              <ReactMarkdown>{conversation!.answer}</ReactMarkdown>
            </div>
          </Card>

          <div className="conversation-footer">
            <div className="conversation-meta">
              <p>{t('conversation.metadata.conversation')} #{conversation!.uuid}</p>
              <p>{t('conversation.metadata.time')}: {formatDate(conversation!.created_at)}</p>
              <p>{t('conversation.metadata.model')}: {conversation!.model}</p>
              {conversation!.generation_time_seconds && <p>{t('conversation.metadata.generationTime')}: {conversation!.generation_time_seconds.toFixed(2)}{t('conversation.metadata.seconds')}</p>}
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

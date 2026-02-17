import { useState, useEffect } from 'react'
import { useLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import html2canvas from 'html2canvas'
import { useT } from './contexts/LanguageContext'
import { useFooter } from './contexts/FooterContext'
import { translate } from './i18n'
import { getLanguageFromUrl } from './utils/language'
import QueryForm from './QueryForm'
import Card from './components/Card'
import Navigation from './components/Navigation'
import CitationRenderer from './components/CitationRenderer'
import type { ConversationResponse } from './types/api'

interface LoaderData {
  conversation: ConversationResponse
}

export async function conversationPageLoader({ params, request }: LoaderFunctionArgs): Promise<LoaderData> {
  const language = getLanguageFromUrl(request.url)
  const { id } = params
  if (!id) {
    throw new Response(translate(language, 'conversation.errors.invalidId'), { status: 400 })
  }

  const res = await fetch(`/api/conversations/${id}`)
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}))
    throw new Response(errorData.error || translate(language, 'conversation.errors.loadFailed'), { status: res.status })
  }

  const conversationData = (await res.json()) as ConversationResponse
  return { conversation: conversationData }
}

function ConversationPage() {
  const t = useT()
  const { conversation } = useLoaderData() as LoaderData
  const { setExtraContent } = useFooter()
  const [submittingNew, setSubmittingNew] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportedImage, setExportedImage] = useState<string | null>(null)
  const [copyButtonText, setCopyButtonText] = useState('')

  useEffect(() => {
    setSubmittingNew(false)
  }, [conversation])

  useEffect(() => {
    const formatDate = (timestamp: number) =>
      new Date(timestamp * 1000).toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    const content = (
      <>
        {t('conversation.metadata.conversation')} #{conversation.uuid}
        {' · '}
        {formatDate(conversation.created_at)}
        {' · '}
        {conversation.language}
        {' · '}
        {conversation.model}
        {conversation.generation_time_seconds != null && ` · ${conversation.generation_time_seconds.toFixed(2)}${t('conversation.metadata.seconds')}`}
      </>
    )
    setExtraContent(content)
    return () => setExtraContent(null)
  }, [conversation, setExtraContent, t])

  useEffect(() => {
    setCopyButtonText(t('conversation.shareLink'))
  }, [t])

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
    <>
      <Navigation />
      <main className="main">

        <QueryForm currentQuestion={conversation.question} onSubmitStart={() => setSubmittingNew(true)} />

        {!submittingNew &&
        <div className="conversation-content">
          <Card borderColor="green">
            <h3 style={{ margin: 0 }}>{conversation.question}</h3>
          </Card>

          <CitationRenderer content={conversation.answer}>
            {({ answer, citationList }) => (
              <>
                <Card borderColor="blue">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                    <h3>{t('conversation.answer')}</h3>
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
                        borderRadius: 'var(--radius-md)',
                        padding: '1rem',
                        backgroundColor: 'white',
                        boxShadow: 'var(--shadow)',
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
                            borderRadius: 'var(--radius-md)',
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
                            style={{ fontSize: 'var(--font-sm)', padding: '0.25rem 0.5rem' }}
                          >
                            {t('common.download')}
                          </button>
                          <button
                            onClick={() => setExportedImage(null)}
                            className="export-button"
                            style={{ fontSize: 'var(--font-sm)', padding: '0.25rem 0.5rem' }}
                          >
                            {t('common.close')}
                          </button>
                        </div>
                      </div>
                    </div>
                  )}

                  <div className="answer">{answer}</div>
                </Card>

                {citationList && (
                  <div data-citation-container>
                    <Card borderColor="yellow">{citationList}</Card>
                  </div>
                )}
              </>
            )}
          </CitationRenderer>
        </div>}
      </main>
    </>
  )
}

export default ConversationPage

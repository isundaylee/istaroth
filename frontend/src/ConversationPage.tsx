import { useState, useEffect } from 'react'
import { useLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import html2canvas from 'html2canvas'
import { Pencil } from 'lucide-react'
import { useT, useTranslation } from './contexts/LanguageContext'
import { useFooter } from './contexts/FooterContext'
import { translate } from './i18n'
import { LANGUAGE_LOCALES, getLanguageFromUrl } from './utils/language'
import { copyToClipboard } from './utils/clipboard'
import QueryForm from './QueryForm'
import { PageSection } from './components/PageShell'
import Button from './components/Button'
import CitedAnswer from './components/CitedAnswer'
import { MinimizedPopupRegion } from './contexts/PopupCoordinatorContext'
import type { ConversationResponse } from './types/api'
import convStyles from './ConversationPage.module.css'

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
  const locale = LANGUAGE_LOCALES[useTranslation().language]
  const { conversation } = useLoaderData() as LoaderData
  const { setExtraContent } = useFooter()
  const [submittingNew, setSubmittingNew] = useState(false)
  // The new-question composer is collapsed by default; clicking the question
  // title expands it (saves the vertical space when just reading the answer).
  const [editing, setEditing] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportedImage, setExportedImage] = useState<string | null>(null)
  const [copyButtonText, setCopyButtonText] = useState('')

  useEffect(() => {
    setSubmittingNew(false)
    setEditing(false)
  }, [conversation])

  useEffect(() => {
    if (submittingNew) {
      setExtraContent(null)
      return
    }
    const formatDate = (timestamp: number) =>
      new Date(timestamp * 1000).toLocaleString(locale, {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    const numberFormatter = new Intl.NumberFormat()
    const content = (
      <>
        {t('conversation.metadata.conversation')} {conversation.short_slug}
        {' · '}
        {formatDate(conversation.created_at)}
        {' · '}
        {conversation.language}
        {' · '}
        {conversation.model}
        {conversation.generation_time_seconds != null && ` · ${conversation.generation_time_seconds.toFixed(2)}${t('conversation.metadata.seconds')}`}
        {conversation.final_generation_input_text_length > 0 && ` · ${numberFormatter.format(conversation.final_generation_input_text_length)} ${t('conversation.metadata.inputChars')}`}
        {conversation.retrieval_unique_chunk_count > 0 && ` · ${numberFormatter.format(conversation.retrieval_unique_chunk_count)} ${t('conversation.metadata.chunks')}`}
        {conversation.retrieval_unique_file_count > 0 && ` · ${numberFormatter.format(conversation.retrieval_unique_file_count)} ${t('conversation.metadata.files')}`}
      </>
    )
    setExtraContent(content)
    return () => setExtraContent(null)
  }, [conversation, setExtraContent, t, locale, submittingNew])

  useEffect(() => {
    setCopyButtonText(t('conversation.shareLink'))
  }, [t])

  const copyCurrentUrl = () => {
    const shortUrl = `${window.location.origin}/s/${conversation.short_slug}`
    copyToClipboard(shortUrl).then(() => {
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
      const element = document.querySelector(`.${CSS.escape(convStyles.content)}`) as HTMLElement
      if (!element) {
        throw new Error(t('conversation.errors.notFound'))
      }

      const canvas = await html2canvas(element, {
        useCORS: true,
        scale: 2,
        scrollX: 0,
        scrollY: 0,
        backgroundColor: getComputedStyle(document.documentElement).getPropertyValue('--color-bg').trim(),
        x: -20,
        y: -20,
        width: element.getBoundingClientRect().width + 40,
        height: element.scrollHeight + 40
      } as any)

      const dataURL = canvas.toDataURL()
      setExportedImage(dataURL)
    } catch (error) {
      console.error('PNG export failed:', error)
      alert(t('conversation.errors.exportFailed'))
    } finally {
      setExporting(false)
    }
  }

  return (
    <>
      <PageSection>
        {editing ? (
          <div onKeyDown={(e) => { if (e.key === 'Escape') setEditing(false) }}>
            <QueryForm key={conversation.uuid} currentQuestion={conversation.question} onSubmitStart={() => setSubmittingNew(true)} />
          </div>
        ) : (
          <button type="button" className={convStyles.askTrigger} onClick={() => setEditing(true)} title={t('conversation.askAnother')}>
            <span className={convStyles.askTriggerTitle}>{conversation.question}</span>
            <span className={convStyles.askTriggerHint}>
              <Pencil size={14} aria-hidden />
              {t('conversation.askAnother')}
            </span>
          </button>
        )}
      </PageSection>

        {!submittingNew &&
        <MinimizedPopupRegion className={convStyles.content} data-conversation-content>
          <CitedAnswer content={conversation.answer} properNouns={conversation.proper_nouns}>
            {({ answer, citationList }) => (
              <>
                <PageSection>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                    <h3>{t('conversation.answer')}</h3>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      <Button onClick={copyCurrentUrl} variant="secondary">
                        {copyButtonText}
                      </Button>
                      <Button
                        onClick={exportPageAsPNG}
                        variant="secondary"
                        disabled={exporting}
                      >
                        {exporting ? t('conversation.exporting') : t('conversation.export')}
                      </Button>
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
                        border: '1px solid var(--color-border)',
                        borderRadius: 'var(--radius-md)',
                        padding: '1rem',
                        backgroundColor: 'var(--color-surface)',
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
                          <Button
                            variant="secondary"
                            onClick={() => {
                              const link = document.createElement('a')
                              link.download = `istaroth-conversation-${conversation.short_slug}-${Date.now()}.png`
                              link.href = exportedImage
                              link.click()
                            }}
                          >
                            {t('common.download')}
                          </Button>
                          <Button
                            variant="secondary"
                            onClick={() => setExportedImage(null)}
                          >
                            {t('common.close')}
                          </Button>
                        </div>
                      </div>
                    </div>
                  )}

                  {answer}
                </PageSection>

                {citationList && (
                  <div data-citation-container>
                    <PageSection>{citationList}</PageSection>
                  </div>
                )}
              </>
            )}
          </CitedAnswer>
        </MinimizedPopupRegion>}
    </>
  )
}

export default ConversationPage

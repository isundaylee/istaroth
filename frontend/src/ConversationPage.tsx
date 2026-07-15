import { useState, useEffect } from 'react'
import { useLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import html2canvas from 'html2canvas'
import { ImageDown, Pencil } from 'lucide-react'
import { useT, useTranslation } from './contexts/LanguageContext'
import { useErrorToast } from './contexts/ErrorToastContext'
import { useFooter } from './contexts/FooterContext'
import { useQueryStream } from './hooks/useQueryStream'
import { translate } from './i18n'
import { LANGUAGE_LOCALES, getLanguageFromUrl } from './utils/language'
import QueryForm from './QueryForm'
import { PageSection } from './components/PageShell'
import Button from './components/Button'
import ShareLinkButton from './components/ShareLinkButton'
import ConversationAnswer from './components/ConversationAnswer'
import conversationAnswerStyles from './components/ConversationAnswer.module.css'
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
  const showError = useErrorToast()
  const locale = LANGUAGE_LOCALES[useTranslation().language]
  const { conversation } = useLoaderData() as LoaderData
  const { setExtraContent } = useFooter()
  // The re-ask stream lives here (not in QueryForm), so collapsing the composer
  // — Escape / clicking away — never unmounts or freezes an in-flight stream.
  const { activeSteps, streamedAnswer, streaming, loading, submit, reset } = useQueryStream()
  // A re-ask is in flight: hide the saved answer/footer while a new one
  // generates. Derived from the hook's ``loading`` so it can never stay stuck
  // true after an error (the hook resets ``loading`` to false), which would
  // otherwise leave the content region permanently blank.
  const submittingNew = loading
  // The new-question composer is collapsed by default; clicking the question
  // title expands it (saves the vertical space when just reading the answer).
  const [editing, setEditing] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [exportedImage, setExportedImage] = useState<string | null>(null)

  useEffect(() => {
    setEditing(false)
    // A conversation-to-conversation re-ask only changes the route param, so
    // this component instance survives the post-``done`` navigation. Clear the
    // stream state (including ``loading``) once the new conversation's loader
    // data lands, or the composer stays stuck in the answering state.
    reset()
  }, [conversation, reset])

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

  const exportPageAsPNG = async () => {
    setExporting(true)

    try {
      const element = document.querySelector(`.${CSS.escape(conversationAnswerStyles.content)}`) as HTMLElement
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
      showError(t('conversation.errors.exportFailed'))
    } finally {
      setExporting(false)
    }
  }

  return (
    <>
      <PageSection>
        {editing ? (
          <div onKeyDown={(e) => { if (e.key === 'Escape') setEditing(false) }}>
            {/* Steps are pre-generation only: hidden once answer text is
                streaming so the indicator never sits next to the visibly
                growing answer (nor reappears on a late step_start). */}
            <QueryForm
              key={conversation.uuid}
              currentQuestion={conversation.question}
              submit={submit}
              loading={loading}
              activeSteps={activeSteps}
              hideProgress={streaming}
            />
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

        {streaming ? (
          // In-flight re-ask: stream the growing answer in the content region
          // instead of blanking it. Share/export/footer are suppressed until the
          // conversation is saved (on `done` we navigate to the real page).
          <ConversationAnswer answer={streamedAnswer} properNouns={[]} />
        ) : (!submittingNew &&
          <ConversationAnswer
            answer={conversation.answer}
            properNouns={conversation.proper_nouns}
            actions={
              <>
                <ShareLinkButton getUrl={() => Promise.resolve(`${window.location.origin}/s/${conversation.short_slug}`)} />
                <Button
                  onClick={exportPageAsPNG}
                  variant="icon"
                  size="sm"
                  disabled={exporting}
                  title={exporting ? t('conversation.exporting') : t('conversation.export')}
                  aria-label={exporting ? t('conversation.exporting') : t('conversation.export')}
                >
                  <ImageDown aria-hidden />
                </Button>
              </>
            }
            exportImage={exportedImage && (
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
          />
        )}
    </>
  )
}

export default ConversationPage

import { useState, useEffect, useRef } from 'react'
import { useT, useTranslation } from './contexts/LanguageContext'
import { useAppNavigate } from './hooks/useAppNavigate'
import Select from './components/Select'
import Button from './components/Button'
import ErrorDisplay from './components/ErrorDisplay'
import { readNdjsonStream } from './utils/ndjson'
import { getClientId } from './utils/clientId'
import type { QueryRequest, ErrorResponse, ModelsResponse, ExampleQuestionResponse, ProgressMessage, ProgressStepStart } from './types/api'

interface QueryFormProps {
  currentQuestion?: string
  onSubmitStart?: () => void
}

const retrievalPresets = {
  fast: { k: 4, chunk_context: 1 },
  balanced: { k: 7, chunk_context: 2 },
  thorough: { k: 10, chunk_context: 5 },
} as const

type RetrievalPreset = keyof typeof retrievalPresets

const resizeTextarea = (textarea: HTMLTextAreaElement) => {
  textarea.style.height = 'auto'
  textarea.style.height = `${textarea.scrollHeight}px`
}

function QueryForm({ currentQuestion, onSubmitStart }: QueryFormProps = {}) {
  const navigate = useAppNavigate()
  const t = useT()
  const { language } = useTranslation()
  const [question, setQuestion] = useState('')
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [selectedModel, setSelectedModel] = useState('')
  const [retrievalPreset, setRetrievalPreset] = useState<RetrievalPreset>('balanced')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  // Pipeline steps that have started but not yet ended, in start order.
  const [activeSteps, setActiveSteps] = useState<ProgressStepStart[]>([])
  const [modelsLoading, setModelsLoading] = useState(true)
  const [exampleQuestion, setExampleQuestion] = useState<string>('')
  const [exampleLoading, setExampleLoading] = useState(true)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Helper function to convert model ID to translation key
  const getModelTranslationKey = (modelId: string) => {
    return modelId.replace(/\./g, '_')
  }

  // Helper function to get model display text
  const getModelText = (modelId: string) => {
    const translationKey = `query.models.${getModelTranslationKey(modelId)}`
    return t(translationKey)
  }

  useEffect(() => {
    // Focus the input field when component mounts
    if (inputRef.current) {
      inputRef.current.focus()
      resizeTextarea(inputRef.current)
    }
  }, [])

  useEffect(() => {
    if (inputRef.current) resizeTextarea(inputRef.current)
  }, [question])

  useEffect(() => {
    // Use current question if provided, otherwise fetch example question
    if (currentQuestion) {
      setExampleQuestion(currentQuestion)
      setExampleLoading(false)
      return
    }

    // Fetch example question when component mounts or language changes
    const fetchExampleQuestion = async () => {
      try {
        setExampleLoading(true)
        const res = await fetch(`/api/example-question?language=${language.toUpperCase()}`)
        if (res.ok) {
          const data = await res.json() as ExampleQuestionResponse
          setExampleQuestion(data.question)
        } else {
          console.error('Failed to fetch example question from server')
          // Don't set error state as this is not critical
        }
      } catch (err) {
        console.error('Error fetching example question:', err)
        // Don't set error state as this is not critical
      } finally {
        setExampleLoading(false)
      }
    }

    fetchExampleQuestion()
  }, [language, currentQuestion])

  useEffect(() => {
    // Fetch available models from backend
    const fetchModels = async () => {
      try {
        const res = await fetch('/api/models')
        if (res.ok) {
          const data = await res.json() as ModelsResponse
          setAvailableModels(data.models)
          // Pre-select the backend-provided default
          if (data.models.length > 0) {
            setSelectedModel(data.default)
          }
        } else {
          console.error('Failed to fetch models from server')
          setError(t('query.errors.modelsLoadFailed'))
        }
      } catch (err) {
        console.error('Error fetching models:', err)
        setError(t('query.errors.modelsLoadFailed'))
      } finally {
        setModelsLoading(false)
      }
    }

    fetchModels()
  }, [])

  // Reset loading state when the question prop changes (e.g. after navigating to a new conversation)
  useEffect(() => {
    setLoading(false)
    setActiveSteps([])
  }, [currentQuestion])

  // Human-readable label for an in-flight pipeline step.
  const stepLabel = (step: ProgressStepStart) => {
    if (step.kind === 'searching') {
      return `${t('query.progress.searching')} “${step.detail ?? ''}”`
    }
    return t(`query.progress.${step.kind}`)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // Use example question if user didn't enter anything
    const questionToSubmit = question.trim() || exampleQuestion
    if (!questionToSubmit) return

    setLoading(true)
    setError(null)
    setActiveSteps([])
    onSubmitStart?.()

    try {
      const retrievalParams = retrievalPresets[retrievalPreset]
      const req_body: QueryRequest = {
        language: language.toUpperCase(),
        question: questionToSubmit,
        model: selectedModel,
        k: retrievalParams.k,
        chunk_context: retrievalParams.chunk_context,
        client_id: getClientId(),
      }
      const res = await fetch('/api/query/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(req_body),
      })

      if (!res.ok || !res.body) {
        const errorData = await res.json().catch(() => null) as ErrorResponse | null
        setError(errorData?.error || t('query.errors.unknown'))
        setLoading(false)
        return
      }

      // Consume the progress events as they arrive.
      let settled = false
      for await (const event of readNdjsonStream<ProgressMessage>(res.body)) {
        if (event.type === 'step_start') {
          setActiveSteps((prev) => [...prev, event])
        } else if (event.type === 'step_end') {
          setActiveSteps((prev) => prev.filter((s) => s.id !== event.id))
        } else if (event.type === 'done') {
          // Don't reset loading here — the dots animation stays visible until the
          // component unmounts (front page) or currentQuestion changes (conversation page).
          settled = true
          setQuestion('')
          navigate(`/conversation/${event.result.conversation_uuid}`)
        } else {
          settled = true
          setError(event.error || t('query.errors.unknown'))
          setLoading(false)
        }
      }

      // Stream closed without a terminal event (e.g. dropped connection).
      if (!settled) {
        setError(t('query.errors.noConnection'))
        setLoading(false)
      }
    } catch (err) {
      setError(t('query.errors.noConnection'))
      setLoading(false)
    }
  }

  return (
    <>
      <form onSubmit={handleSubmit} className="query-form">
        <div className="query-composer">
          <textarea
            ref={inputRef}
            value={question}
            onChange={(e) => {
              setQuestion(e.target.value)
              resizeTextarea(e.target)
            }}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault()
                e.currentTarget.form?.requestSubmit()
              }
            }}
            placeholder={exampleLoading ? t('query.exampleLoading') : exampleQuestion || t('query.placeholder')}
            disabled={loading}
            className="query-textarea"
            rows={2}
          />
          <div className="query-composer-footer">
            <div className="query-options-row">
              <Select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                disabled={loading || modelsLoading}
                className="model-select"
              >
                {modelsLoading ? (
                  <option value="">{t('common.loading')}</option>
                ) : (
                  availableModels.map(modelId => (
                    <option key={modelId} value={modelId}>
                      {getModelText(modelId)}
                    </option>
                  ))
                )}
              </Select>
              <Select
                value={retrievalPreset}
                onChange={(e) => setRetrievalPreset(e.target.value as RetrievalPreset)}
                disabled={loading}
                className="retrieval-select"
                aria-label={t('query.retrievalPresetLabel')}
                title={t('query.retrievalPresetLabel')}
              >
                <option value="fast">{t('query.retrievalPresets.fast')}</option>
                <option value="balanced">{t('query.retrievalPresets.balanced')}</option>
                <option value="thorough">{t('query.retrievalPresets.thorough')}</option>
              </Select>
            </div>
            <Button
              type="submit"
              className="query-submit-button"
              disabled={loading || (!question.trim() && !exampleQuestion) || availableModels.length === 0}
            >
              <span className="button-text-sizer">
                <span className={loading ? 'button-text-active' : 'button-text-hidden'}><span className="loading-ellipsis">{t('query.submitting')}</span></span>
                <span className={loading ? 'button-text-hidden' : 'button-text-active'}>{t('query.submitButton')}</span>
              </span>
            </Button>
          </div>
        </div>
      </form>

      {loading && activeSteps.length > 0 && (
        <ul className="query-progress">
          {activeSteps.map((step) => (
            <li key={step.id} className="query-progress-item">
              <span className="loading-ellipsis">{stepLabel(step)}</span>
            </li>
          ))}
        </ul>
      )}

      {error && <ErrorDisplay error={error} />}
    </>
  )
}

export default QueryForm

import { useState, useEffect } from 'react'
import { useT, useTranslation } from './contexts/LanguageContext'
import { useAppNavigate } from './hooks/useAppNavigate'
import Select from './components/Select'
import Button from './components/Button'
import Composer from './components/Composer'
import ErrorDisplay from './components/ErrorDisplay'
import QueryProgress from './components/QueryProgress'
import { getClientId } from './utils/clientId'
import { consumeQueryStream } from './utils/queryStream'
import type { QueryRequest, ErrorResponse, ModelsResponse, ExampleQuestionResponse, ProgressStepStart } from './types/api'
import styles from './QueryForm.module.css'
import queryProgressStyles from './components/QueryProgress.module.css'

interface QueryFormProps {
  currentQuestion?: string
  onSubmitStart?: () => void
}

const retrievalPresets = {
  fast: 12,
  balanced: 35,
  thorough: 110,
} as const

type RetrievalPreset = keyof typeof retrievalPresets

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

  // Helper function to convert model ID to translation key
  const getModelTranslationKey = (modelId: string) => {
    return modelId.replace(/[./]/g, '_')
  }

  // Helper function to get model display text
  const getModelText = (modelId: string) => {
    const translationKey = `query.models.${getModelTranslationKey(modelId)}`
    return t(translationKey)
  }

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

  const handleSubmit = async () => {
    // Use example question if user didn't enter anything
    const questionToSubmit = question.trim() || exampleQuestion
    if (!questionToSubmit) return

    setLoading(true)
    setError(null)
    setActiveSteps([])
    onSubmitStart?.()

    try {
      const req_body: QueryRequest = {
        language: language.toUpperCase(),
        question: questionToSubmit,
        model: selectedModel,
        budget: retrievalPresets[retrievalPreset],
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

      await consumeQueryStream(res.body, {
        onStepStart: (step) => setActiveSteps((prev) => [...prev, step]),
        onStepEnd: (id) => setActiveSteps((prev) => prev.filter((step) => step.id !== id)),
        onDone: (result) => {
          // Don't reset loading here — the dots animation stays visible until the
          // component unmounts (front page) or currentQuestion changes (conversation page).
          setQuestion('')
          navigate(`/conversation/${result.conversation_uuid}`)
        },
        onError: (message) => {
          setError(message)
          setLoading(false)
        },
        noConnectionError: t('query.errors.noConnection'),
        unknownError: t('query.errors.unknown')
      })
    } catch (err) {
      setError(t('query.errors.noConnection'))
      setLoading(false)
    }
  }

  return (
    <>
      <Composer
        value={question}
        onChange={setQuestion}
        onSubmit={handleSubmit}
        placeholder={exampleLoading ? t('query.exampleLoading') : exampleQuestion || t('query.placeholder')}
        disabled={loading}
        controls={
          <div className={styles.optionsRow}>
            <Select
              variant="compact"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              disabled={loading || modelsLoading}
              className={styles.modelSelect}
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
              variant="compact"
              value={retrievalPreset}
              onChange={(e) => setRetrievalPreset(e.target.value as RetrievalPreset)}
              disabled={loading}
              aria-label={t('query.retrievalPresetLabel')}
              title={t('query.retrievalPresetLabel')}
            >
              <option value="fast">{t('query.retrievalPresets.fast')}</option>
              <option value="balanced">{t('query.retrievalPresets.balanced')}</option>
              <option value="thorough">{t('query.retrievalPresets.thorough')}</option>
            </Select>
          </div>
        }
        actions={
          <Button
            type="submit"
            variant="submit"
            disabled={loading || (!question.trim() && !exampleQuestion) || availableModels.length === 0}
          >
            <span className={styles.buttonTextSizer}>
              <span className={loading ? '' : styles.buttonTextHidden}><span className={queryProgressStyles.loadingEllipsis}>{t('query.submitting')}</span></span>
              <span className={loading ? styles.buttonTextHidden : ''}>{t('query.submitButton')}</span>
            </span>
          </Button>
        }
      />

      {loading && activeSteps.length > 0 && (
        <QueryProgress steps={activeSteps} />
      )}

      {error && <ErrorDisplay error={error} />}
    </>
  )
}

export default QueryForm

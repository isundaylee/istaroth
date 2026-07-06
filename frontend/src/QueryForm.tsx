import { useState, useEffect, forwardRef, useImperativeHandle } from 'react'
import { useT, useTranslation } from './contexts/LanguageContext'
import { useErrorToast } from './contexts/ErrorToastContext'
import { useAppNavigate } from './hooks/useAppNavigate'
import Select, { type SelectOption } from './components/Select'
import Button from './components/Button'
import Composer from './components/Composer'
import QueryProgress from './components/QueryProgress'
import { getClientId } from './utils/clientId'
import { consumeQueryStream } from './utils/queryStream'
import type { QueryRequest, ErrorResponse, ModelsResponse, ExampleQuestionResponse, ProgressStepStart } from './types/api'
import styles from './QueryForm.module.css'
import queryProgressStyles from './components/QueryProgress.module.css'

// Imperative handle: lets the home hero's bubble submit the form directly.
export interface QueryFormHandle {
  submit: () => void
}

interface QueryFormProps {
  currentQuestion?: string
  onSubmitStart?: () => void
  // Controlled question text (the home hero's bubble fills it); when omitted
  // the form keeps its own internal state.
  question?: string
  onQuestionChange?: (question: string) => void
  // Observers for the home hero: it mirrors the form's example question,
  // loading flag, and in-flight pipeline steps into the figure/status UI.
  onExampleChange?: (example: string) => void
  onLoadingChange?: (loading: boolean) => void
  onActiveStepsChange?: (steps: ProgressStepStart[]) => void
  // When true the form doesn't render its own <QueryProgress> (the caller
  // displays the steps elsewhere, e.g. over the hero figure).
  hideProgress?: boolean
}

const retrievalPresets = {
  fast: 12,
  balanced: 35,
  thorough: 110,
} as const

type RetrievalPreset = keyof typeof retrievalPresets

const QueryForm = forwardRef<QueryFormHandle, QueryFormProps>(function QueryForm({
  currentQuestion,
  onSubmitStart,
  question: questionProp,
  onQuestionChange,
  onExampleChange,
  onLoadingChange,
  onActiveStepsChange,
  hideProgress = false,
}, ref) {
  const navigate = useAppNavigate()
  const t = useT()
  const { language } = useTranslation()
  const showError = useErrorToast()
  const [internalQuestion, setInternalQuestion] = useState('')
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [selectedModel, setSelectedModel] = useState('')
  const [retrievalPreset, setRetrievalPreset] = useState<RetrievalPreset>('balanced')
  const [loading, setLoading] = useState(false)
  // Pipeline steps that have started but not yet ended, in start order.
  const [activeSteps, setActiveSteps] = useState<ProgressStepStart[]>([])
  const [modelsLoading, setModelsLoading] = useState(true)
  const [exampleQuestion, setExampleQuestion] = useState<string>('')
  const [exampleLoading, setExampleLoading] = useState(true)

  const question = questionProp ?? internalQuestion
  const setQuestion = (value: string) => {
    onQuestionChange?.(value)
    if (questionProp === undefined) setInternalQuestion(value)
  }

  // Model IDs contain `.`/`/` which aren't valid nested-key segments; the i18n
  // keys replace them with `_`.
  const getModelTranslationKey = (modelId: string) => modelId.replace(/[./]/g, '_')

  // The collapsed control shows only the speed; the open dropdown lists speed
  // (label) + full model name (muted detail).
  const modelOptions: SelectOption[] = availableModels.map((modelId) => ({
    value: modelId,
    label: t(`query.models.${getModelTranslationKey(modelId)}.speed`),
    detail: t(`query.models.${getModelTranslationKey(modelId)}.name`),
  }))

  useEffect(() => {
    onExampleChange?.(exampleQuestion)
  }, [exampleQuestion, onExampleChange])

  useEffect(() => {
    onLoadingChange?.(loading)
  }, [loading, onLoadingChange])

  useEffect(() => {
    onActiveStepsChange?.(activeSteps)
  }, [activeSteps, onActiveStepsChange])

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
          showError(t('query.errors.modelsLoadFailed'))
        }
      } catch (err) {
        console.error('Error fetching models:', err)
        showError(t('query.errors.modelsLoadFailed'))
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

  useImperativeHandle(ref, () => ({ submit: handleSubmit }))

  const handleSubmit = async () => {
    // Use example question if user didn't enter anything
    const questionToSubmit = question.trim() || exampleQuestion
    if (!questionToSubmit) return

    setLoading(true)
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
        showError(errorData?.error || t('query.errors.unknown'))
        setLoading(false)
        return
      }

      await consumeQueryStream(res.body, {
        onStepStart: (step) => setActiveSteps((prev) => [...prev, step]),
        onStepEnd: (id) => setActiveSteps((prev) => prev.filter((step) => step.id !== id)),
        onDone: (result) => {
          // Don't reset loading here — the thinking state stays visible until the
          // component unmounts (front page) or currentQuestion changes (conversation page).
          setQuestion('')
          navigate(`/conversation/${result.conversation_uuid}`)
        },
        onError: (message) => {
          showError(message)
          setLoading(false)
        },
        noConnectionError: t('query.errors.noConnection'),
        unknownError: t('query.errors.unknown')
      })
    } catch (err) {
      showError(t('query.errors.noConnection'))
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
              options={modelOptions}
              value={selectedModel}
              onChange={setSelectedModel}
              disabled={loading || modelsLoading}
              placeholder={t('common.loading')}
              ariaLabel={t('query.modelSelectLabel')}
            />
            <Select
              options={[
                { value: 'fast', label: t('query.retrievalPresets.fast') },
                { value: 'balanced', label: t('query.retrievalPresets.balanced') },
                { value: 'thorough', label: t('query.retrievalPresets.thorough') },
              ]}
              value={retrievalPreset}
              onChange={(v) => setRetrievalPreset(v as RetrievalPreset)}
              disabled={loading}
              ariaLabel={t('query.retrievalPresetLabel')}
            />
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

      {!hideProgress && loading && activeSteps.length > 0 && (
        <QueryProgress steps={activeSteps} />
      )}
    </>
  )
})

export default QueryForm

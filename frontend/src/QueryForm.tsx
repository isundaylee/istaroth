import { useState, useEffect, forwardRef, useImperativeHandle } from 'react'
import { useT, useTranslation } from './contexts/LanguageContext'
import { useErrorToast } from './contexts/ErrorToastContext'
import Select, { type SelectOption } from './components/Select'
import Button from './components/Button'
import Composer from './components/Composer'
import QueryProgress from './components/QueryProgress'
import { getClientId } from './utils/clientId'
import type { QueryRequest, ModelsResponse, ExampleQuestionResponse, ProgressStepStart } from './types/api'
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
  // Observer for the home hero: it mirrors the form's example question into the
  // figure's speech bubble.
  onExampleChange?: (example: string) => void
  // The stream is owned by the page (via ``useQueryStream``); the form only
  // builds the request and drives the composer. ``loading`` disables the
  // controls and ``activeSteps`` feeds the form's own progress indicator.
  submit: (request: QueryRequest) => Promise<void>
  loading: boolean
  activeSteps: ProgressStepStart[]
  // When true the form doesn't render its own <QueryProgress> — either the
  // caller displays the steps elsewhere (e.g. over the hero figure), or answer
  // text is streaming and the page swapped to the conversation view.
  hideProgress: boolean
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
  submit,
  loading,
  activeSteps,
  hideProgress,
}, ref) {
  const t = useT()
  const { language } = useTranslation()
  const showError = useErrorToast()
  const [internalQuestion, setInternalQuestion] = useState('')
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [selectedModel, setSelectedModel] = useState('')
  const [retrievalPreset, setRetrievalPreset] = useState<RetrievalPreset>('balanced')
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

  useImperativeHandle(ref, () => ({ submit: handleSubmit }))

  const handleSubmit = async () => {
    // Use example question if user didn't enter anything
    const questionToSubmit = question.trim() || exampleQuestion
    if (!questionToSubmit) return

    // The typed question is intentionally NOT cleared here: a stream/network
    // error leaves it in the composer for retry. On success the page navigates
    // away (front page) or remounts this form (conversation re-ask), so the
    // stale text never lingers.
    onSubmitStart?.()

    await submit({
      language: language.toUpperCase(),
      question: questionToSubmit,
      model: selectedModel,
      budget: retrievalPresets[retrievalPreset],
      client_id: getClientId(),
    })
  }

  return (
    <>
      <Composer
        slashFocusTarget
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

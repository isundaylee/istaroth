import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useT, useTranslation } from './contexts/LanguageContext'
import type { QueryRequest, QueryResponse, ErrorResponse, ModelsResponse, ExampleQuestionResponse } from './types/api'
import ErrorDisplay from './components/ErrorDisplay'

interface QueryFormProps {
  currentQuestion?: string
}

function QueryForm({ currentQuestion }: QueryFormProps = {}) {
  const navigate = useNavigate()
  const t = useT()
  const { language } = useTranslation()
  const [question, setQuestion] = useState('')
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [selectedModel, setSelectedModel] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [modelsLoading, setModelsLoading] = useState(true)
  const [exampleQuestion, setExampleQuestion] = useState<string>('')
  const [exampleLoading, setExampleLoading] = useState(true)
  const inputRef = useRef<HTMLInputElement>(null)

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
    }
  }, [])

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
          // Set default to first model if available
          if (data.models.length > 0) {
            setSelectedModel(data.models[0])
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    // Use example question if user didn't enter anything
    const questionToSubmit = question.trim() || exampleQuestion
    if (!questionToSubmit) return

    setLoading(true)
    setError(null)

    try {
      const req_body: QueryRequest = {
        language: language.toUpperCase(),
        question: questionToSubmit,
        model: selectedModel,
        k: 10,
        chunk_context: 5,
      }
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(req_body),
      })

      const data = await res.json()

      if (res.ok) {
        const response = data as QueryResponse
        // Clear the form and redirect to conversation page
        setQuestion('')
        navigate(`/conversation/${response.conversation_uuid}`)
      } else {
        const errorData = data as ErrorResponse
        setError(errorData.error || t('query.errors.unknown'))
      }
    } catch (err) {
      setError(t('query.errors.noConnection'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <form onSubmit={handleSubmit} className="query-form">
        <div className="input-row">
          <input
            ref={inputRef}
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={exampleLoading ? t('query.exampleLoading') : exampleQuestion || t('query.placeholder')}
            disabled={loading}
            className="question-input"
          />
          <select
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
          </select>
          <button
            type="submit"
            disabled={loading || (!question.trim() && !exampleQuestion) || availableModels.length === 0}
            className="submit-button"
          >
            {loading ? t('query.submitting') : t('query.submitButton')}
          </button>
        </div>
      </form>

      {error && <ErrorDisplay error={error} />}
    </>
  )
}

export default QueryForm

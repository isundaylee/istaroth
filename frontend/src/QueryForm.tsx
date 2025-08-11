import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useT } from './contexts/LanguageContext'

interface QueryResponse {
  question: string
  answer: string
  conversation_id: string
}

interface ErrorResponse {
  error: string
}

function QueryForm() {
  const navigate = useNavigate()
  const t = useT()
  const [question, setQuestion] = useState('')
  const [selectedModel, setSelectedModel] = useState('gemini-2.5-flash-lite')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim()) return

    setLoading(true)
    setError(null)

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: question.trim(),
          k: 10,
          model: selectedModel,
        }),
      })

      const data = await res.json()

      if (res.ok) {
        const response = data as QueryResponse
        // Clear the form and redirect to conversation page
        setQuestion('')
        navigate(`/conversation/${response.conversation_id}`)
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
            placeholder={t('query.placeholder')}
            disabled={loading}
            className="question-input"
          />
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            disabled={loading}
            className="model-select"
          >
            <option value="gemini-2.5-flash-lite">{getModelText('gemini-2.5-flash-lite')}</option>
            <option value="gemini-2.5-flash">{getModelText('gemini-2.5-flash')}</option>
            <option value="gpt-5-nano">{getModelText('gpt-5-nano')}</option>
            <option value="gpt-5-mini">{getModelText('gpt-5-mini')}</option>
            <option value="gemini-2.5-pro">{getModelText('gemini-2.5-pro')}</option>
          </select>
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="submit-button"
          >
            {loading ? t('query.submitting') : t('query.submitButton')}
          </button>
        </div>
      </form>

      {error && (
        <div className="error">
          <h3>{t('common.error')}</h3>
          <p>{error}</p>
        </div>
      )}
    </>
  )
}

export default QueryForm

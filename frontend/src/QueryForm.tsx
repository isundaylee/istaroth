import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

interface QueryResponse {
  question: string
  answer: string
  conversation_id: number
}

interface ErrorResponse {
  error: string
}

interface QueryFormProps {
  onTitleFadeOut?: () => void
}

function QueryForm({ onTitleFadeOut }: QueryFormProps) {
  const navigate = useNavigate()
  const [question, setQuestion] = useState('')
  const [selectedModel, setSelectedModel] = useState('gemini-2.5-flash-lite')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    // Focus the input field when component mounts
    if (inputRef.current) {
      inputRef.current.focus()
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim()) return

    // Trigger title fade out on first query (only on home page)
    if (onTitleFadeOut) {
      onTitleFadeOut()
    }

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
        setError(errorData.error || '发生了未知错误')
      }
    } catch (err) {
      setError('无法连接到服务器')
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
            placeholder="请输入关于原神背景故事的问题..."
            disabled={loading}
            className="question-input"
          />
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            disabled={loading}
            className="model-select"
          >
            <option value="gemini-2.5-flash-lite">超快速 (gemini-2.5-flash-lite)</option>
            <option value="gemini-2.5-flash">快速 (gemini-2.5-flash)</option>
            <option value="gpt-5-nano">快速 (gpt-5-nano)</option>
            <option value="gpt-5-mini">中速 (gpt-5-mini)</option>
            <option value="gemini-2.5-pro">慢速 (gemini-2.5-pro)</option>
          </select>
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="submit-button"
          >
            {loading ? '回答中...' : '提问'}
          </button>
        </div>
      </form>

      {error && (
        <div className="error">
          <h3>错误</h3>
          <p>{error}</p>
        </div>
      )}
    </>
  )
}

export default QueryForm

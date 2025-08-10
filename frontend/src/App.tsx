import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'

interface QueryResponse {
  question: string
  answer: string
}

interface ErrorResponse {
  error: string
}

function App() {
  const [question, setQuestion] = useState('')
  const [response, setResponse] = useState<QueryResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [titleFadeOut, setTitleFadeOut] = useState(false)
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

    // Hide the title when user submits their first query
    if (!titleFadeOut) {
      setTitleFadeOut(true)
    }

    setLoading(true)
    setError(null)
    setResponse(null)

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: question.trim(),
          k: 10,
        }),
      })

      const data = await res.json()

      if (res.ok) {
        setResponse(data as QueryResponse)
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
    <div className="app">
      <main className="main">
        <form onSubmit={handleSubmit} className="query-form">
          <div className="input-group">
            <input
              ref={inputRef}
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="请输入关于原神背景故事的问题..."
              disabled={loading}
              className="question-input"
            />
            <button
              type="submit"
              disabled={loading || !question.trim()}
              className="submit-button"
            >
              {loading ? '回答中...' : '提问'}
            </button>
          </div>
        </form>

        <header className={`header${titleFadeOut ? ' fade-out' : ''}`}>
          <h1>伊斯塔露</h1>
          <img src="/istaroth-logo.png" alt="Istaroth Logo" className="logo" />
        </header>

        {error && (
          <div className="error">
            <h3>错误</h3>
            <p>{error}</p>
          </div>
        )}

        {response && (
          <div className="response">
            <h3>回答</h3>
            <div className="answer">
              <ReactMarkdown>{response.answer}</ReactMarkdown>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default App

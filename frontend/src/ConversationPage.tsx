import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'

interface ConversationResponse {
  id: number
  question: string
  answer: string
  model: string | null
  k: number
  created_at: number
}

interface ErrorResponse {
  error: string
}

function ConversationPage() {
  const { id } = useParams<{ id: string }>()
  const [conversation, setConversation] = useState<ConversationResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchConversation = async () => {
      if (!id) {
        setError('无效的对话ID')
        setLoading(false)
        return
      }

      try {
        const res = await fetch(`/api/conversations/${id}`)
        const data = await res.json()

        if (res.ok) {
          const conversationData = data as ConversationResponse
          if (!conversationData) {
            throw new Error('服务器返回了空的对话数据')
          }
          setConversation(conversationData)
        } else {
          const errorData = data as ErrorResponse
          setError(errorData.error || '无法加载对话')
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : '无法连接到服务器')
      } finally {
        setLoading(false)
      }
    }

    fetchConversation()
  }, [id])

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const copyCurrentUrl = () => {
    navigator.clipboard.writeText(window.location.href).then(() => {
      alert('链接已复制到剪贴板!')
    }).catch(() => {
      alert('复制失败，请手动复制链接')
    })
  }

  if (loading) {
    return (
      <div className="app">
        <main className="main">
          <div className="loading">加载中...</div>
        </main>
      </div>
    )
  }

  if (error) {
    return (
      <div className="app">
        <main className="main">
          <div className="error">
            <h3>错误</h3>
            <p>{error}</p>
            <Link to="/" className="back-link">
              返回首页
            </Link>
          </div>
        </main>
      </div>
    )
  }


  return (
    <div className="app">
      <main className="main">
        <div className="conversation-header">
          <Link to="/" className="back-link">
            ← 返回首页
          </Link>
        </div>

        <div className="conversation-content">
          <div className="question-section">
            <h3>问题: <span style={{fontWeight: 'normal'}}>{conversation.question}</span></h3>
          </div>

          <div className="answer-section">
            <div className="answer-header">
              <h3>回答:</h3>
              <button onClick={copyCurrentUrl} className="share-button">
                复制分享链接
              </button>
            </div>
            <div className="answer">
              <ReactMarkdown>{conversation.answer}</ReactMarkdown>
            </div>
          </div>

          <div className="conversation-meta">
            <p>对话 #{conversation.id}</p>
            <p>时间: {formatDate(conversation.created_at)}</p>
            {conversation.model && <p>模型: {conversation.model}</p>}
          </div>
        </div>
      </main>
    </div>
  )
}

export default ConversationPage

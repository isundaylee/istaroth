import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import html2canvas from 'html2canvas'
import QueryForm from './QueryForm'
import Card from './components/Card'

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
  const [exporting, setExporting] = useState(false)

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

  const exportPageAsPNG = async () => {
    if (!conversation) return

    setExporting(true)

    try {
      const element = document.querySelector('.conversation-content') as HTMLElement
      if (!element) {
        throw new Error('对话内容元素未找到')
      }

      const canvas = await html2canvas(element, {
        useCORS: true,
        scale: 2,
        scrollX: 0,
        scrollY: 0,
        backgroundColor: '#f5f5f5',
        x: -20,
        y: -20,
        width: element.scrollWidth + 40,
        height: element.scrollHeight + 40
      } as any)

      const link = document.createElement('a')
      link.download = `istaroth-conversation-${conversation.id}-${Date.now()}.png`
      link.href = canvas.toDataURL()
      link.click()
    } catch (error) {
      console.error('导出PNG失败:', error)
      alert('导出PNG失败，请重试')
    } finally {
      setExporting(false)
    }
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
        <QueryForm />

        <div className="conversation-content">
          <Card borderColor="green">
            <h3>
              问题: <span style={{fontWeight: 'normal'}}>{conversation!.question}</span>
            </h3>
          </Card>

          <Card borderColor="blue">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
              <h3>回答:</h3>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button onClick={copyCurrentUrl} className="share-button">
                  复制分享链接
                </button>
                <button
                  onClick={exportPageAsPNG}
                  className="export-button"
                  disabled={exporting}
                >
                  {exporting ? '导出中...' : '导出为PNG'}
                </button>
              </div>
            </div>
            <div className="answer">
              <ReactMarkdown>{conversation!.answer}</ReactMarkdown>
            </div>
          </Card>

          <div className="conversation-footer">
            <div className="conversation-meta">
              <p>对话 #{conversation!.id}</p>
              <p>时间: {formatDate(conversation!.created_at)}</p>
              {conversation!.model && <p>模型: {conversation!.model}</p>}
            </div>
            <Link to="/" className="back-link">
              ← 返回首页
            </Link>
          </div>
        </div>
      </main>
    </div>
  )
}

export default ConversationPage

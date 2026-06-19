import { useState } from 'react'
import { useLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import { useT } from './contexts/LanguageContext'
import { translate } from './i18n'
import { getLanguageFromUrl } from './utils/language'
import { getClientId } from './utils/clientId'
import Navigation from './components/Navigation'
import PageCard from './components/PageCard'
import PageTitle from './components/PageTitle'
import Card from './components/Card'
import { AppLink } from './components/AppLink'
import type { ConversationListResponse, ConversationSummary } from './types/api'

const PAGE_SIZE = 50

interface ConversationPage {
  conversations: ConversationSummary[]
  hasMore: boolean
}

type LoaderData = ConversationPage

// Over-fetch one row so the presence of the extra row tells us whether another
// page exists, without an extra empty request when the count is an exact
// multiple of PAGE_SIZE.
async function fetchConversations(beforeId?: number): Promise<ConversationPage> {
  const params = new URLSearchParams({ client_id: getClientId(), limit: String(PAGE_SIZE + 1) })
  if (beforeId !== undefined) {
    params.set('before_id', String(beforeId))
  }
  const res = await fetch(`/api/conversations?${params.toString()}`)
  if (!res.ok) {
    throw new Response('', { status: res.status })
  }
  const all = ((await res.json()) as ConversationListResponse).conversations
  return { conversations: all.slice(0, PAGE_SIZE), hasMore: all.length > PAGE_SIZE }
}

export async function historyPageLoader({ request }: LoaderFunctionArgs): Promise<LoaderData> {
  try {
    return await fetchConversations()
  } catch {
    throw new Response(
      translate(getLanguageFromUrl(request.url), 'history.errors.loadFailed'),
      { status: 500 }
    )
  }
}

const formatDate = (timestamp: number) =>
  new Date(timestamp * 1000).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })

function HistoryPage() {
  const t = useT()
  const initial = useLoaderData() as LoaderData
  const [conversations, setConversations] = useState(initial.conversations)
  const [hasMore, setHasMore] = useState(initial.hasMore)
  const [loadingMore, setLoadingMore] = useState(false)

  const loadMore = async () => {
    setLoadingMore(true)
    try {
      const next = await fetchConversations(conversations[conversations.length - 1].id)
      setConversations((prev) => [...prev, ...next.conversations])
      setHasMore(next.hasMore)
    } finally {
      setLoadingMore(false)
    }
  }

  return (
    <>
      <Navigation />
      <main className="main">
        <PageCard>
          <PageTitle>{t('history.title')}</PageTitle>

          {conversations.length === 0 ? (
            <Card style={{ margin: '1rem 0' }}>
              <p>{t('history.empty')}</p>
            </Card>
          ) : (
            <>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {conversations.map((conversation) => (
                  <AppLink
                    key={conversation.uuid}
                    to={`/conversation/${conversation.uuid}`}
                    style={{ textDecoration: 'none', color: 'inherit' }}
                  >
                    <Card style={{ cursor: 'pointer', padding: '1rem', margin: 0, transition: 'all 0.2s' }}>
                      <p style={{ margin: 0, wordBreak: 'break-word', fontWeight: 600 }}>
                        {conversation.question}
                      </p>
                      <p style={{ margin: '0.4rem 0 0 0', fontSize: 'var(--font-xs)', color: 'var(--color-text-muted)' }}>
                        {formatDate(conversation.created_at)}
                        {' · '}
                        {conversation.language}
                        {' · '}
                        {conversation.model}
                      </p>
                    </Card>
                  </AppLink>
                ))}
              </div>

              {hasMore && (
                <div style={{ textAlign: 'center', marginTop: '1rem' }}>
                  <button onClick={loadMore} disabled={loadingMore} className="share-button">
                    {loadingMore ? t('common.loading') : t('history.loadMore')}
                  </button>
                </div>
              )}
            </>
          )}
        </PageCard>
      </main>
    </>
  )
}

export default HistoryPage

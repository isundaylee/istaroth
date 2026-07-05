import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Pencil } from 'lucide-react'
import { useT } from '../contexts/LanguageContext'
import { useCloseSidebarDrawer } from './PageShell'
import { getClientId } from '../utils/clientId'
import { AppLink } from './AppLink'
import Button from './Button'
import type { ConversationListResponse, ConversationSummary } from '../types/api'
import styles from './HistoryRail.module.css'

const PAGE_SIZE = 50

async function fetchConversations(beforeId?: number): Promise<{ conversations: ConversationSummary[]; hasMore: boolean }> {
  const params = new URLSearchParams({ client_id: getClientId(), limit: String(PAGE_SIZE + 1) })
  if (beforeId !== undefined) params.set('before_id', String(beforeId))
  const res = await fetch(`/api/conversations?${params.toString()}`)
  if (!res.ok) throw new Response('', { status: res.status })
  const all = ((await res.json()) as ConversationListResponse).conversations
  return { conversations: all.slice(0, PAGE_SIZE), hasMore: all.length > PAGE_SIZE }
}

const TODAY = new Date()

function dayLabel(ts: number, t: ReturnType<typeof useT>): string {
  const d = new Date(ts * 1000)
  if (d.getFullYear() === TODAY.getFullYear() && d.getMonth() === TODAY.getMonth() && d.getDate() === TODAY.getDate()) {
    return t('history.today')
  }
  const yesterday = new Date(TODAY)
  yesterday.setDate(yesterday.getDate() - 1)
  if (d.getFullYear() === yesterday.getFullYear() && d.getMonth() === yesterday.getMonth() && d.getDate() === yesterday.getDate()) {
    return t('history.yesterday')
  }
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function formatTime(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

interface HistoryRailContentProps {
  activeConversationId?: string
}

export function HistoryRailContent({ activeConversationId }: HistoryRailContentProps) {
  const t = useT()
  const closeDrawer = useCloseSidebarDrawer()
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(false)

  const seenIdsRef = useRef<Set<string>>(new Set())

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(false)
    fetchConversations().then((page) => {
      if (cancelled) return
      for (const c of page.conversations) seenIdsRef.current.add(c.uuid)
      setConversations(page.conversations)
      setHasMore(page.hasMore)
      setLoading(false)
    }).catch(() => {
      if (cancelled) return
      setError(true)
      setLoading(false)
    })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!activeConversationId) return
    if (seenIdsRef.current.has(activeConversationId)) return
    let cancelled = false
    fetchConversations().then((page) => {
      if (cancelled) return
      for (const c of page.conversations) seenIdsRef.current.add(c.uuid)
      setConversations(page.conversations)
      setHasMore(page.hasMore)
    }).catch(() => {})
    return () => { cancelled = true }
  }, [activeConversationId])

  const loadMore = useCallback(async () => {
    if (conversations.length === 0) return
    setLoadingMore(true)
    try {
      const next = await fetchConversations(conversations[conversations.length - 1].id)
      for (const c of next.conversations) seenIdsRef.current.add(c.uuid)
      setConversations((prev) => [...prev, ...next.conversations])
      setHasMore(next.hasMore)
    } finally {
      setLoadingMore(false)
    }
  }, [conversations])

  const groups = useMemo(() => {
    const map = new Map<string, ConversationSummary[]>()
    for (const c of conversations) {
      const key = dayLabel(c.created_at, t)
      const group = map.get(key)
      if (group) {
        group.push(c)
      } else {
        map.set(key, [c])
      }
    }
    return [...map.entries()]
  }, [conversations, t])

  if (loading) {
    return <div className={styles.railStatus}>{t('common.loading')}</div>
  }
  if (error) {
    return <div className={styles.railStatus}>{t('history.errors.loadFailed')}</div>
  }
  if (conversations.length === 0) {
    return (
      <div className={styles.railEmpty}>
        <p>{t('history.empty')}</p>
      </div>
    )
  }

  return (
    <div className={styles.railScroll}>
      <AppLink to="/" className={styles.newQuestion} onClick={closeDrawer}>
        <Pencil size={14} className={styles.newQuestionIcon} aria-hidden />
        {t('history.newQuestion')}
      </AppLink>
      {groups.map(([label, entries]) => (
        <div key={label} className={styles.group}>
          <h3 className={styles.groupHeader}>{label}</h3>
          <div className={styles.timeline}>
            {entries.map((entry) => (
              <div
                key={entry.uuid}
                className={`${styles.entry} ${entry.uuid === activeConversationId ? styles.entryActive : ''}`}
              >
                <div className={styles.marker}>
                  <svg viewBox="0 0 24 24" className={styles.sparkle} aria-hidden="true">
                    <path
                      d="M12 2 Q12 12 22 12 Q12 12 12 22 Q12 12 2 12 Q12 12 12 2 Z"
                      fill="var(--color-primary-fill)"
                    />
                  </svg>
                  <div className={styles.spine} />
                </div>
                <AppLink
                  to={`/conversation/${entry.uuid}`}
                  className={styles.entryLink}
                  onClick={closeDrawer}
                >
                  <span className={styles.entryQuestion}>{entry.question}</span>
                  <span className={styles.entryMeta}>
                    {formatTime(entry.created_at)}
                    {' · '}
                    {entry.language}
                    {' · '}
                    {entry.model}
                  </span>
                </AppLink>
              </div>
            ))}
          </div>
        </div>
      ))}
      {hasMore && (
        <div className={styles.loadMore}>
          <Button onClick={loadMore} disabled={loadingMore} variant="secondary" size="sm">
            {loadingMore ? t('common.loading') : t('history.loadMore')}
          </Button>
        </div>
      )}
    </div>
  )
}

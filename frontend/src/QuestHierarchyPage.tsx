import React from 'react'
import { useLoaderData, useSearchParams, type LoaderFunctionArgs } from 'react-router-dom'
import { useT } from './contexts/LanguageContext'
import Navigation from './components/Navigation'
import Card from './components/Card'
import TextInput from './components/TextInput'
import PageCard from './components/PageCard'
import LibraryHeader from './components/LibraryHeader'
import { translate } from './i18n'
import { getLanguageFromUrl } from './utils/language'
import { useAppNavigate } from './hooks/useAppNavigate'
import type {
  QuestHierarchyResponse,
  QuestHierarchyType,
  QuestHierarchySeries,
  QuestHierarchyChapter,
} from './types/api'

interface LoaderData {
  types: QuestHierarchyType[]
}

export async function questHierarchyPageLoader({ request }: LoaderFunctionArgs): Promise<LoaderData> {
  const language = getLanguageFromUrl(request.url)

  const res = await fetch(`/api/library/quest-hierarchy?language=${language}`)
  if (!res.ok) {
    throw new Response(translate(language, 'library.errors.loadFailed'), { status: res.status })
  }
  const data = (await res.json()) as QuestHierarchyResponse
  return { types: data.types }
}

function seriesQuestCount(series: QuestHierarchySeries): number {
  return series.chapters.reduce((sum, chapter) => sum + chapter.quests.length, 0)
}

function seriesFirstQuestId(series: QuestHierarchySeries): number | null {
  for (const chapter of series.chapters) {
    if (chapter.quests.length > 0) return chapter.quests[0].id
  }
  return null
}

function chapterFirstQuestId(chapter: QuestHierarchyChapter): number | null {
  return chapter.quests.length > 0 ? chapter.quests[0].id : null
}

function typeQuestCount(type: QuestHierarchyType): number {
  return (
    type.series.reduce((sum, series) => sum + seriesQuestCount(series), 0) +
    type.chapters.reduce((sum, chapter) => sum + chapter.quests.length, 0) +
    type.standalone_quests.length
  )
}

interface QuestSearchEntry {
  id: number
  title: string
  context: string
  haystack: string
}

// Flatten the tree into one searchable quest list so a query can surface a
// quest regardless of its drill-down position. A quest's haystack includes its
// ancestors' titles, so matching a series/chapter title surfaces its quests too.
function flattenQuests(
  types: QuestHierarchyType[],
  translateQuestType: (questType: string) => string
): QuestSearchEntry[] {
  const entries: QuestSearchEntry[] = []
  const push = (id: number, title: string, ancestors: string[]) => {
    const context = ancestors.join(' / ')
    entries.push({ id, title, context, haystack: [title, ...ancestors].join(' ').toLowerCase() })
  }
  for (const type of types) {
    const typeLabel = translateQuestType(type.quest_type)
    for (const series of type.series) {
      for (const chapter of series.chapters) {
        for (const quest of chapter.quests) {
          push(quest.id, quest.title, [typeLabel, series.series_title, chapter.chapter_title])
        }
      }
    }
    for (const chapter of type.chapters) {
      for (const quest of chapter.quests) {
        push(quest.id, quest.title, [typeLabel, chapter.chapter_title])
      }
    }
    for (const quest of type.standalone_quests) {
      push(quest.id, quest.title, [typeLabel])
    }
  }
  return entries
}

interface NavCardProps {
  label: string
  count?: number
  sublabel?: string
  onClick: () => void
}

function NavCard({ label, count, sublabel, onClick }: NavCardProps) {
  return (
    <div
      onClick={onClick}
      onMouseEnter={(e: React.MouseEvent<HTMLDivElement>) => {
        const card = e.currentTarget.querySelector('.card') as HTMLElement
        if (card) {
          card.style.backgroundColor = 'var(--color-surface-active)'
          card.style.transform = 'translateY(-2px)'
        }
      }}
      onMouseLeave={(e: React.MouseEvent<HTMLDivElement>) => {
        const card = e.currentTarget.querySelector('.card') as HTMLElement
        if (card) {
          card.style.backgroundColor = 'var(--color-surface-secondary)'
          card.style.transform = 'translateY(0)'
        }
      }}
    >
      <Card style={{ cursor: 'pointer', transition: 'all 0.2s', padding: '1rem', margin: 0 }}>
        <p style={{ margin: 0, wordBreak: 'break-word' }}>
          {label}
          {count !== undefined && (
            <span style={{ color: 'var(--color-text-secondary)' }}> ({count})</span>
          )}
        </p>
        {sublabel && (
          <p
            style={{
              margin: '0.25rem 0 0',
              wordBreak: 'break-word',
              color: 'var(--color-text-secondary)',
              fontSize: 'var(--font-sm)',
            }}
          >
            {sublabel}
          </p>
        )}
      </Card>
    </div>
  )
}

function CardGrid({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
        gap: '1rem',
      }}
    >
      {children}
    </div>
  )
}

function QuestHierarchyPage() {
  const t = useT()
  const navigate = useAppNavigate()
  const { types } = useLoaderData() as LoaderData
  const [searchParams] = useSearchParams()

  // Initial drill-down comes from the URL so the file viewer's back button can
  // deep-link straight to a type (and its standalone list). Subsequent in-page
  // navigation is plain state, which keeps the loader from refetching.
  const typeParam = searchParams.get('type')
  const initialType = typeParam ? types.find((type) => type.quest_type === typeParam) ?? null : null
  const [selectedType, setSelectedType] = React.useState<QuestHierarchyType | null>(initialType)
  const [showStandalone, setShowStandalone] = React.useState(
    initialType !== null && searchParams.get('standalone') === '1'
  )
  const [search, setSearch] = React.useState('')

  const translateQuestType = (questType: string): string => {
    const key = `library.questTypes.${questType}`
    const translated = t(key)
    return translated === key ? questType : translated
  }

  // translateQuestType only changes with the active language, which remounts
  // the page via the loader, so depending on `types` alone is sufficient.
  const allQuests = React.useMemo(() => flattenQuests(types, translateQuestType), [types])

  const reset = () => {
    setSelectedType(null)
    setShowStandalone(false)
  }

  const openType = (type: QuestHierarchyType) => {
    setSelectedType(type)
    setShowStandalone(false)
  }

  const openQuest = (id: number) => {
    navigate(`/library/agd_quest/${encodeURIComponent(id)}`)
  }

  // Breadcrumb trail of clickable segments leading to the current view.
  const crumbs: { label: string; onClick: () => void }[] = [
    { label: t('library.categories.agd_quest'), onClick: reset },
  ]
  if (selectedType) {
    crumbs.push({ label: translateQuestType(selectedType.quest_type), onClick: () => openType(selectedType) })
  }
  if (showStandalone) {
    crumbs.push({ label: t('library.standalone'), onClick: () => undefined })
  }

  const query = search.trim().toLowerCase()
  const searchResults = query ? allQuests.filter((entry) => entry.haystack.includes(query)) : []

  let content: React.ReactNode
  if (query) {
    content =
      searchResults.length === 0 ? (
        <Card style={{ margin: '1rem 0' }}>
          <p>{t('library.noSearchResults')}</p>
        </Card>
      ) : (
        <CardGrid>
          {searchResults.map((entry) => (
            <NavCard
              key={entry.id}
              label={entry.title || t('library.noFileName')}
              sublabel={entry.context}
              onClick={() => openQuest(entry.id)}
            />
          ))}
        </CardGrid>
      )
  } else if (showStandalone && selectedType) {
    content = (
      <CardGrid>
        {selectedType.standalone_quests.map((quest) => (
          <NavCard key={quest.id} label={quest.title || t('library.noFileName')} onClick={() => openQuest(quest.id)} />
        ))}
      </CardGrid>
    )
  } else if (selectedType) {
    content = (
      <CardGrid>
        {selectedType.series.map((series) => {
          const firstQuestId = seriesFirstQuestId(series)
          return (
            <NavCard
              key={`s${series.series_id}`}
              label={series.series_title}
              count={seriesQuestCount(series)}
              onClick={() => firstQuestId !== null && openQuest(firstQuestId)}
            />
          )
        })}
        {selectedType.chapters.map((chapter) => {
          const firstQuestId = chapterFirstQuestId(chapter)
          return (
            <NavCard
              key={`c${chapter.chapter_id}`}
              label={chapter.chapter_title}
              count={chapter.quests.length}
              onClick={() => firstQuestId !== null && openQuest(firstQuestId)}
            />
          )
        })}
        {selectedType.standalone_quests.length > 0 && (
          <NavCard
            label={t('library.standalone')}
            count={selectedType.standalone_quests.length}
            onClick={() => setShowStandalone(true)}
          />
        )}
      </CardGrid>
    )
  } else {
    content = (
      <CardGrid>
        {types.map((type) => (
          <NavCard
            key={type.quest_type}
            label={translateQuestType(type.quest_type)}
            count={typeQuestCount(type)}
            onClick={() => openType(type)}
          />
        ))}
      </CardGrid>
    )
  }

  // The back button climbs the in-page drill-down one level at a time, only
  // leaving for the library categories once at the quest root.
  let backText = t('library.backToCategories')
  let onBack: (() => void) | undefined
  if (showStandalone && selectedType) {
    backText = translateQuestType(selectedType.quest_type)
    onBack = () => setShowStandalone(false)
  } else if (selectedType) {
    backText = t('library.categories.agd_quest')
    onBack = reset
  }

  return (
    <>
      <Navigation />
      <main className="main">
        <PageCard>
          <LibraryHeader
            title={t('library.categories.agd_quest')}
            backPath="/library"
            backText={backText}
            onBack={onBack}
          />

          <TextInput
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('library.questSearchPlaceholder')}
            style={{ width: '100%', marginBottom: '1rem' }}
          />

          {!query && crumbs.length > 1 && (
            <div style={{ margin: '0 0 1rem', display: 'flex', flexWrap: 'wrap', gap: '0.25rem', alignItems: 'center' }}>
              {crumbs.map((crumb, index) => (
                <React.Fragment key={index}>
                  {index > 0 && <span style={{ color: 'var(--color-text-secondary)' }}>/</span>}
                  {index < crumbs.length - 1 ? (
                    <button
                      onClick={crumb.onClick}
                      style={{
                        background: 'none',
                        border: 'none',
                        padding: '0.25rem',
                        cursor: 'pointer',
                        color: 'var(--color-primary-link)',
                        fontSize: 'var(--font-sm)',
                      }}
                    >
                      {crumb.label}
                    </button>
                  ) : (
                    <span style={{ padding: '0.25rem', fontSize: 'var(--font-sm)' }}>{crumb.label}</span>
                  )}
                </React.Fragment>
              ))}
            </div>
          )}

          {content}
        </PageCard>
      </main>
    </>
  )
}

export default QuestHierarchyPage

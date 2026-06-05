import React from 'react'
import { useLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import { useT } from './contexts/LanguageContext'
import Navigation from './components/Navigation'
import Card from './components/Card'
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

function typeQuestCount(type: QuestHierarchyType): number {
  return (
    type.series.reduce((sum, series) => sum + seriesQuestCount(series), 0) +
    type.chapters.reduce((sum, chapter) => sum + chapter.quests.length, 0) +
    type.standalone_quests.length
  )
}

interface NavCardProps {
  label: string
  count?: number
  onClick: () => void
}

function NavCard({ label, count, onClick }: NavCardProps) {
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

  const [selectedType, setSelectedType] = React.useState<QuestHierarchyType | null>(null)
  const [selectedSeries, setSelectedSeries] = React.useState<QuestHierarchySeries | null>(null)
  const [selectedChapter, setSelectedChapter] = React.useState<QuestHierarchyChapter | null>(null)
  const [showStandalone, setShowStandalone] = React.useState(false)

  const translateQuestType = (questType: string): string => {
    const key = `library.questTypes.${questType}`
    const translated = t(key)
    return translated === key ? questType : translated
  }

  const reset = () => {
    setSelectedType(null)
    setSelectedSeries(null)
    setSelectedChapter(null)
    setShowStandalone(false)
  }

  const openType = (type: QuestHierarchyType) => {
    setSelectedType(type)
    setSelectedSeries(null)
    setSelectedChapter(null)
    setShowStandalone(false)
  }

  const openSeries = (series: QuestHierarchySeries) => {
    setSelectedSeries(series)
    setSelectedChapter(null)
    setShowStandalone(false)
  }

  const openChapter = (chapter: QuestHierarchyChapter) => {
    setSelectedChapter(chapter)
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
  if (selectedSeries) {
    crumbs.push({ label: selectedSeries.series_title, onClick: () => openSeries(selectedSeries) })
  }
  if (selectedChapter) {
    crumbs.push({ label: selectedChapter.chapter_title, onClick: () => openChapter(selectedChapter) })
  }
  if (showStandalone) {
    crumbs.push({ label: t('library.standalone'), onClick: () => undefined })
  }

  let content: React.ReactNode
  if (showStandalone && selectedType) {
    content = (
      <CardGrid>
        {selectedType.standalone_quests.map((quest) => (
          <NavCard key={quest.id} label={quest.title || t('library.noFileName')} onClick={() => openQuest(quest.id)} />
        ))}
      </CardGrid>
    )
  } else if (selectedChapter) {
    content = (
      <CardGrid>
        {selectedChapter.quests.map((quest) => (
          <NavCard key={quest.id} label={quest.title || t('library.noFileName')} onClick={() => openQuest(quest.id)} />
        ))}
      </CardGrid>
    )
  } else if (selectedSeries) {
    content = (
      <CardGrid>
        {selectedSeries.chapters.map((chapter) => (
          <NavCard
            key={chapter.chapter_id}
            label={chapter.chapter_title}
            count={chapter.quests.length}
            onClick={() => openChapter(chapter)}
          />
        ))}
      </CardGrid>
    )
  } else if (selectedType) {
    content = (
      <CardGrid>
        {selectedType.series.map((series) => (
          <NavCard
            key={`s${series.series_id}`}
            label={series.series_title}
            count={seriesQuestCount(series)}
            onClick={() => openSeries(series)}
          />
        ))}
        {selectedType.chapters.map((chapter) => (
          <NavCard
            key={`c${chapter.chapter_id}`}
            label={chapter.chapter_title}
            count={chapter.quests.length}
            onClick={() => openChapter(chapter)}
          />
        ))}
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

  return (
    <>
      <Navigation />
      <main className="main">
        <PageCard>
          <LibraryHeader
            title={t('library.categories.agd_quest')}
            backPath="/library"
            backText={t('library.backToCategories')}
          />

          {crumbs.length > 1 && (
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
                        color: 'var(--color-link)',
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

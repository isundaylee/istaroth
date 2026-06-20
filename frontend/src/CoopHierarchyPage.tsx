import React from 'react'
import { useLoaderData, useSearchParams, type LoaderFunctionArgs } from 'react-router-dom'
import { useT } from './contexts/LanguageContext'
import Card from './components/Card'
import HierarchyBrowser, { NavCard, CardGrid, type Crumb } from './components/HierarchyBrowser'
import { translate } from './i18n'
import { getLanguageFromUrl } from './utils/language'
import { useAppNavigate } from './hooks/useAppNavigate'
import type {
  CoopHierarchyResponse,
  CoopHierarchyCharacter,
  CoopHierarchyChapter,
} from './types/api'

interface LoaderData {
  characters: CoopHierarchyCharacter[]
}

export async function coopHierarchyPageLoader({ request }: LoaderFunctionArgs): Promise<LoaderData> {
  const language = getLanguageFromUrl(request.url)

  const res = await fetch(`/api/library/coop-hierarchy?language=${language}`)
  if (!res.ok) {
    throw new Response(translate(language, 'library.errors.loadFailed'), { status: res.status })
  }
  const data = (await res.json()) as CoopHierarchyResponse
  return { characters: data.characters }
}

function characterQuestCount(character: CoopHierarchyCharacter): number {
  return character.chapters.reduce((sum, chapter) => sum + chapter.quests.length, 0)
}

interface HangoutSearchEntry {
  id: number
  title: string
  context: string
  haystack: string
}

// Flatten the tree into one searchable quest list so a query can surface a
// hangout regardless of its drill-down position. A quest's haystack includes its
// ancestors' titles, so matching a character/chapter title surfaces its quests.
function flattenHangouts(characters: CoopHierarchyCharacter[]): HangoutSearchEntry[] {
  const entries: HangoutSearchEntry[] = []
  for (const character of characters) {
    for (const chapter of character.chapters) {
      for (const quest of chapter.quests) {
        const ancestors = [character.character_name, chapter.chapter_title].filter(Boolean)
        entries.push({
          id: quest.id,
          title: quest.title,
          context: ancestors.join(' / '),
          haystack: [quest.title, ...ancestors].join(' ').toLowerCase(),
        })
      }
    }
  }
  return entries
}

function CoopHierarchyPage() {
  const t = useT()
  const navigate = useAppNavigate()
  const { characters } = useLoaderData() as LoaderData
  const [searchParams] = useSearchParams()

  // Initial drill-down comes from the URL so the file viewer's back button can
  // deep-link straight to a character (and chapter). Subsequent in-page
  // navigation is plain state, which keeps the loader from refetching.
  const avatarParam = searchParams.get('avatar')
  const initialCharacter = avatarParam
    ? characters.find((character) => String(character.avatar_id) === avatarParam) ?? null
    : null
  const chapterParam = searchParams.get('chapter')
  const initialChapter =
    initialCharacter !== null && chapterParam
      ? initialCharacter.chapters.find((chapter) => String(chapter.chapter_id) === chapterParam) ??
        null
      : null

  const [selectedCharacter, setSelectedCharacter] =
    React.useState<CoopHierarchyCharacter | null>(initialCharacter)
  const [selectedChapter, setSelectedChapter] = React.useState<CoopHierarchyChapter | null>(
    initialChapter
  )
  const [search, setSearch] = React.useState('')

  const allHangouts = React.useMemo(() => flattenHangouts(characters), [characters])

  const reset = () => {
    setSelectedCharacter(null)
    setSelectedChapter(null)
  }

  // A character with a single act drills straight into it (the lone chapter card
  // would just be a redundant click).
  const openCharacter = (character: CoopHierarchyCharacter) => {
    setSelectedCharacter(character)
    setSelectedChapter(character.chapters.length === 1 ? character.chapters[0] : null)
  }

  const openChapter = (chapter: CoopHierarchyChapter) => setSelectedChapter(chapter)

  const openQuest = (id: number) => {
    navigate(`/library/agd_coop/${encodeURIComponent(id)}`)
  }

  const query = search.trim().toLowerCase()

  // Breadcrumb trail of clickable segments leading to the current view (hidden
  // while searching).
  const crumbs: Crumb[] = query
    ? []
    : [{ label: t('library.categories.agd_coop'), onClick: reset }]
  if (!query && selectedCharacter) {
    crumbs.push({
      label: selectedCharacter.character_name,
      onClick: () => openCharacter(selectedCharacter),
    })
    // Only show the chapter crumb when the character has more than one act.
    if (selectedChapter && selectedCharacter.chapters.length > 1) {
      crumbs.push({ label: selectedChapter.chapter_title, onClick: () => undefined })
    }
  }

  const searchResults = query ? allHangouts.filter((entry) => entry.haystack.includes(query)) : []

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
  } else if (selectedChapter) {
    content = (
      <CardGrid>
        {selectedChapter.quests.map((quest) => (
          <NavCard
            key={quest.id}
            label={quest.title || t('library.noFileName')}
            onClick={() => openQuest(quest.id)}
          />
        ))}
      </CardGrid>
    )
  } else if (selectedCharacter) {
    content = (
      <CardGrid>
        {selectedCharacter.chapters.map((chapter) => (
          <NavCard
            key={chapter.chapter_id}
            label={chapter.chapter_title || t('library.noFileName')}
            count={chapter.quests.length}
            onClick={() => openChapter(chapter)}
          />
        ))}
      </CardGrid>
    )
  } else {
    content = (
      <CardGrid>
        {characters.map((character) => (
          <NavCard
            key={character.avatar_id}
            label={character.character_name}
            count={characterQuestCount(character)}
            onClick={() => openCharacter(character)}
          />
        ))}
      </CardGrid>
    )
  }

  // The back button climbs the in-page drill-down one level at a time, only
  // leaving for the library categories once at the hangout root.
  let backText = t('library.backToCategories')
  let onBack: (() => void) | undefined
  if (selectedChapter && selectedCharacter && selectedCharacter.chapters.length > 1) {
    backText = selectedCharacter.character_name
    onBack = () => setSelectedChapter(null)
  } else if (selectedCharacter) {
    backText = t('library.categories.agd_coop')
    onBack = reset
  }

  return (
    <HierarchyBrowser
      title={t('library.categories.agd_coop')}
      backText={backText}
      onBack={onBack}
      search={search}
      onSearchChange={setSearch}
      searchPlaceholder={t('library.coopSearchPlaceholder')}
      crumbs={crumbs}
    >
      {content}
    </HierarchyBrowser>
  )
}

export default CoopHierarchyPage

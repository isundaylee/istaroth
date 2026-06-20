import { useEffect, useMemo, useState } from 'react'
import { useLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'
import { useT, useTranslation } from './contexts/LanguageContext'
import Navigation from './components/Navigation'
import PageCard from './components/PageCard'
import LibraryHeader from './components/LibraryHeader'
import NavButton from './components/NavButton'
import { translate } from './i18n'
import { getLanguageFromUrl } from './utils/language'
import { useAppNavigate } from './hooks/useAppNavigate'
import { useProperNounSelection } from './hooks/useProperNounSelection'
import { buildProperNounMatcher } from './utils/properNouns'
import { rehypeProperNouns } from './utils/rehypeProperNouns'
import type {
  LibraryFileResponse,
  LibraryFilesResponse,
  LibraryFileInfo,
  ProperNounsResponse,
  QuestSeriesResponse,
  CoopCharacterResponse
} from './types/api'

const QUEST_CATEGORY = 'agd_quest'
const COOP_CATEGORY = 'agd_coop'

interface LoaderData {
  fileContent: string
  fileTitle: string
  fileId: string
  previousFile: LibraryFileInfo | null
  nextFile: LibraryFileInfo | null
  category: string
  currentId: number | null
  questSeries: QuestSeriesResponse | null
  coopCharacter: CoopCharacterResponse | null
}

export async function libraryFileViewerLoader({ params, request }: LoaderFunctionArgs): Promise<LoaderData> {
  const { category, id } = params
  if (!category || !id) {
    throw new Response(translate(getLanguageFromUrl(request.url), 'library.errors.invalidCategory'), { status: 400 })
  }

  const language = getLanguageFromUrl(request.url)
  const isQuest = category === QUEST_CATEGORY
  const isCoop = category === COOP_CATEGORY

  const [fileRes, filesRes, tocRes] = await Promise.all([
    fetch(`/api/library/file/${encodeURIComponent(category)}/${encodeURIComponent(id)}?language=${language}`),
    fetch(`/api/library/files/${encodeURIComponent(category)}?language=${language}`),
    isQuest
      ? fetch(`/api/library/quest-series/${encodeURIComponent(id)}?language=${language}`)
      : isCoop
      ? fetch(`/api/library/coop-character/${encodeURIComponent(id)}?language=${language}`)
      : Promise.resolve(null)
  ])

  if (!fileRes.ok) {
    throw new Response(translate(language, 'library.errors.loadFailed'), { status: fileRes.status })
  }

  const fileData = (await fileRes.json()) as LibraryFileResponse
  let previousFile: LibraryFileInfo | null = null
  let nextFile: LibraryFileInfo | null = null

  if (filesRes.ok) {
    const filesData = (await filesRes.json()) as LibraryFilesResponse
    const currentId = parseInt(id, 10)
    const currentIndex = filesData.files.findIndex((file) => file.id === currentId)
    if (currentIndex > 0) previousFile = filesData.files[currentIndex - 1]
    if (currentIndex >= 0 && currentIndex < filesData.files.length - 1) nextFile = filesData.files[currentIndex + 1]
  }

  // The TOC is supplementary; a failed fetch must not break the viewer.
  let questSeries: QuestSeriesResponse | null = null
  let coopCharacter: CoopCharacterResponse | null = null
  if (tocRes && tocRes.ok) {
    if (isQuest) {
      questSeries = (await tocRes.json()) as QuestSeriesResponse
    } else if (isCoop) {
      coopCharacter = (await tocRes.json()) as CoopCharacterResponse
    }
  }

  return {
    fileContent: fileData.content,
    fileTitle: fileData.file_info.title,
    fileId: id,
    previousFile,
    nextFile,
    category,
    currentId: isQuest || isCoop ? parseInt(id, 10) : null,
    questSeries,
    coopCharacter
  }
}

function LibraryFileViewer() {
  const t = useT()
  const { language } = useTranslation()
  const navigate = useAppNavigate()
  const { fileContent, fileTitle, fileId, previousFile, nextFile, category, currentId, questSeries, coopCharacter } = useLoaderData() as LoaderData
  const { answerRef, answerHandlers, selectionUi } = useProperNounSelection(fileContent)
  // Static curated list (per language, fast) and the per-file LLM extraction
  // (null = still in flight). We highlight nothing for the first 2s, then fall
  // back to the static list; the LLM result replaces it whenever it arrives.
  const [staticNouns, setStaticNouns] = useState<string[]>([])
  const [llmNouns, setLlmNouns] = useState<string[] | null>(null)
  const [fallbackElapsed, setFallbackElapsed] = useState(false)
  const properNounMatcher = useMemo(() => {
    const nouns = llmNouns !== null ? llmNouns : fallbackElapsed ? staticNouns : []
    return nouns.length > 0 ? buildProperNounMatcher(nouns) : null
  }, [llmNouns, fallbackElapsed, staticNouns])

  // Group the enclosing series' chapters (or the lone chapter) into TOC sections.
  const series = questSeries?.series
  const chapter = questSeries?.chapter

  // For quests/hangouts, return to the enclosing hierarchy view (the quest type,
  // or the hangout's character + chapter) rather than the flat category root.
  let backPath: string
  if (category === QUEST_CATEGORY && questSeries?.quest_type) {
    backPath = `/library/${QUEST_CATEGORY}?type=${encodeURIComponent(questSeries.quest_type)}${
      !series && !chapter ? '&standalone=1' : ''
    }`
  } else if (category === COOP_CATEGORY && coopCharacter) {
    backPath = `/library/${COOP_CATEGORY}?avatar=${encodeURIComponent(
      coopCharacter.avatar_id
    )}&chapter=${encodeURIComponent(coopCharacter.chapter.chapter_id)}`
  } else {
    backPath = `/library/${encodeURIComponent(category)}`
  }

  const translateCategory = (category: string): string => {
    const translationKey = `library.categories.${category}`
    const translated = t(translationKey)
    return translated === translationKey ? category : translated
  }
  // TOC sections and header come from the quest series/chapter or, for hangouts,
  // the character's enclosing act.
  let tocGroups: { title: string; quests: { id: number; title: string }[] }[]
  let tocTitle: string
  if (series) {
    tocGroups = series.chapters.map((c) => ({ title: c.chapter_title, quests: c.quests }))
    tocTitle = series.series_title
  } else if (chapter) {
    tocGroups = [{ title: chapter.chapter_title, quests: chapter.quests }]
    tocTitle = t('library.questSeriesToc')
  } else if (coopCharacter) {
    tocGroups = [{ title: coopCharacter.chapter.chapter_title, quests: coopCharacter.chapter.quests }]
    tocTitle = t('library.coopCharacterToc')
  } else {
    tocGroups = []
    tocTitle = ''
  }
  const tocQuestCount = tocGroups.reduce((sum, group) => sum + group.quests.length, 0)

  // Static curated list: fetched once per language, reused across files.
  useEffect(() => {
    let cancelled = false
    fetch(`/api/library/proper-nouns?language=${encodeURIComponent(language.toUpperCase())}`)
      .then((res) => (res.ok ? (res.json() as Promise<ProperNounsResponse>) : null))
      .then((data) => {
        if (!cancelled) setStaticNouns(data?.nouns ?? [])
      })
      .catch(() => {
        if (!cancelled) setStaticNouns([])
      })
    return () => {
      cancelled = true
    }
  }, [language])

  // Per-file LLM extraction: show nothing for 2s, then fall back to the static
  // list; replace with the LLM result whenever it arrives. On failure we leave
  // llmNouns null so the static fallback stays.
  useEffect(() => {
    let cancelled = false
    setLlmNouns(null)
    setFallbackElapsed(false)
    const timer = window.setTimeout(() => {
      if (!cancelled) setFallbackElapsed(true)
    }, 2000)
    fetch(
      `/api/library/file/${encodeURIComponent(category)}/${encodeURIComponent(fileId)}/proper-nouns?language=${encodeURIComponent(language.toUpperCase())}`
    )
      .then((res) => (res.ok ? (res.json() as Promise<ProperNounsResponse>) : null))
      .then((data) => {
        if (!cancelled && data) setLlmNouns(data.nouns)
      })
      .catch(() => {})
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [language, category, fileId])

  return (
    <>
      <Navigation />
      <main className="main">
        <PageCard>
          <LibraryHeader
            title={fileTitle || translateCategory(category)}
            backPath={backPath}
            backText={t('library.backToFiles')}
          />

          {tocQuestCount > 1 && (
            <details
              open
              style={{
                margin: '0 0 1.5rem',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-md)',
                padding: '0.75rem 1rem'
              }}
            >
              <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
                {tocTitle}
              </summary>
              <div style={{ marginTop: '0.5rem' }}>
                {tocGroups.map((group, groupIndex) => (
                  <div key={groupIndex} style={{ marginBottom: '0.5rem' }}>
                    {tocGroups.length > 1 && (
                      <p style={{ margin: '0.25rem 0', color: 'var(--color-text-secondary)', fontSize: 'var(--font-sm)' }}>
                        {group.title}
                      </p>
                    )}
                    <div style={{ fontSize: 'var(--font-sm)', lineHeight: 1.8 }}>
                      {group.quests.map((quest, questIndex) => (
                        <span key={quest.id}>
                          {questIndex > 0 && <span style={{ color: 'var(--color-text-muted)' }}> / </span>}
                          {quest.id === currentId ? (
                            <span style={{ fontWeight: 600, color: 'var(--color-primary-link)' }}>
                              {quest.title || t('library.noFileName')}
                            </span>
                          ) : (
                            <button
                              onClick={() => navigate(`/library/${encodeURIComponent(category)}/${encodeURIComponent(quest.id)}`)}
                              style={{
                                background: 'none',
                                border: 'none',
                                padding: 0,
                                cursor: 'pointer',
                                color: 'var(--color-text)',
                                fontSize: 'inherit',
                                textAlign: 'left'
                              }}
                            >
                              {quest.title || t('library.noFileName')}
                            </button>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </details>
          )}

          <div ref={answerRef} className="answer" onMouseUp={answerHandlers.onMouseUp} onKeyUp={answerHandlers.onKeyUp} onClick={answerHandlers.onClick}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkBreaks]}
              rehypePlugins={properNounMatcher ? [rehypeProperNouns(properNounMatcher)] : []}
            >
              {fileContent}
            </ReactMarkdown>
          </div>
          {previousFile && (
            <NavButton
              onClick={() => navigate(`/library/${encodeURIComponent(category)}/${encodeURIComponent(previousFile.id)}`)}
              label={t('library.previous')}
              title={previousFile.title || t('library.noFileName')}
              marginTop="2rem"
            />
          )}
          {nextFile && (
            <NavButton
              onClick={() => navigate(`/library/${encodeURIComponent(category)}/${encodeURIComponent(nextFile.id)}`)}
              label={t('library.next')}
              title={nextFile.title || t('library.noFileName')}
              marginTop={previousFile ? '1rem' : '2rem'}
            />
          )}
          <NavButton
            onClick={() => navigate(backPath)}
            label={t('library.backToFiles')}
            title={translateCategory(category)}
            marginTop={previousFile || nextFile ? '1rem' : '2rem'}
          />
        </PageCard>
        {selectionUi}
      </main>
    </>
  )
}

export default LibraryFileViewer

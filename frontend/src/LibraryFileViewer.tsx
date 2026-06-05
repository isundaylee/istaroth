import { useLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'
import { useT } from './contexts/LanguageContext'
import Navigation from './components/Navigation'
import PageCard from './components/PageCard'
import LibraryHeader from './components/LibraryHeader'
import NavButton from './components/NavButton'
import { translate } from './i18n'
import { getLanguageFromUrl } from './utils/language'
import { useAppNavigate } from './hooks/useAppNavigate'
import type { LibraryFileResponse, LibraryFilesResponse, LibraryFileInfo, QuestSeriesResponse } from './types/api'

const QUEST_CATEGORY = 'agd_quest'

interface LoaderData {
  fileContent: string
  fileTitle: string
  previousFile: LibraryFileInfo | null
  nextFile: LibraryFileInfo | null
  category: string
  questId: number | null
  questSeries: QuestSeriesResponse | null
}

export async function libraryFileViewerLoader({ params, request }: LoaderFunctionArgs): Promise<LoaderData> {
  const { category, id } = params
  if (!category || !id) {
    throw new Response(translate(getLanguageFromUrl(request.url), 'library.errors.invalidCategory'), { status: 400 })
  }

  const language = getLanguageFromUrl(request.url)
  const isQuest = category === QUEST_CATEGORY

  const [fileRes, filesRes, seriesRes] = await Promise.all([
    fetch(`/api/library/file/${encodeURIComponent(category)}/${encodeURIComponent(id)}?language=${language}`),
    fetch(`/api/library/files/${encodeURIComponent(category)}?language=${language}`),
    isQuest
      ? fetch(`/api/library/quest-series/${encodeURIComponent(id)}?language=${language}`)
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
  if (seriesRes && seriesRes.ok) {
    questSeries = (await seriesRes.json()) as QuestSeriesResponse
  }

  return {
    fileContent: fileData.content,
    fileTitle: fileData.file_info.title,
    previousFile,
    nextFile,
    category,
    questId: isQuest ? parseInt(id, 10) : null,
    questSeries
  }
}

function LibraryFileViewer() {
  const t = useT()
  const navigate = useAppNavigate()
  const { fileContent, fileTitle, previousFile, nextFile, category, questId, questSeries } = useLoaderData() as LoaderData

  const translateCategory = (category: string): string => {
    const translationKey = `library.categories.${category}`
    const translated = t(translationKey)
    return translated === translationKey ? category : translated
  }

  // Group the enclosing series' chapters (or the lone chapter) into TOC sections.
  const series = questSeries?.series
  const chapter = questSeries?.chapter
  const tocGroups = series
    ? series.chapters.map((c) => ({ title: c.chapter_title, quests: c.quests }))
    : chapter
    ? [{ title: chapter.chapter_title, quests: chapter.quests }]
    : []
  const tocQuestCount = tocGroups.reduce((sum, group) => sum + group.quests.length, 0)

  return (
    <>
      <Navigation />
      <main className="main">
        <PageCard>
          <LibraryHeader
            title={fileTitle || translateCategory(category)}
            backPath={`/library/${encodeURIComponent(category)}`}
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
                {series ? series.series_title : t('library.questSeriesToc')}
              </summary>
              <div style={{ marginTop: '0.5rem' }}>
                {tocGroups.map((group, groupIndex) => (
                  <div key={groupIndex} style={{ marginBottom: '0.5rem' }}>
                    {tocGroups.length > 1 && (
                      <p style={{ margin: '0.25rem 0', color: 'var(--color-text-secondary)', fontSize: 'var(--font-sm)' }}>
                        {group.title}
                      </p>
                    )}
                    <ul style={{ margin: 0, paddingLeft: '1.25rem' }}>
                      {group.quests.map((quest) => (
                        <li key={quest.id}>
                          {quest.id === questId ? (
                            <span style={{ fontWeight: 600, color: 'var(--color-primary)' }}>
                              {quest.title || t('library.noFileName')}
                            </span>
                          ) : (
                            <button
                              onClick={() => navigate(`/library/${encodeURIComponent(QUEST_CATEGORY)}/${encodeURIComponent(quest.id)}`)}
                              style={{
                                background: 'none',
                                border: 'none',
                                padding: 0,
                                cursor: 'pointer',
                                color: 'var(--color-link)',
                                fontSize: 'inherit',
                                textAlign: 'left'
                              }}
                            >
                              {quest.title || t('library.noFileName')}
                            </button>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </details>
          )}

          <div className="answer">
            <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{fileContent}</ReactMarkdown>
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
        </PageCard>
      </main>
    </>
  )
}

export default LibraryFileViewer

import { useCallback, useEffect, useRef, useState } from 'react'
import { useLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'
import { useT, useTranslation } from './contexts/LanguageContext'
import { AppLink } from './components/AppLink'
import Navigation from './components/Navigation'
import PageCard from './components/PageCard'
import LibraryHeader from './components/LibraryHeader'
import NavButton from './components/NavButton'
import CitationRenderer from './components/CitationRenderer'
import QueryProgress from './components/QueryProgress'
import { translate } from './i18n'
import { buildUrlWithLanguage, getLanguageFromUrl } from './utils/language'
import { useAppNavigate } from './hooks/useAppNavigate'
import { buildLibraryFilePath } from './utils/library'
import { getClientId } from './utils/clientId'
import { consumeQueryStream } from './utils/queryStream'
import type {
  ErrorResponse,
  LibraryFileResponse,
  LibraryFilesResponse,
  LibraryFileInfo,
  LibraryRetrieveRequest,
  LibraryRetrieveResponse,
  ModelsResponse,
  ProgressStepStart,
  QueryRequest,
  QuestSeriesResponse,
  CoopCharacterResponse
} from './types/api'

const QUEST_CATEGORY = 'agd_quest'
const COOP_CATEGORY = 'agd_coop'
const MAX_SELECTION_LENGTH = 80
const MAX_SELECTION_TERMS = 8

interface SelectionState {
  text: string
  top: number
  left: number
  placement: 'above' | 'below'
}

type SelectionPanel =
  | {
      kind: 'search'
      query: string
      loading: boolean
      results: LibraryRetrieveResponse['results']
      error: string | null
    }
  | {
      kind: 'ask'
      query: string
      question: string
      loading: boolean
      activeSteps: ProgressStepStart[]
      answer: string
      conversationUuid: string | null
      error: string | null
    }

interface SelectionPanelFrameProps {
  panel: SelectionPanel
  placement: SelectionState['placement']
  top: number
  left: number
  retrievePagePath: (query: string) => string
  onClose: () => void
}

interface RetrievalSelectionPanelProps {
  panel: Extract<SelectionPanel, { kind: 'search' }>
}

interface QuerySelectionPanelProps {
  panel: Extract<SelectionPanel, { kind: 'ask' }>
}

interface LoaderData {
  fileContent: string
  fileTitle: string
  previousFile: LibraryFileInfo | null
  nextFile: LibraryFileInfo | null
  category: string
  currentId: number | null
  questSeries: QuestSeriesResponse | null
  coopCharacter: CoopCharacterResponse | null
}

function RetrievalSelectionPanel({ panel }: RetrievalSelectionPanelProps) {
  const t = useT()

  if (panel.loading) {
    return <p className="library-selection-muted">{t('library.selection.searching')}</p>
  }
  if (panel.error) {
    return <p className="library-selection-error">{panel.error}</p>
  }
  if (panel.results.length === 0) {
    return <p className="library-selection-muted">{t('library.selection.noResults')}</p>
  }

  return (
    <div className="library-selection-results">
      {panel.results.map((result) => (
        <div key={`${result.file_info.category}-${result.file_info.id}`} className="library-selection-result">
          <AppLink to={buildLibraryFilePath(result.file_info)}>
            {result.file_info.title || t('library.noFileName')}
          </AppLink>
          <p>{result.snippet}</p>
          <span>{t('library.selection.score')}: {result.score.toFixed(3)}</span>
        </div>
      ))}
    </div>
  )
}

function QuerySelectionPanel({ panel }: QuerySelectionPanelProps) {
  const t = useT()

  return (
    <>
      {panel.loading && panel.activeSteps.length === 0 && (
        <p className="library-selection-muted loading-ellipsis">{t('query.submitting')}</p>
      )}
      {panel.loading && panel.activeSteps.length > 0 && (
        <QueryProgress steps={panel.activeSteps} className="library-selection-progress" />
      )}
      {panel.error && <p className="library-selection-error">{panel.error}</p>}
      {panel.answer && (
        <CitationRenderer content={panel.answer}>
          {({ answer, citationList }) => (
            <>
              <div className="answer library-selection-answer">{answer}</div>
              {citationList && (
                <div className="library-selection-citations" data-citation-container>
                  {citationList}
                </div>
              )}
            </>
          )}
        </CitationRenderer>
      )}
    </>
  )
}

function SelectionPanelFrame({
  panel,
  placement,
  top,
  left,
  retrievePagePath,
  onClose
}: SelectionPanelFrameProps) {
  const t = useT()
  const panelBody = panel.kind === 'search'
    ? <RetrievalSelectionPanel panel={panel} />
    : <QuerySelectionPanel panel={panel} />

  return (
    <div
      className={`library-selection-panel library-selection--${placement}`}
      style={{
        top: `${top}px`,
        left: `${left}px`,
        maxHeight: placement === 'above' ? `calc(${top}px - 1rem)` : `calc(100vh - ${top}px - 1rem)`
      }}
      onMouseDown={(event) => event.stopPropagation()}
    >
      <div className="library-selection-panel__header">
        <div>
          <p className="library-selection-panel__eyebrow">
            {panel.kind === 'search' ? t('library.selection.keywordSearch') : t('library.selection.ask')}
          </p>
          <h3>{panel.kind === 'ask' ? panel.question : panel.query}</h3>
          {panel.kind === 'search' && (
            <AppLink className="library-selection-panel__top-link" to={retrievePagePath(panel.query)}>
              {t('library.selection.openRetrieve')}
            </AppLink>
          )}
          {panel.kind === 'ask' && panel.conversationUuid && (
            <AppLink className="library-selection-panel__top-link" to={`/conversation/${panel.conversationUuid}`}>
              {t('library.selection.openConversation')}
            </AppLink>
          )}
        </div>
        <button type="button" className="library-selection-panel__close" onClick={onClose} aria-label={t('common.close')}>×</button>
      </div>
      {panelBody}
    </div>
  )
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
  const { fileContent, fileTitle, previousFile, nextFile, category, currentId, questSeries, coopCharacter } = useLoaderData() as LoaderData
  const answerRef = useRef<HTMLDivElement>(null)
  const selectionUiRef = useRef<HTMLDivElement>(null)
  const activeRequestIdRef = useRef(0)
  const defaultModelRef = useRef<string | null>(null)
  const [selection, setSelection] = useState<SelectionState | null>(null)
  const [panel, setPanel] = useState<SelectionPanel | null>(null)

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
  const normalizeSelectionText = (text: string) => text.replace(/\s+/g, ' ').trim()
  const isEntityLikeSelection = (text: string) =>
    text.length > 0 && text.length <= MAX_SELECTION_LENGTH && text.split(/\s+/).length <= MAX_SELECTION_TERMS
  const getErrorMessage = (data: unknown, fallback: string) => {
    if (data && typeof data === 'object') {
      if ('error' in data && typeof data.error === 'string') return data.error
      if ('detail' in data && typeof data.detail === 'string') return data.detail
    }
    return fallback
  }
  const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

  const captureSelection = useCallback(() => {
    const currentSelection = window.getSelection()
    const container = answerRef.current
    if (!currentSelection || !container || currentSelection.rangeCount === 0 || currentSelection.isCollapsed) {
      setSelection(null)
      setPanel(null)
      return
    }

    const range = currentSelection.getRangeAt(0)
    if (
      !container.contains(range.commonAncestorContainer) ||
      !container.contains(currentSelection.anchorNode) ||
      !container.contains(currentSelection.focusNode)
    ) {
      return
    }

    const selectedText = normalizeSelectionText(currentSelection.toString())
    if (!isEntityLikeSelection(selectedText)) {
      setSelection(null)
      setPanel(null)
      return
    }

    const rect = range.getBoundingClientRect()
    if (rect.width === 0 && rect.height === 0) {
      setSelection(null)
      setPanel(null)
      return
    }

    const placement = rect.top > window.innerHeight / 2 ? 'above' : 'below'
    setSelection({
      text: selectedText,
      top: placement === 'above' ? clamp(rect.top - 8, 8, window.innerHeight - 8) : clamp(rect.bottom + 8, 8, window.innerHeight - 8),
      left: clamp(rect.left + rect.width / 2, 140, window.innerWidth - 140),
      placement
    })
    setPanel(null)
  }, [])

  useEffect(() => {
    setSelection(null)
    setPanel(null)
    activeRequestIdRef.current += 1
  }, [fileContent])

  useEffect(() => {
    const handleMouseDown = (event: MouseEvent) => {
      const target = event.target as Node
      if (answerRef.current?.contains(target) || selectionUiRef.current?.contains(target)) return
      setSelection(null)
      setPanel(null)
      activeRequestIdRef.current += 1
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setSelection(null)
      setPanel(null)
      activeRequestIdRef.current += 1
    }
    document.addEventListener('mousedown', handleMouseDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleMouseDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [])

  const runKeywordSearch = async () => {
    if (!selection) return
    const query = selection.text
    const requestId = activeRequestIdRef.current + 1
    activeRequestIdRef.current = requestId
    setPanel({ kind: 'search', query, loading: true, results: [], error: null })

    try {
      const reqBody: LibraryRetrieveRequest = {
        language: language.toUpperCase(),
        query,
        k: 10,
        semantic: false,
        chunk_context: 0
      }
      const res = await fetch('/api/library/retrieve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(reqBody)
      })
      const data = await res.json().catch(() => null)
      if (activeRequestIdRef.current !== requestId) return
      if (!res.ok) {
        setPanel({ kind: 'search', query, loading: false, results: [], error: getErrorMessage(data, t('library.selection.errors.searchFailed')) })
        return
      }
      setPanel({ kind: 'search', query, loading: false, results: (data as LibraryRetrieveResponse).results, error: null })
    } catch {
      if (activeRequestIdRef.current === requestId) {
        setPanel({ kind: 'search', query, loading: false, results: [], error: t('library.selection.errors.noConnection') })
      }
    }
  }

  const fetchDefaultModel = async () => {
    if (defaultModelRef.current) return defaultModelRef.current
    const res = await fetch('/api/models')
    const data = await res.json().catch(() => null)
    if (!res.ok) {
      throw new Error(getErrorMessage(data as ErrorResponse | null, t('query.errors.modelsLoadFailed')))
    }
    const response = data as ModelsResponse
    if (!response.default) {
      throw new Error(t('query.errors.modelsLoadFailed'))
    }
    defaultModelRef.current = response.default
    return response.default
  }

  const updateAskPanel = (requestId: number, updater: (panel: Extract<SelectionPanel, { kind: 'ask' }>) => Extract<SelectionPanel, { kind: 'ask' }>) => {
    if (activeRequestIdRef.current !== requestId) return
    setPanel((current) => current?.kind === 'ask' ? updater(current) : current)
  }

  const retrievePagePath = (query: string) =>
    buildUrlWithLanguage('/retrieve', `?q=${encodeURIComponent(query)}&semantic=0`, language)

  const runAsk = async () => {
    if (!selection) return
    const query = selection.text
    const question = language === 'chs' ? `“${query}”是什么？` : `What is “${query}”?`
    const requestId = activeRequestIdRef.current + 1
    activeRequestIdRef.current = requestId
    setPanel({
      kind: 'ask',
      query,
      question,
      loading: true,
      activeSteps: [],
      answer: '',
      conversationUuid: null,
      error: null
    })

    try {
      const reqBody: QueryRequest = {
        language: language.toUpperCase(),
        question,
        model: await fetchDefaultModel(),
        k: 7,
        chunk_context: 2,
        client_id: getClientId()
      }
      const res = await fetch('/api/query/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(reqBody)
      })
      if (!res.ok || !res.body) {
        const data = await res.json().catch(() => null)
        updateAskPanel(requestId, (current) => ({ ...current, loading: false, error: getErrorMessage(data, t('query.errors.unknown')) }))
        return
      }

      await consumeQueryStream(res.body, {
        onStepStart: (step) => updateAskPanel(requestId, (current) => ({ ...current, activeSteps: [...current.activeSteps, step] })),
        onStepEnd: (id) => updateAskPanel(requestId, (current) => ({ ...current, activeSteps: current.activeSteps.filter((step) => step.id !== id) })),
        onDone: (result) => updateAskPanel(requestId, (current) => ({
            ...current,
            loading: false,
            activeSteps: [],
            answer: result.answer,
            conversationUuid: result.conversation_uuid,
            error: null
          })),
        onError: (message) => updateAskPanel(requestId, (current) => ({ ...current, loading: false, activeSteps: [], error: message })),
        noConnectionError: t('query.errors.noConnection'),
        unknownError: t('query.errors.unknown')
      })
    } catch (error) {
      updateAskPanel(requestId, (current) => ({
        ...current,
        loading: false,
        activeSteps: [],
        error: error instanceof Error ? error.message : t('query.errors.noConnection')
      }))
    }
  }

  const closeSelectionPanel = () => {
    setSelection(null)
    setPanel(null)
    activeRequestIdRef.current += 1
  }

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

          <div ref={answerRef} className="answer" onMouseUp={captureSelection} onKeyUp={captureSelection}>
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
          <NavButton
            onClick={() => navigate(backPath)}
            label={t('library.backToFiles')}
            title={translateCategory(category)}
            marginTop={previousFile || nextFile ? '1rem' : '2rem'}
          />
        </PageCard>
        {selection && (
          <div ref={selectionUiRef}>
            {!panel && (
              <div
                className={`library-selection-toolbar library-selection--${selection.placement}`}
                style={{ top: `${selection.top}px`, left: `${selection.left}px` }}
                onMouseDown={(event) => event.preventDefault()}
              >
                <button type="button" onClick={runKeywordSearch}>{t('library.selection.keywordSearch')}</button>
                <button type="button" onClick={runAsk}>{t('library.selection.ask')}</button>
              </div>
            )}
            {panel && (
              <SelectionPanelFrame
                panel={panel}
                placement={selection.placement}
                top={selection.top}
                left={selection.left}
                retrievePagePath={retrievePagePath}
                onClose={closeSelectionPanel}
              />
            )}
          </div>
        )}
      </main>
    </>
  )
}

export default LibraryFileViewer

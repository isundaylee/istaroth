import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useT, useTranslation } from '../contexts/LanguageContext'
import { SelectionPanelFrame, type SelectionPanel, type SelectionState } from '../components/SelectionPanel'
import { calculateFloatingPlacement } from '../utils/floatingPanel'
import { getClientId } from '../utils/clientId'
import { buildUrlWithLanguage } from '../utils/language'
import { consumeQueryStream } from '../utils/queryStream'
import type {
  ErrorResponse,
  LibraryRetrieveRequest,
  LibraryRetrieveResponse,
  ModelsResponse,
  QueryRequest
} from '../types/api'

const MAX_SELECTION_LENGTH = 80
const MAX_SELECTION_TERMS = 8

interface AnswerHandlers {
  onMouseUp: () => void
  onKeyUp: () => void
  onClick: (event: React.MouseEvent<HTMLDivElement>) => void
}

interface UseProperNounSelectionResult {
  /** Ref to attach to the answer container that holds the highlighted markdown. */
  answerRef: React.RefObject<HTMLDivElement>
  /** Spread onto the answer container to drive selection/click interactions. */
  answerHandlers: AnswerHandlers
  /** The floating toolbar/panel UI; render it once inside the page. */
  selectionUi: React.ReactNode
}

/**
 * Selecting text (or clicking a highlighted proper noun) inside the answer
 * container opens a toolbar to keyword-search or ask about that term, mirroring
 * the library file viewer. Pass a ``resetKey`` (e.g. the content identity) so the
 * selection clears whenever the underlying answer changes.
 */
export function useProperNounSelection(resetKey: unknown): UseProperNounSelectionResult {
  const t = useT()
  const { language } = useTranslation()
  const answerRef = useRef<HTMLDivElement>(null)
  const activeRequestIdRef = useRef(0)
  const defaultModelRef = useRef<string | null>(null)
  const [selection, setSelection] = useState<SelectionState | null>(null)
  const [panel, setPanel] = useState<SelectionPanel | null>(null)
  const [isFullscreen, setIsFullscreen] = useState(false)

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

  const openSelectionAtRect = useCallback((text: string, rect: DOMRect): boolean => {
    if (rect.width === 0 && rect.height === 0) return false
    const { top, left, placement } = calculateFloatingPlacement(rect)
    setSelection({ text, top, left, placement })
    setPanel(null)
    setIsFullscreen(false)
    return true
  }, [])

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

    if (!openSelectionAtRect(selectedText, range.getBoundingClientRect())) {
      setSelection(null)
      setPanel(null)
    }
  }, [openSelectionAtRect])

  const handleProperNounClick = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      const target = (event.target as HTMLElement).closest('.proper-noun')
      if (!target || !answerRef.current?.contains(target)) return
      const text = target.textContent?.trim()
      if (text) openSelectionAtRect(text, target.getBoundingClientRect())
    },
    [openSelectionAtRect]
  )

  useEffect(() => {
    setSelection(null)
    setPanel(null)
    setIsFullscreen(false)
    activeRequestIdRef.current += 1
  }, [resetKey])

  useEffect(() => {
    const handleMouseDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement
      // Keep this panel open for clicks in its own answer or in any floating
      // popup (including nested ones, which portal out of this subtree).
      if (answerRef.current?.contains(target) || target.closest?.('[data-floating-popup]')) return
      setSelection(null)
      setPanel(null)
      setIsFullscreen(false)
      activeRequestIdRef.current += 1
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setSelection(null)
      setPanel(null)
      setIsFullscreen(false)
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
      properNouns: [],
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
        client_id: getClientId(),
        cache_key: query
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
            properNouns: result.proper_nouns,
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
    setIsFullscreen(false)
    activeRequestIdRef.current += 1
  }

  const selectionUi = selection ? (
    panel ? (
      <SelectionPanelFrame
        panel={panel}
        placement={selection.placement}
        top={selection.top}
        left={selection.left}
        fullscreen={isFullscreen}
        retrievePagePath={retrievePagePath}
        onClose={closeSelectionPanel}
        onToggleFullscreen={() => setIsFullscreen((value) => !value)}
      />
    ) : (
      // Portalled to body (like FloatingPanel) so the fixed toolbar escapes any
      // transformed/clipping ancestor when this panel is itself nested.
      createPortal(
        <div
          className={`library-selection-toolbar library-selection--${selection.placement}`}
          style={{ top: `${selection.top}px`, left: `${selection.left}px` }}
          data-floating-popup
          onMouseDown={(event) => event.preventDefault()}
        >
          <button type="button" onClick={runKeywordSearch}>{t('library.selection.keywordSearch')}</button>
          <button type="button" onClick={runAsk}>{t('library.selection.ask')}</button>
        </div>,
        document.body
      )
    )
  ) : null

  return {
    answerRef,
    answerHandlers: { onMouseUp: captureSelection, onKeyUp: captureSelection, onClick: handleProperNounClick },
    selectionUi
  }
}

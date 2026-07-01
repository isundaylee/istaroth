import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useT, useTranslation } from '../contexts/LanguageContext'
import Button from '../components/Button'
import { SelectionPanelFrame, type SelectionPanel, type SelectionState } from '../components/SelectionPanel'
import selStyles from '../components/SelectionPanel.module.css'
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
const _BUDGET_BALANCED = 35

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
  const [isMinimized, setIsMinimized] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  // Whether a panel (search/ask result) is open vs just a bare selection
  // toolbar. Only flips on open/close, so handlers below can depend on it
  // directly (no re-subscribe churn during answer streaming, which leaves it
  // unchanged).
  const hasPanel = panel !== null

  // Fully dismiss any toolbar/panel and cancel in-flight requests. Used wherever
  // a selection is torn down (reset, outside-click with no panel, Escape, the
  // panel's close button).
  const closeSelection = useCallback(() => {
    setSelection(null)
    setPanel(null)
    setIsMinimized(false)
    setIsFullscreen(false)
    activeRequestIdRef.current += 1
  }, [])

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
    setIsMinimized(false)
    setIsFullscreen(false)
    return true
  }, [])

  const captureSelection = useCallback(() => {
    // A bare click (collapsed/invalid selection) should dismiss only an
    // unconfirmed selection toolbar — never an open or minimized panel, whose
    // side-rail card must survive clicks in the answer area.
    const clearToolbar = () => {
      if (hasPanel) return
      setSelection(null)
      setPanel(null)
    }
    const currentSelection = window.getSelection()
    const container = answerRef.current
    if (!currentSelection || !container || currentSelection.rangeCount === 0 || currentSelection.isCollapsed) {
      clearToolbar()
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
      clearToolbar()
      return
    }

    if (!openSelectionAtRect(selectedText, range.getBoundingClientRect())) {
      clearToolbar()
    }
  }, [openSelectionAtRect, hasPanel])

  const handleAnswerClick = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      const target = (event.target as HTMLElement).closest('.proper-noun')
      if (target && answerRef.current?.contains(target)) {
        const text = target.textContent?.trim()
        if (text) openSelectionAtRect(text, target.getBoundingClientRect())
        return
      }
      // Otherwise it's a plain click in the answer (not on a proper noun). A
      // collapsed selection means no text was selected, so this counts as
      // "clicking outside the popup" and minimizes an open panel to its card.
      // This lives here rather than in the document mousedown handler because
      // that handler exempts the answer area (the whole document in the library
      // viewer) so that dragging to select text doesn't dismiss anything.
      const selectedNoText = window.getSelection()?.isCollapsed ?? true
      if (hasPanel && selectedNoText) {
        setIsMinimized(true)
      }
    },
    [openSelectionAtRect, hasPanel]
  )

  useEffect(() => {
    closeSelection()
  }, [resetKey, closeSelection])

  useEffect(() => {
    const handleMouseDown = (event: MouseEvent) => {
      const target = event.target as HTMLElement
      // Ignore clicks in any floating popup/card (incl. nested ones that portal
      // out of this subtree) and in this answer area — the latter is exempt so
      // text selection works; plain answer clicks minimize via the click handler.
      if (answerRef.current?.contains(target) || target.closest?.('[data-floating-popup]')) return
      // With a panel open, an outside click minimizes it to a side-rail card
      // (kept open, full close happens via the card); a bare toolbar just closes.
      if (hasPanel) {
        setIsMinimized(true)
        return
      }
      closeSelection()
    }
    // Escape fully closes (matching the panel's own close button), whether or
    // not a panel is open.
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeSelection()
    }
    document.addEventListener('mousedown', handleMouseDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleMouseDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [hasPanel, closeSelection])

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
        budget: _BUDGET_BALANCED,
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

  const selectionUi = selection ? (
    panel ? (
      <SelectionPanelFrame
        panel={panel}
        placement={selection.placement}
        top={selection.top}
        left={selection.left}
        fullscreen={isFullscreen}
        minimized={isMinimized}
        retrievePagePath={retrievePagePath}
        onClose={closeSelection}
        onRestore={() => setIsMinimized(false)}
        onToggleFullscreen={() => setIsFullscreen((value) => !value)}
      />
    ) : (
      // Portalled to body (like FloatingPanel) so the fixed toolbar escapes any
      // transformed/clipping ancestor when this panel is itself nested.
      createPortal(
        <div
          className={`${selStyles.toolbar} ${selStyles[`toolbar${selection.placement === 'above' ? 'Above' : 'Below'}`] || ''}`}
          style={{ top: `${selection.top}px`, left: `${selection.left}px` }}
          data-floating-popup
          onMouseDown={(event) => event.preventDefault()}
        >
          <Button variant="ghost" onClick={runKeywordSearch}>{t('library.selection.keywordSearch')}</Button>
          <Button variant="ghost" onClick={runAsk}>{t('library.selection.ask')}</Button>
        </div>,
        document.body
      )
    )
  ) : null

  return {
    answerRef,
    answerHandlers: { onMouseUp: captureSelection, onKeyUp: captureSelection, onClick: handleAnswerClick },
    selectionUi
  }
}

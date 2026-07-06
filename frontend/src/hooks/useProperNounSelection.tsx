import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useT, useTranslation } from '../contexts/LanguageContext'
import { usePopupRegistration } from '../contexts/PopupCoordinatorContext'
import { SelectionPanelFrame, type SelectionPanel } from '../components/SelectionPanel'
import Button from '../components/Button'
import selStyles from '../components/SelectionPanel.module.css'
import { useFloatingPanelState, useOutsidePointerDown } from './useFloatingPanelState'
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
 *
 * The bare toolbar and the search/ask panel are independent: a new selection
 * parks an open panel to its side-rail card rather than discarding it, so a
 * panel (e.g. an in-flight or completed ask) is only ever replaced by
 * explicitly running a new search/ask, or closed via its own close button.
 */
export function useProperNounSelection(resetKey: unknown): UseProperNounSelectionResult {
  const t = useT()
  const { language } = useTranslation()
  const answerRef = useRef<HTMLDivElement>(null)
  const activeRequestIdRef = useRef(0)
  const defaultModelRef = useRef<string | null>(null)
  const [selection, setSelection] = useState<{ text: string; rect: DOMRect } | null>(null)
  const [panel, setPanel] = useState<SelectionPanel | null>(null)
  const { position, minimized, fullscreen, openAtRect, minimize, restore, toggleFullscreen, reset } =
    useFloatingPanelState()
  // Whether a search/ask panel exists (open or minimized). Only flips on
  // open/close, so handlers below can depend on it directly (no re-subscribe
  // churn during answer streaming, which leaves it unchanged).
  const hasPanel = panel !== null

  // Fully dismiss the panel and cancel its in-flight request (Escape while the
  // panel is topmost, its close button, or its rail card's). The bare toolbar
  // is dismissed separately by clearing ``selection``, so tearing it down never
  // touches the panel or its request.
  const closePanel = useCallback(() => {
    setPanel(null)
    reset()
    activeRequestIdRef.current += 1
  }, [reset])
  const closeToolbar = useCallback(() => setSelection(null), [])
  // Tear down both when the underlying answer changes.
  const closeSelection = useCallback(() => {
    setSelection(null)
    closePanel()
  }, [closePanel])

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
    // Park an open panel to its rail card instead of discarding it — a new
    // selection must never destroy a search/ask result.
    if (hasPanel) minimize()
    setSelection({ text, rect })
    return true
  }, [hasPanel, minimize])

  const captureSelection = useCallback(() => {
    // A bare click (collapsed/invalid selection) dismisses only an unconfirmed
    // selection toolbar — never the panel, whose (open or minimized) state is
    // managed separately and survives clicks in the answer area.
    const clearToolbar = () => setSelection(null)
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

    const text = normalizeSelectionText(currentSelection.toString())
    if (!isEntityLikeSelection(text)) {
      clearToolbar()
      return
    }

    if (!openSelectionAtRect(text, range.getBoundingClientRect())) {
      clearToolbar()
    }
  }, [openSelectionAtRect])

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
      // This lives here rather than in the document pointerdown handler because
      // that handler exempts the answer area (the whole document in the library
      // viewer) so that dragging to select text doesn't dismiss anything.
      // Guard on DOM containment: popups and rail cards rendered by React
      // children of the answer (e.g. a citation popup's card) portal out of its
      // DOM but still bubble synthetic clicks here through the React tree, and
      // restoring such a card must not minimize this panel.
      const selectedNoText = window.getSelection()?.isCollapsed ?? true
      if (hasPanel && selectedNoText && answerRef.current?.contains(event.target as HTMLElement)) {
        minimize()
      }
    },
    [openSelectionAtRect, hasPanel, minimize]
  )

  useEffect(() => {
    closeSelection()
  }, [resetKey, closeSelection])

  // The answer area is exempt so text selection works; plain answer clicks
  // minimize via the click handler above. An outside click dismisses a bare
  // toolbar and minimizes an open panel to its side-rail card (kept open, full
  // close happens via the card); a minimized card survives outside clicks.
  const isAnswerTarget = useCallback(
    (target: HTMLElement) => answerRef.current?.contains(target) ?? false,
    []
  )
  useOutsidePointerDown(selection !== null, isAnswerTarget, closeToolbar)
  useOutsidePointerDown(hasPanel && !minimized, isAnswerTarget, minimize)

  // The bare toolbar holds its own coordinator registration (the panel's
  // FloatingPanel holds another for the panel's whole lifetime), so Escape
  // dismisses whichever is topmost and visible — a minimized panel is skipped,
  // so Escape aimed at the toolbar never dismisses a parked card.
  const { zIndex: toolbarZIndex } = usePopupRegistration({
    enabled: selection !== null,
    minimized: false,
    onClose: closeToolbar
  })

  const runKeywordSearch = async () => {
    if (!selection) return
    const query = selection.text
    openAtRect(selection.rect)
    setSelection(null)
    const requestId = activeRequestIdRef.current + 1
    activeRequestIdRef.current = requestId
    setPanel({ kind: 'search', query, loading: true, results: [], error: null })

    try {
      const reqBody: LibraryRetrieveRequest = {
        language: language.toUpperCase(),
        query,
        k: 10,
        semantic: false
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

  const librarySearchPath = (query: string) =>
    buildUrlWithLanguage('/library', `?q=${encodeURIComponent(query)}&semantic=0`, language)

  const runAsk = async () => {
    if (!selection) return
    const query = selection.text
    const question = language === 'chs' ? `“${query}”是什么？` : `What is “${query}”?`
    openAtRect(selection.rect)
    setSelection(null)
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

  const toolbarPosition = selection ? calculateFloatingPlacement(selection.rect) : null

  const selectionUi = (
    <>
      {panel && (
        <SelectionPanelFrame
          panel={panel}
          placement={position.placement}
          top={position.top}
          left={position.left}
          fullscreen={fullscreen}
          minimized={minimized}
          librarySearchPath={librarySearchPath}
          onClose={closePanel}
          onRestore={restore}
          onToggleFullscreen={toggleFullscreen}
        />
      )}
      {toolbarPosition &&
        // Portalled to body (like FloatingPanel) so the fixed toolbar escapes any
        // transformed/clipping ancestor when this panel is itself nested.
        createPortal(
          <div
            className={`${selStyles.toolbar} ${selStyles[`toolbar${toolbarPosition.placement === 'above' ? 'Above' : 'Below'}`] || ''}`}
            style={{ top: `${toolbarPosition.top}px`, left: `${toolbarPosition.left}px`, zIndex: toolbarZIndex }}
            data-floating-popup
            onMouseDown={(event) => event.preventDefault()}
          >
            <Button type="button" variant="ghost" onClick={runKeywordSearch}>{t('library.selection.keywordSearch')}</Button>
            <Button type="button" variant="ghost" onClick={runAsk}>{t('library.selection.ask')}</Button>
          </div>,
          document.body
        )}
    </>
  )

  return {
    answerRef,
    answerHandlers: { onMouseUp: captureSelection, onKeyUp: captureSelection, onClick: handleAnswerClick },
    selectionUi
  }
}

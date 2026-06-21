import { useT } from '../contexts/LanguageContext'
import { useProperNounSelection } from '../hooks/useProperNounSelection'
import type { LibraryRetrieveResponse, ProgressStepStart } from '../types/api'
import { buildLibraryFilePath } from '../utils/library'
import { AppLink } from './AppLink'
import CitationRenderer from './CitationRenderer'
import { FloatingPanel } from './FloatingPanel'
import QueryProgress from './QueryProgress'

export interface SelectionState {
  text: string
  top: number
  left: number
  placement: 'above' | 'below'
}

export type SelectionPanel =
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
      properNouns: string[]
      conversationUuid: string | null
      error: string | null
    }

interface SelectionPanelFrameProps {
  panel: SelectionPanel
  placement: SelectionState['placement']
  top: number
  left: number
  fullscreen: boolean
  minimized: boolean
  retrievePagePath: (query: string) => string
  onClose: () => void
  onRestore: () => void
  onToggleFullscreen: () => void
}

function RetrievalSelectionPanel({ panel }: { panel: Extract<SelectionPanel, { kind: 'search' }> }) {
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

function QuerySelectionPanel({ panel }: { panel: Extract<SelectionPanel, { kind: 'ask' }> }) {
  const t = useT()
  // Recurse: proper nouns highlighted inside this answer become clickable and
  // open their own nested selection panel, exactly like the page-level answer.
  const { answerRef, answerHandlers, selectionUi } = useProperNounSelection(panel.answer)

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
        <CitationRenderer content={panel.answer} properNouns={panel.properNouns}>
          {({ answer, citationList }) => (
            <>
              <div
                ref={answerRef}
                className="answer library-selection-answer"
                onMouseUp={answerHandlers.onMouseUp}
                onKeyUp={answerHandlers.onKeyUp}
                onClick={answerHandlers.onClick}
              >
                {answer}
              </div>
              {citationList && (
                <div className="library-selection-citations" data-citation-container>
                  {citationList}
                </div>
              )}
              {selectionUi}
            </>
          )}
        </CitationRenderer>
      )}
    </>
  )
}

export function SelectionPanelFrame({
  panel,
  placement,
  top,
  left,
  fullscreen,
  minimized,
  retrievePagePath,
  onClose,
  onRestore,
  onToggleFullscreen
}: SelectionPanelFrameProps) {
  const t = useT()
  const eyebrow = panel.kind === 'search' ? t('library.selection.keywordSearch') : t('library.selection.ask')
  const title = panel.kind === 'ask' ? panel.question : panel.query
  const topLink = panel.kind === 'search' ? (
    <AppLink className="floating-panel__top-link" to={retrievePagePath(panel.query)} target="_blank" rel="noopener noreferrer">
      {t('library.selection.openRetrieve')}
    </AppLink>
  ) : panel.kind === 'ask' && panel.conversationUuid ? (
    <AppLink className="floating-panel__top-link" to={`/conversation/${panel.conversationUuid}`} target="_blank" rel="noopener noreferrer">
      {t('library.selection.openConversation')}
    </AppLink>
  ) : null
  const panelBody = panel.kind === 'search'
    ? <RetrievalSelectionPanel panel={panel} />
    : <QuerySelectionPanel panel={panel} />

  return (
    <FloatingPanel
      placement={placement}
      top={top}
      left={left}
      fullscreen={fullscreen}
      minimized={minimized}
      onRestore={onRestore}
      onToggleFullscreen={onToggleFullscreen}
      eyebrow={eyebrow}
      title={title}
      topLink={topLink}
      onClose={onClose}
    >
      {panelBody}
    </FloatingPanel>
  )
}

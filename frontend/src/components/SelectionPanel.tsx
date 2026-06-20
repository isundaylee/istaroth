import { useT } from '../contexts/LanguageContext'
import type { LibraryRetrieveResponse, ProgressStepStart } from '../types/api'
import { buildLibraryFilePath } from '../utils/library'
import { AppLink } from './AppLink'
import CitationRenderer from './CitationRenderer'
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
  retrievePagePath: (query: string) => string
  onClose: () => void
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

export function SelectionPanelFrame({
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
            <AppLink className="library-selection-panel__top-link" to={retrievePagePath(panel.query)} target="_blank" rel="noopener noreferrer">
              {t('library.selection.openRetrieve')}
            </AppLink>
          )}
          {panel.kind === 'ask' && panel.conversationUuid && (
            <AppLink className="library-selection-panel__top-link" to={`/conversation/${panel.conversationUuid}`} target="_blank" rel="noopener noreferrer">
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

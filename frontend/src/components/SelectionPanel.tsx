import clsx from 'clsx'
import { useT } from '../contexts/LanguageContext'
import type { LibraryRetrieveResponse, ProgressStepStart } from '../types/api'
import { buildLibraryFilePath } from '../utils/library'
import { AppLink } from './AppLink'
import { FloatingPanel } from './FloatingPanel'
import panelStyles from './FloatingPanel.module.css'
import queryProgressStyles from './QueryProgress.module.css'
import Reader from './Reader'
import selStyles from './SelectionPanel.module.css'
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
  librarySearchPath: (query: string) => string
  onClose: () => void
  onRestore: () => void
  onToggleFullscreen: () => void
}

function RetrievalSelectionPanel({ panel }: { panel: Extract<SelectionPanel, { kind: 'search' }> }) {
  const t = useT()

  if (panel.loading) {
    return <p className={selStyles.muted}>{t('library.selection.searching')}</p>
  }
  if (panel.error) {
    return <p className={selStyles.error}>{panel.error}</p>
  }
  if (panel.results.length === 0) {
    return <p className={selStyles.muted}>{t('library.selection.noResults')}</p>
  }

  return (
    <div className={selStyles.results}>
      {panel.results.map((result) => (
        <div key={`${result.file_info.category}-${result.file_info.id}`} className={selStyles.result}>
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
        <p className={clsx(selStyles.muted, queryProgressStyles.loadingEllipsis)}>{t('query.submitting')}</p>
      )}
      {panel.loading && panel.activeSteps.length > 0 && (
        <QueryProgress steps={panel.activeSteps} className={selStyles.progress} />
      )}
      {panel.error && <p className={selStyles.error}>{panel.error}</p>}
      {panel.answer && (
        <Reader
          content={panel.answer}
          properNouns={panel.properNouns}
          citations
          resetKey={panel.answer}
          answerClassName={selStyles.answer}
          citationListClassName={selStyles.citations}
        />
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
  librarySearchPath,
  onClose,
  onRestore,
  onToggleFullscreen
}: SelectionPanelFrameProps) {
  const t = useT()
  const eyebrow = panel.kind === 'search' ? t('library.selection.keywordSearch') : t('library.selection.ask')
  const title = panel.kind === 'ask' ? panel.question : panel.query
  const topLink = panel.kind === 'search' ? (
    <AppLink className={panelStyles.topLink} to={librarySearchPath(panel.query)} target="_blank" rel="noopener noreferrer">
      {t('library.selection.openLibrarySearch')}
    </AppLink>
  ) : panel.kind === 'ask' && panel.conversationUuid ? (
    <AppLink className={panelStyles.topLink} to={`/conversation/${panel.conversationUuid}`} target="_blank" rel="noopener noreferrer">
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

import clsx from 'clsx'
import { createContext, useContext, type MouseEvent, type ReactNode, type RefObject } from 'react'
import { useProperNounSelection } from '../hooks/useProperNounSelection'
import CitationRenderer from './CitationRenderer'
import { PageSection } from './PageShell'
import styles from './Reader.module.css'

interface ReaderContextValue {
  answer: ReactNode
  citationList: ReactNode
  selectionUi: ReactNode
  answerRef: RefObject<HTMLDivElement>
  answerHandlers: {
    onMouseUp: () => void
    onKeyUp: () => void
    onClick: (event: MouseEvent<HTMLDivElement>) => void
  }
}

const ReaderContext = createContext<ReaderContextValue | null>(null)

function useReaderContext(): ReaderContextValue {
  const context = useContext(ReaderContext)
  if (!context) {
    throw new Error('Reader components must be rendered inside ReaderProvider')
  }
  return context
}

interface ReaderProviderProps {
  content: string
  properNouns?: string[]
  resetKey?: unknown
  children: ReactNode
}

export function ReaderProvider({ content, properNouns, resetKey = content, children }: ReaderProviderProps) {
  const { answerRef, answerHandlers, selectionUi } = useProperNounSelection(resetKey)

  return (
    <CitationRenderer content={content} properNouns={properNouns}>
      {({ answer, citationList }) => (
        <ReaderContext.Provider value={{ answer, citationList, selectionUi, answerRef, answerHandlers }}>
          {children}
        </ReaderContext.Provider>
      )}
    </CitationRenderer>
  )
}

interface ReaderProps {
  answerClassName?: string
}

function Reader({ answerClassName }: ReaderProps) {
  const { answer, selectionUi, answerRef, answerHandlers } = useReaderContext()

  return (
    <div className={styles.root}>
      <div
        ref={answerRef}
        className={clsx('answer', answerClassName)}
        onMouseUp={answerHandlers.onMouseUp}
        onKeyUp={answerHandlers.onKeyUp}
        onClick={answerHandlers.onClick}
      >
        {answer}
      </div>
      {selectionUi}
    </div>
  )
}

interface ReaderCitationListProps {
  className?: string
  sectioned?: boolean
}

export function ReaderCitationList({ className, sectioned = false }: ReaderCitationListProps) {
  const { citationList } = useReaderContext()

  if (!citationList) return null

  return (
    <div
      data-citation-container
      className={clsx(!sectioned && styles.citations, className)}
    >
      {sectioned ? <PageSection>{citationList}</PageSection> : citationList}
    </div>
  )
}

export default Reader

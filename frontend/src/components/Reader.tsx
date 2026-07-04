import clsx from 'clsx'
import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'
import { useMemo, type ReactNode } from 'react'
import { useProperNounSelection } from '../hooks/useProperNounSelection'
import { buildProperNounMatcher } from '../utils/properNouns'
import { rehypeProperNouns } from '../utils/rehypeProperNouns'
import CitationRenderer from './CitationRenderer'
import { PageSection } from './PageShell'
import styles from './Reader.module.css'

interface ReaderProps {
  content: string
  properNouns?: string[]
  citations?: boolean
  gfm?: boolean
  resetKey?: unknown
  answerClassName?: string
  title?: ReactNode
  actions?: ReactNode
  beforeAnswer?: ReactNode
  sectioned?: boolean
  citationListClassName?: string
}

function Reader({
  content,
  properNouns,
  citations = false,
  gfm = false,
  resetKey = content,
  answerClassName,
  title,
  actions,
  beforeAnswer,
  sectioned = false,
  citationListClassName
}: ReaderProps) {
  const { answerRef, answerHandlers, selectionUi } = useProperNounSelection(resetKey)
  const properNounMatcher = useMemo(
    () => (!citations && properNouns && properNouns.length > 0 ? buildProperNounMatcher(properNouns) : null),
    [citations, properNouns]
  )
  const remarkPlugins = gfm ? [remarkGfm, remarkBreaks] : [remarkBreaks]
  const render = ({ answer, citationList }: { answer: ReactNode; citationList: ReactNode }) => {
    const header = (title || actions) && (
      <div className={styles.header}>
        {title && <h3>{title}</h3>}
        {actions && <div className={styles.actions}>{actions}</div>}
      </div>
    )
    const answerBlock = (
      <>
        {header}
        {beforeAnswer}
        <div
          ref={answerRef}
          className={clsx('answer', answerClassName)}
          onMouseUp={answerHandlers.onMouseUp}
          onKeyUp={answerHandlers.onKeyUp}
          onClick={answerHandlers.onClick}
        >
          {answer}
        </div>
      </>
    )
    return (
      <div className={styles.root}>
        {sectioned ? <PageSection>{answerBlock}</PageSection> : answerBlock}
        {citationList && (
          <div
            data-citation-container
            className={clsx(!sectioned && styles.citations, citationListClassName)}
          >
            {sectioned ? <PageSection>{citationList}</PageSection> : citationList}
          </div>
        )}
        {selectionUi}
      </div>
    )
  }

  if (citations) {
    return (
      <CitationRenderer content={content} properNouns={properNouns}>
        {({ answer, citationList }) => render({ answer, citationList })}
      </CitationRenderer>
    )
  }

  return render({
    answer: (
      <ReactMarkdown
        remarkPlugins={remarkPlugins}
        rehypePlugins={properNounMatcher ? [rehypeProperNouns(properNounMatcher)] : []}
      >
        {content}
      </ReactMarkdown>
    ),
    citationList: null
  })
}

export default Reader

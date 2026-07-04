import clsx from 'clsx'
import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'
import { useMemo, type MouseEvent, type ReactNode, type RefObject } from 'react'
import { useProperNounSelection } from '../hooks/useProperNounSelection'
import { buildProperNounMatcher } from '../utils/properNouns'
import { rehypeProperNouns } from '../utils/rehypeProperNouns'
import CitationRenderer from './CitationRenderer'

interface ReaderRenderProps {
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

interface ReaderProps {
  content: string
  properNouns?: string[]
  citations?: boolean
  gfm?: boolean
  resetKey?: unknown
  answerClassName?: string
  children?: (props: ReaderRenderProps) => ReactNode
}

function Reader({
  content,
  properNouns,
  citations = false,
  gfm = false,
  resetKey = content,
  answerClassName,
  children
}: ReaderProps) {
  const { answerRef, answerHandlers, selectionUi } = useProperNounSelection(resetKey)
  const properNounMatcher = useMemo(
    () => (!citations && properNouns && properNouns.length > 0 ? buildProperNounMatcher(properNouns) : null),
    [citations, properNouns]
  )
  const remarkPlugins = gfm ? [remarkGfm, remarkBreaks] : [remarkBreaks]
  const defaultRender = ({ answer, citationList }: { answer: ReactNode; citationList: ReactNode }) => (
    <div style={{ position: 'relative' }}>
      <div
        ref={answerRef}
        className={clsx('answer', answerClassName)}
        onMouseUp={answerHandlers.onMouseUp}
        onKeyUp={answerHandlers.onKeyUp}
        onClick={answerHandlers.onClick}
      >
        {answer}
      </div>
      {citationList && (
        <div
          data-citation-container
          style={{
            marginTop: '1rem',
            paddingTop: '0.75rem',
            borderTop: '1px solid var(--color-border-divider)'
          }}
        >
          {citationList}
        </div>
      )}
      {selectionUi}
    </div>
  )
  const render = ({ answer, citationList }: { answer: ReactNode; citationList: ReactNode }) =>
    children
      ? children({ answer, citationList, selectionUi, answerRef, answerHandlers })
      : defaultRender({ answer, citationList })

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

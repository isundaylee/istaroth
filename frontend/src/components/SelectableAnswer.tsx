import clsx from 'clsx'
import type { ReactNode } from 'react'
import { useProperNounSelection } from '../hooks/useProperNounSelection'

interface SelectableAnswerProps {
  /** Content identity (e.g. conversation uuid); the selection clears when it changes. */
  resetKey: unknown
  className?: string
  children: ReactNode
}

/**
 * Answer container wired for proper-noun selection: selecting text (or clicking
 * a highlighted proper noun) inside it opens the search/ask toolbar. The
 * selection UI portals to body / the minimized rail, so it can be rendered
 * adjacent to the container.
 */
function SelectableAnswer({ resetKey, className, children }: SelectableAnswerProps) {
  const { answerRef, answerHandlers, selectionUi } = useProperNounSelection(resetKey)

  return (
    <>
      <div ref={answerRef} className={clsx('answer', className)} {...answerHandlers}>
        {children}
      </div>
      {selectionUi}
    </>
  )
}

export default SelectableAnswer

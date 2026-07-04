import type { ReactNode } from 'react'
import { useProperNounSelection } from '../hooks/useProperNounSelection'
import clsx from 'clsx'

interface Props {
  resetKey: unknown
  className?: string
  children: ReactNode
}

/**
 * Wraps ``useProperNounSelection`` and owns the boilerplate: the answer
 * container div with selection/click handlers, plus the portalled selection UI
 * (toolbar and search/ask panel). Replaces three identical copies across
 * ConversationPage, LibraryFileViewer, and SelectionPanel.
 */
export function SelectableAnswer({ resetKey, className, children }: Props) {
  const { answerRef, answerHandlers, selectionUi } = useProperNounSelection(resetKey)

  return (
    <>
      <div
        ref={answerRef}
        className={clsx('answer', className)}
        onMouseUp={answerHandlers.onMouseUp}
        onKeyUp={answerHandlers.onKeyUp}
        onClick={answerHandlers.onClick}
      >{children}</div>
      {selectionUi}
    </>
  )
}

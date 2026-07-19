import type { ReactNode } from 'react'
import { PageSection } from './PageShell'
import CitedAnswer from './CitedAnswer'
import { MinimizedPopupRegion } from '../contexts/PopupCoordinatorContext'
import styles from './ConversationAnswer.module.css'

interface ConversationAnswerProps {
  answer: string
  properNouns: string[]
  /**
   * Share/export controls; floated into the first line of the answer. Omitted
   * while streaming (those affordances need a saved conversation).
   */
  actions?: ReactNode
  /** The exported-PNG preview block (omit while streaming). */
  exportImage?: ReactNode
}

/**
 * The canonical conversation answer view: cited answer and citation list.
 * Shared by the saved conversation page and the mid-stream state so the two
 * are visually identical. ``CitedAnswer`` trims any trailing partial citation
 * tag itself, so a still-streaming ``answer`` renders cleanly without this
 * component needing to know it is streaming.
 */
function ConversationAnswer({ answer, properNouns, actions, exportImage }: ConversationAnswerProps) {
  return (
    <MinimizedPopupRegion className={styles.content} data-conversation-content>
      <CitedAnswer content={answer} properNouns={properNouns}>
        {({ answer: renderedAnswer, citationList }) => (
          <>
            <PageSection>
              {exportImage}

              <div className={styles.answerBlock}>
                {actions && <div className={styles.actions}>{actions}</div>}
                {renderedAnswer}
              </div>
            </PageSection>

            {citationList && (
              <div data-citation-container>
                <PageSection>{citationList}</PageSection>
              </div>
            )}
          </>
        )}
      </CitedAnswer>
    </MinimizedPopupRegion>
  )
}

export default ConversationAnswer

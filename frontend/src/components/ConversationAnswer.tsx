import type { ReactNode } from 'react'
import { useT } from '../contexts/LanguageContext'
import { PageSection } from './PageShell'
import CitedAnswer from './CitedAnswer'
import { MinimizedPopupRegion } from '../contexts/PopupCoordinatorContext'
import styles from './ConversationAnswer.module.css'

interface ConversationAnswerProps {
  answer: string
  properNouns: string[]
  /**
   * Share/export controls; rendered next to the heading. Omitted while the
   * answer is streaming (those affordances need a saved conversation).
   */
  actions?: ReactNode
  /** The exported-PNG preview block (omit while streaming). */
  exportImage?: ReactNode
}

/**
 * The canonical conversation answer view: heading row, cited answer, and
 * citation list. Shared by the saved conversation page and the mid-stream
 * state so the two are visually identical. ``CitedAnswer`` trims any trailing
 * partial citation tag itself, so a still-streaming ``answer`` renders cleanly
 * without this component needing to know it is streaming.
 */
function ConversationAnswer({ answer, properNouns, actions, exportImage }: ConversationAnswerProps) {
  const t = useT()

  return (
    <MinimizedPopupRegion className={styles.content} data-conversation-content>
      <CitedAnswer content={answer} properNouns={properNouns}>
        {({ answer: renderedAnswer, citationList }) => (
          <>
            <PageSection>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <h3>{t('conversation.answer')}</h3>
                {actions && <div style={{ display: 'flex', gap: '0.5rem' }}>{actions}</div>}
              </div>

              {exportImage}

              {renderedAnswer}
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

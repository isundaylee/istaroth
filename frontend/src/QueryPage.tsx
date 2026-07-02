import { useEffect, useRef, useState } from 'react'
import { useT, useTranslation } from './contexts/LanguageContext'
import QueryForm, { type QueryFormHandle } from './QueryForm'
import PageShell, { PageSection } from './components/PageShell'
import IstarothFigure from './components/IstarothFigure'
import QueryProgress from './components/QueryProgress'
import type { ProgressStepStart } from './types/api'
import styles from './QueryPage.module.css'

// Fixed star positions for the hero's dark-theme starfield (viewBox 1000×640).
// Hand-placed to ring the character (center-bottom stays clear) — no runtime
// randomness, so the sky is stable across renders.
const SPARKLES: Array<{ x: number; y: number; r: number; slow?: boolean }> = [
  { x: 76, y: 88, r: 7 },
  { x: 178, y: 210, r: 5, slow: true },
  { x: 120, y: 388, r: 8 },
  { x: 62, y: 540, r: 5, slow: true },
  { x: 262, y: 500, r: 4 },
  { x: 310, y: 96, r: 4, slow: true },
  { x: 235, y: 305, r: 3 },
  { x: 700, y: 120, r: 5 },
  { x: 785, y: 300, r: 8, slow: true },
  { x: 872, y: 90, r: 5 },
  { x: 930, y: 245, r: 4 },
  { x: 950, y: 470, r: 7, slow: true },
  { x: 838, y: 560, r: 5 },
  { x: 745, y: 460, r: 3, slow: true },
  { x: 480, y: 60, r: 4 },
  { x: 590, y: 150, r: 3, slow: true },
]

const DOTS: Array<{ x: number; y: number; r: number }> = [
  { x: 145, y: 140, r: 2 },
  { x: 45, y: 300, r: 1.6 },
  { x: 210, y: 430, r: 2.2 },
  { x: 320, y: 220, r: 1.4 },
  { x: 170, y: 560, r: 1.6 },
  { x: 660, y: 70, r: 1.6 },
  { x: 760, y: 200, r: 2.2 },
  { x: 905, y: 160, r: 1.4 },
  { x: 855, y: 400, r: 2 },
  { x: 700, y: 560, r: 1.8 },
  { x: 975, y: 350, r: 1.5 },
  { x: 545, y: 100, r: 1.8 },
]

// Four-point sparkle (✦): four quadratic curves pinched through the center.
const sparklePath = ({ x, y, r }: { x: number; y: number; r: number }) =>
  `M ${x} ${y - r} Q ${x} ${y} ${x + r} ${y} Q ${x} ${y} ${x} ${y + r} Q ${x} ${y} ${x - r} ${y} Q ${x} ${y} ${x} ${y - r} Z`

function StarField() {
  return (
    <svg
      className={styles.starfield}
      viewBox="0 0 1000 640"
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
    >
      {SPARKLES.map((s) => (
        <path
          key={`${s.x}-${s.y}`}
          d={sparklePath(s)}
          fill="var(--color-primary-fill)"
          className={s.slow ? styles.starSlow : styles.star}
        />
      ))}
      {DOTS.map((d) => (
        <circle
          key={`${d.x}-${d.y}`}
          cx={d.x}
          cy={d.y}
          r={d.r}
          fill="var(--color-primary-fill)"
          className={styles.starSlow}
        />
      ))}
    </svg>
  )
}

function QueryPage() {
  const t = useT()
  const { language } = useTranslation()
  const [question, setQuestion] = useState('')
  const [exampleQuestion, setExampleQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [activeSteps, setActiveSteps] = useState<ProgressStepStart[]>([])
  const formRef = useRef<QueryFormHandle>(null)

  useEffect(() => {
    setExampleQuestion('')
  }, [language])

  return (
    <PageShell flush>
      <div className={styles.stage}>
      <PageSection className={styles.hero}>
        <StarField />
        <IstarothFigure
          pose={loading ? 'think' : 'greet'}
          label={t('query.hero.figureAlt')}
          className={styles.figure}
          bubble={
            !loading ? (
              <button
                type="button"
                className={styles.bubble}
                disabled={!exampleQuestion}
                onClick={() => {
                  setQuestion(exampleQuestion)
                  formRef.current?.submit()
                }}
              >
                <span className={styles.bubbleGreeting}>{t('query.hero.greeting')}</span>
                <span className={styles.bubbleQuestion}>
                  {exampleQuestion
                    ? `${t('query.hero.tryAsking')}${exampleQuestion}`
                    : t('query.exampleLoading')}
                </span>
              </button>
            ) : undefined
          }
          status={
            loading ? (
              <div className={styles.thinkingStatus}>
                <span className={styles.thinkingCaption}>
                  {t('query.hero.thinking')}
                </span>
                {activeSteps.length > 0 && (
                  <QueryProgress steps={activeSteps} className={styles.thinkingSteps} />
                )}
              </div>
            ) : undefined
          }
        />
      </PageSection>

      <PageSection>
        <QueryForm
          ref={formRef}
          question={question}
          onQuestionChange={setQuestion}
          onExampleChange={setExampleQuestion}
          onLoadingChange={setLoading}
          onActiveStepsChange={setActiveSteps}
          hideProgress
        />
      </PageSection>
      </div>
    </PageShell>
  )
}

export default QueryPage

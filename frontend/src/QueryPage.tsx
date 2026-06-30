import { useT } from './contexts/LanguageContext'
import QueryForm from './QueryForm'
import Navigation from './components/Navigation'
import styles from './QueryPage.module.css'

// The clock dial cradling the Istaroth avatar — the God of Time, and a visual
// pun on a knowledge base that has every legend "indexed". The avatar PNG is
// clipped to a circle so only the round portrait shows (not its wordmark tile);
// the tick ring lives in its own group so it can rotate slowly behind the face.
const DIAL_TICK_OUTER = 173

function Dial({ label }: { label: string }) {
  const ticks = Array.from({ length: 60 }, (_, i) => {
    const cardinal = i % 15 === 0
    const major = i % 5 === 0
    return {
      angle: i * 6,
      inner: cardinal ? 148 : major ? 155 : 161,
      width: cardinal ? 2 : 1,
      opacity: cardinal ? 0.85 : major ? 0.5 : 0.28,
    }
  })

  return (
    <svg className={styles.dial} viewBox="0 0 400 400" role="img" aria-label={label}>
      <defs>
        <clipPath id="dial-avatar">
          <circle cx="200" cy="200" r="102" />
        </clipPath>
      </defs>

      <circle cx="200" cy="200" r="181" fill="none" stroke="var(--figure-line)" strokeWidth="1" />
      <circle cx="200" cy="200" r="117" fill="none" stroke="var(--figure-line)" strokeWidth="1" />

      <g className={styles.dialTicks}>
        {ticks.map((tick) => (
          <line
            key={tick.angle}
            x1="200"
            y1={200 - DIAL_TICK_OUTER}
            x2="200"
            y2={200 - tick.inner}
            stroke="var(--figure-gold)"
            strokeWidth={tick.width}
            strokeOpacity={tick.opacity}
            strokeLinecap="round"
            transform={`rotate(${tick.angle} 200 200)`}
          />
        ))}
      </g>

      <g className={styles.dialNumerals}>
        <text x="200" y="74" textAnchor="middle">XII</text>
        <text x="331" y="205" textAnchor="middle">III</text>
        <text x="200" y="338" textAnchor="middle">VI</text>
        <text x="69" y="205" textAnchor="middle">IX</text>
      </g>

      <circle cx="200" cy="200" r="106" fill="var(--figure-ink)" stroke="var(--figure-gold-dim)" strokeWidth="1.5" />
      <image
        href="/istaroth-logo.png"
        x="44"
        y="65"
        width="312"
        height="312"
        clipPath="url(#dial-avatar)"
        preserveAspectRatio="xMidYMid slice"
      />
    </svg>
  )
}

function QueryPage() {
  const t = useT()

  return (
    <main className="main">
      <div className={styles.panel}>
        <Navigation embedded />

        <div className={styles.stage}>
          <div className={styles.composerSection}>
            <QueryForm />
          </div>

          <div className={styles.heroSection}>
            <div className={styles.heroText}>
              <h1 className={styles.introTitle}>{t('query.title')}</h1>
              <p className={styles.introText}>{t('meta.description')}</p>
              <a
                href="https://github.com/isundaylee/istaroth"
                target="_blank"
                rel="noopener noreferrer"
                className={styles.figureGithub}
              >
                <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
                </svg>
                {t('meta.githubLink')}
              </a>
            </div>

            <div className={styles.heroFigure}>
              <Dial label={t('query.title')} />
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}

export default QueryPage

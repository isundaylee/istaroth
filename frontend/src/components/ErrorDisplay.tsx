import { useT } from '../contexts/LanguageContext'
import Navigation from './Navigation'
import styles from './ErrorDisplay.module.css'

/** Full-page error view for route-level failures (see ErrorBoundary).
 * Transient operation errors go through useErrorToast instead. */
function ErrorDisplay({ error }: { error: string }) {
  const t = useT()

  return (
    <>
      <Navigation />
      <div className={styles.error}>
        <h3>{t('common.error')}</h3>
        <p>{error}</p>
      </div>
    </>
  )
}

export default ErrorDisplay

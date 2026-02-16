import { useT } from '../contexts/LanguageContext'
import Navigation from './Navigation'

interface ErrorDisplayProps {
  error: string
  fullPage?: boolean
}

function ErrorDisplay({
  error,
  fullPage = false
}: ErrorDisplayProps) {
  const t = useT()

  const errorContent = (
    <div className="error">
      <h3>{t('common.error')}</h3>
      <p>{error}</p>
    </div>
  )

  if (fullPage) {
    return (
      <>
        <Navigation />
        <main className="main">
          {errorContent}
        </main>
      </>
    )
  }

  return errorContent
}

export default ErrorDisplay

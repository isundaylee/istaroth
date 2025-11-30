import { Link } from 'react-router-dom'
import { useT } from '../contexts/LanguageContext'
import Navigation from './Navigation'

interface ErrorDisplayProps {
  error: string
  fullPage?: boolean
  showBackLink?: boolean
  backLinkTo?: string
}

function ErrorDisplay({
  error,
  fullPage = false,
  showBackLink = false,
  backLinkTo = '/'
}: ErrorDisplayProps) {
  const t = useT()

  const errorContent = (
    <div className="error">
      <h3>{t('common.error')}</h3>
      <p>{error}</p>
      {showBackLink && (
        <Link to={backLinkTo} className="back-link">
          {t('common.back')}
        </Link>
      )}
    </div>
  )

  if (fullPage) {
    return (
      <div className="app">
        <Navigation />
        <main className="main">
          {errorContent}
        </main>
      </div>
    )
  }

  return errorContent
}

export default ErrorDisplay

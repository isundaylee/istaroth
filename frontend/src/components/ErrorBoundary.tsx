import { useRouteError, isRouteErrorResponse } from 'react-router-dom'
import { LanguageProvider, useT } from '../contexts/LanguageContext'
import ErrorDisplay from './ErrorDisplay'

function ErrorBoundaryContent() {
  const error = useRouteError()
  const t = useT()

  let message = t('common.unexpectedError')

  if (isRouteErrorResponse(error)) {
    message = typeof error.data === 'string' ? error.data : error.statusText || message
  } else if (error instanceof Error) {
    message = error.message
  } else if (typeof error === 'string') {
    message = error
  }

  return <ErrorDisplay error={message} fullPage={true} />
}

function ErrorBoundary() {
  return (
    <LanguageProvider>
      <ErrorBoundaryContent />
    </LanguageProvider>
  )
}

export default ErrorBoundary

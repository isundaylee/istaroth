import { useRouteError, isRouteErrorResponse } from 'react-router-dom'
import { LanguageProvider } from '../contexts/LanguageContext'
import ErrorDisplay from './ErrorDisplay'

function ErrorBoundaryContent() {
  const error = useRouteError()

  let message = 'An unexpected error occurred'

  if (isRouteErrorResponse(error)) {
    message = typeof error.data === 'string' ? error.data : error.statusText || message
  } else if (error instanceof Error) {
    message = error.message
  } else if (typeof error === 'string') {
    message = error
  }

  return <ErrorDisplay error={message} fullPage={true} showBackLink={true} />
}

function ErrorBoundary() {
  return (
    <LanguageProvider>
      <ErrorBoundaryContent />
    </LanguageProvider>
  )
}

export default ErrorBoundary

import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useT, useTranslation } from './contexts/LanguageContext'
import { AppLink } from './components/AppLink'
import Navigation from './components/Navigation'
import PageCard from './components/PageCard'
import Card from './components/Card'
import ErrorDisplay from './components/ErrorDisplay'
import { buildLibraryFilePath } from './utils/library'
import type { LibraryRetrieveRequest, LibraryRetrieveResponse } from './types/api'

const QUERY_PARAM = 'q'

const escapeRegExp = (value: string): string =>
  value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const highlightSnippet = (snippet: string, query: string): React.ReactNode => {
  const tokens = Array.from(new Set(query.split(/\s+/).map((token) => token.trim()).filter(Boolean)))
  if (tokens.length === 0) {
    return snippet
  }

  const escapedTokens = tokens.map(escapeRegExp).join('|')
  const splitRegex = new RegExp(`(${escapedTokens})`, 'gi')
  const matchRegex = new RegExp(`^(${escapedTokens})$`, 'i')

  return snippet.split(splitRegex).map((part, index) => (
    matchRegex.test(part)
      ? (
        <span
          key={`${part}-${index}`}
          style={{ backgroundColor: 'rgba(52, 152, 219, 0.50)' }}
        >
          {part}
        </span>
      )
      : part
  ))
}

function RetrievePage() {
  const t = useT()
  const { language } = useTranslation()
  const location = useLocation()
  const [query, setQuery] = useState('')
  const [submittedQuery, setSubmittedQuery] = useState<string | null>(null)
  const [initialQuerySubmitted, setInitialQuerySubmitted] = useState(false)
  const [results, setResults] = useState<LibraryRetrieveResponse['results']>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const activeRequestIdRef = useRef(0)

  const urlQuery = useMemo(() => {
    const params = new URLSearchParams(location.search)
    return params.get(QUERY_PARAM)
  }, [location.search])

  const runSearch = async (value: string) => {
    const trimmed = value.trim()
    if (!trimmed) return

    setLoading(true)
    setError(null)
    const requestId = activeRequestIdRef.current + 1
    activeRequestIdRef.current = requestId
    setSubmittedQuery(trimmed)

    try {
      const reqBody: LibraryRetrieveRequest = {
        language: language.toUpperCase(),
        query: trimmed,
        k: 10
      }
      const res = await fetch('/api/library/retrieve', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(reqBody)
      })
      const data = await res.json()
      if (res.ok) {
        const response = data as LibraryRetrieveResponse
        if (activeRequestIdRef.current === requestId) {
          setResults(response.results)
        }
      } else {
        if (activeRequestIdRef.current === requestId) {
          setError((data as { error?: string }).error || t('retrieve.errors.unknown'))
        }
      }
    } catch (err) {
      if (activeRequestIdRef.current === requestId) {
        setError(t('retrieve.errors.noConnection'))
      }
    } finally {
      if (activeRequestIdRef.current === requestId) {
        setLoading(false)
      }
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = query.trim()
    if (!trimmed) return

    if (trimmed === submittedQuery) {
      return
    }

    const params = new URLSearchParams(location.search)
    params.set(QUERY_PARAM, trimmed)
    const nextUrl = buildUrlWithLanguage(location.pathname, `?${params.toString()}`, language)
    window.history.replaceState(null, '', nextUrl)
    await runSearch(trimmed)
  }

  useEffect(() => {
    if (initialQuerySubmitted) {
      return
    }
    if (loading) {
      return
    }
    if (!urlQuery) {
      activeRequestIdRef.current += 1
      setResults([])
      setError(null)
      setInitialQuerySubmitted(true)
      return
    }
    setQuery(urlQuery)
    setSubmittedQuery(urlQuery)
    setInitialQuerySubmitted(true)
    runSearch(urlQuery)
  }, [urlQuery, language, loading, initialQuerySubmitted])

  const resultsContent = useMemo(() => {
    if (!submittedQuery) {
      return null
    }
    if (results.length === 0) {
      return (
        <Card style={{ marginTop: '1rem' }}>
          <p>{t('retrieve.noResults')}</p>
        </Card>
      )
    }
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginTop: '1rem' }}>
        {results.map((result) => {
          const linkPath = buildLibraryFilePath(result.file_info)
          return (
            <Card key={`${result.file_info.category}-${result.file_info.id}`} style={{ margin: 0 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <AppLink
                  to={linkPath}
                  style={{
                    fontSize: '1.1rem',
                    fontWeight: 600,
                    color: '#2c3e50',
                    textDecoration: 'none'
                  }}
                >
                  {result.file_info.title || t('library.noFileName')}
                </AppLink>
                <p style={{ margin: 0, color: '#5a6c7d', lineHeight: '1.6' }}>
                  {highlightSnippet(result.snippet, submittedQuery ?? '')}
                </p>
              </div>
            </Card>
          )
        })}
      </div>
    )
  }, [results, urlQuery, location.search, language, t])

  return (
    <div className="app">
      <Navigation />
      <main className="main">
        <PageCard>
          <h1 style={{ marginBottom: '1.5rem', textAlign: 'center', fontSize: '2.2rem', color: '#2c3e50' }}>
            {t('retrieve.title')}
          </h1>
          <form onSubmit={handleSubmit} className="query-form">
            <div className="input-row">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t('retrieve.placeholder')}
                disabled={loading}
                className="question-input"
              />
              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="submit-button"
              >
                {loading ? t('retrieve.submitting') : t('retrieve.submitButton')}
              </button>
            </div>
          </form>

          {error && <ErrorDisplay error={error} />}
          {resultsContent}
        </PageCard>
      </main>
    </div>
  )
}

export default RetrievePage

import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useT, useTranslation } from './contexts/LanguageContext'
import { AppLink } from './components/AppLink'
import Navigation from './components/Navigation'
import PageCard from './components/PageCard'
import Card from './components/Card'
import Button from './components/Button'
import Composer from './components/Composer'
import ErrorDisplay from './components/ErrorDisplay'
import styles from './RetrievePage.module.css'
import { buildUrlWithLanguage } from './utils/language'
import { buildLibraryFilePath } from './utils/library'
import type { LibraryRetrieveRequest, LibraryRetrieveResponse } from './types/api'

const QUERY_PARAM = 'q'
const SEMANTIC_PARAM = 'semantic'

interface SearchParams {
  query: string
  semantic: boolean
}

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
          style={{ backgroundColor: 'var(--color-highlight-bg)' }}
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
  const [formParams, setFormParams] = useState<SearchParams>({ query: '', semantic: false })
  const [submittedParams, setSubmittedParams] = useState<SearchParams | null>(null)
  const [initialQuerySubmitted, setInitialQuerySubmitted] = useState(false)
  const [results, setResults] = useState<LibraryRetrieveResponse['results']>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const activeRequestIdRef = useRef(0)

  const urlParams = useMemo((): SearchParams => {
    const params = new URLSearchParams(location.search)
    return {
      query: params.get(QUERY_PARAM) ?? '',
      semantic: params.get(SEMANTIC_PARAM) === '1'
    }
  }, [location.search])

  const writeParamsToUrl = (params: SearchParams) => {
    const urlSearchParams = new URLSearchParams(location.search)
    urlSearchParams.set(QUERY_PARAM, params.query)
    urlSearchParams.set(SEMANTIC_PARAM, params.semantic ? '1' : '0')
    const nextUrl = buildUrlWithLanguage(location.pathname, `?${urlSearchParams.toString()}`, language)
    window.history.replaceState(null, '', nextUrl)
  }

  const runSearch = async (params: SearchParams) => {
    const trimmed = params.query.trim()
    if (!trimmed) return

    setLoading(true)
    setError(null)
    const requestId = activeRequestIdRef.current + 1
    activeRequestIdRef.current = requestId
    setSubmittedParams({ query: trimmed, semantic: params.semantic })

    try {
      const reqBody: LibraryRetrieveRequest = {
        language: language.toUpperCase(),
        query: trimmed,
        k: 10,
        semantic: params.semantic,
        chunk_context: 0
      }
      const res = await fetch('/api/library/retrieve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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

  const handleSubmit = async () => {
    const params: SearchParams = { query: formParams.query.trim(), semantic: formParams.semantic }
    if (!params.query || (params.query === submittedParams?.query && params.semantic === submittedParams?.semantic)) return

    writeParamsToUrl(params)
    await runSearch(params)
  }

  useEffect(() => {
    if (initialQuerySubmitted) return
    if (loading) return
    if (!urlParams.query) {
      activeRequestIdRef.current += 1
      setResults([])
      setError(null)
      setInitialQuerySubmitted(true)
      return
    }
    setFormParams(urlParams)
    setInitialQuerySubmitted(true)
    runSearch(urlParams)
  }, [initialQuerySubmitted, loading])

  const resultsContent = useMemo(() => {
    if (!submittedParams || loading) return null
    if (results.length === 0) {
      return (
        <Card style={{ margin: 0 }}>
          <p>{t('retrieve.noResults')}</p>
        </Card>
      )
    }
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {results.map((result) => {
          const linkPath = buildLibraryFilePath(result.file_info)
          return (
            <Card key={`${result.file_info.category}-${result.file_info.id}`} style={{ margin: 0 }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <AppLink
                  to={linkPath}
                  style={{
                    fontSize: 'var(--font-base)',
                    fontWeight: 600,
                    color: 'var(--color-heading)',
                    textDecoration: 'none'
                  }}
                >
                  {result.file_info.title || t('library.noFileName')}
                </AppLink>
                <p style={{ margin: 0, color: 'var(--color-text-subtle)', lineHeight: '1.6' }}>
                  {highlightSnippet(result.snippet, submittedParams.query)}
                </p>
              </div>
            </Card>
          )
        })}
      </div>
    )
  }, [results, submittedParams, loading, language, t])

  return (
    <>
      <Navigation />
      <main className="main">
        <Composer
          submitOnEnter
          value={formParams.query}
          onChange={(query) => setFormParams({ ...formParams, query })}
          onSubmit={handleSubmit}
          placeholder={t('retrieve.placeholder')}
          disabled={loading}
          controls={
            <div className={styles.searchMode} role="group" aria-label={t('retrieve.searchMode')}>
              <button
                type="button"
                className={formParams.semantic ? '' : styles.isActive}
                aria-pressed={!formParams.semantic}
                onClick={() => setFormParams({ ...formParams, semantic: false })}
                disabled={loading}
              >
                {t('retrieve.searchModeBm25')}
              </button>
              <button
                type="button"
                className={formParams.semantic ? styles.isActive : ''}
                aria-pressed={formParams.semantic}
                onClick={() => setFormParams({ ...formParams, semantic: true })}
                disabled={loading}
              >
                {t('retrieve.searchModeSemantic')}
              </button>
            </div>
          }
          actions={
            <Button
              type="submit"
              className="query-submit-button"
              disabled={loading || !formParams.query.trim() || (formParams.query.trim() === submittedParams?.query && formParams.semantic === submittedParams?.semantic)}
            >
              {loading ? t('retrieve.submitting') : t('retrieve.submitButton')}
            </Button>
          }
        />

        {error && <ErrorDisplay error={error} />}
        {resultsContent && <PageCard>{resultsContent}</PageCard>}
      </main>
    </>
  )
}

export default RetrievePage

import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useT, useTranslation } from './contexts/LanguageContext'
import { AppLink } from './components/AppLink'
import Navigation from './components/Navigation'
import PageCard from './components/PageCard'
import PageTitle from './components/PageTitle'
import Card from './components/Card'
import TextInput from './components/TextInput'
import Button from './components/Button'
import ErrorDisplay from './components/ErrorDisplay'
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
    const params: SearchParams = { query: formParams.query.trim(), semantic: formParams.semantic }
    if (!params.query || (params.query === submittedParams?.query && params.semantic === submittedParams?.semantic)) return

    writeParamsToUrl(params)
    await runSearch(params)
  }

  useEffect(() => {
    if (initialQuerySubmitted) {
      return
    }
    if (loading) {
      return
    }
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
    if (!submittedParams || loading) {
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
        <PageCard>
          <PageTitle>
            {t('retrieve.title')}
          </PageTitle>
          <form onSubmit={handleSubmit} className="query-form">
            <div className="input-row">
              <TextInput
                value={formParams.query}
                onChange={(e) => setFormParams({ ...formParams, query: e.target.value })}
                placeholder={t('retrieve.placeholder')}
                disabled={loading}
              />
              <Button
                type="submit"
                disabled={loading || !formParams.query.trim()}
              >
                {loading ? t('retrieve.submitting') : t('retrieve.submitButton')}
              </Button>
            </div>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginTop: '0.5rem', cursor: 'pointer', userSelect: 'none' }}>
              <input
                type="checkbox"
                checked={formParams.semantic}
                onChange={(e) => setFormParams({ ...formParams, semantic: e.target.checked })}
                disabled={loading}
              />
              {t('retrieve.semantic')}
            </label>
          </form>

          {error && <ErrorDisplay error={error} />}
          {resultsContent}
        </PageCard>
      </main>
    </>
  )
}

export default RetrievePage

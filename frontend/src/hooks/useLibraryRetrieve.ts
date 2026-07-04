import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useT, useTranslation } from '../contexts/LanguageContext'
import { buildUrlWithLanguage } from '../utils/language'
import type { LibraryRetrieveRequest, LibraryRetrieveResponse } from '../types/api'

const QUERY_PARAM = 'q'
const SEMANTIC_PARAM = 'semantic'

export interface LibraryRetrieveParams {
  query: string
  semantic: boolean
}

export function useLibraryRetrieve() {
  const t = useT()
  const { language } = useTranslation()
  const location = useLocation()
  const [formParams, setFormParams] = useState<LibraryRetrieveParams>({ query: '', semantic: false })
  const [submittedParams, setSubmittedParams] = useState<LibraryRetrieveParams | null>(null)
  const [initialQuerySubmitted, setInitialQuerySubmitted] = useState(false)
  const [results, setResults] = useState<LibraryRetrieveResponse['results']>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const activeRequestIdRef = useRef(0)

  const urlParams = useMemo((): LibraryRetrieveParams => {
    const params = new URLSearchParams(location.search)
    return {
      query: params.get(QUERY_PARAM) ?? '',
      semantic: params.get(SEMANTIC_PARAM) === '1',
    }
  }, [location.search])

  const clearSearch = useCallback(() => {
    activeRequestIdRef.current += 1
    setResults([])
    setError(null)
    setLoading(false)
    setSubmittedParams(null)
  }, [])

  const writeParamsToUrl = useCallback((params: LibraryRetrieveParams) => {
    const urlSearchParams = new URLSearchParams(location.search)
    if (params.query) {
      urlSearchParams.set(QUERY_PARAM, params.query)
      urlSearchParams.set(SEMANTIC_PARAM, params.semantic ? '1' : '0')
    } else {
      urlSearchParams.delete(QUERY_PARAM)
      urlSearchParams.delete(SEMANTIC_PARAM)
    }
    const nextUrl = buildUrlWithLanguage(location.pathname, `?${urlSearchParams.toString()}`, language)
    window.history.replaceState(null, '', nextUrl)
  }, [language, location.pathname, location.search])

  const runSearch = useCallback(async (params: LibraryRetrieveParams) => {
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
        chunk_context: 0,
      }
      const res = await fetch('/api/library/retrieve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(reqBody),
      })
      const data = await res.json()
      if (activeRequestIdRef.current !== requestId) return
      if (res.ok) {
        setResults((data as LibraryRetrieveResponse).results)
      } else {
        setError((data as { error?: string }).error || t('retrieve.errors.unknown'))
      }
    } catch {
      if (activeRequestIdRef.current === requestId) {
        setError(t('retrieve.errors.noConnection'))
      }
    } finally {
      if (activeRequestIdRef.current === requestId) {
        setLoading(false)
      }
    }
  }, [language, t])

  const submit = useCallback(async () => {
    const params: LibraryRetrieveParams = { query: formParams.query.trim(), semantic: formParams.semantic }
    if (!params.query) {
      writeParamsToUrl(params)
      clearSearch()
      return
    }
    if (params.query === submittedParams?.query && params.semantic === submittedParams?.semantic) return

    writeParamsToUrl(params)
    await runSearch(params)
  }, [clearSearch, formParams, runSearch, submittedParams, writeParamsToUrl])

  useEffect(() => {
    if (initialQuerySubmitted) return
    if (loading) return
    setFormParams(urlParams)
    setInitialQuerySubmitted(true)
    if (urlParams.query) {
      runSearch(urlParams)
    } else {
      clearSearch()
    }
  }, [clearSearch, initialQuerySubmitted, loading, runSearch, urlParams])

  return {
    formParams,
    setFormParams,
    submittedParams,
    results,
    error,
    loading,
    submit,
  }
}

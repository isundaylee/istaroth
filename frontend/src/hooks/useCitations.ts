import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from '../contexts/LanguageContext'
import type { CitationResponse } from '../types/api'
import { fetchCitationsBatch as apiFetchCitationsBatch, fetchLibraryFile } from '../utils/api'
import { formatCitationId, parseCitationId } from '../utils/citations'

type CachedCitation = CitationResponse | { error: string }

/**
 * Citation cache + loading state, batch fetch, file-text fetch, and prefetch
 * for the title-list. Decouples the citation data layer from the popup/panel
 * UI so it can be reused elsewhere.
 */
export function useCitations(uniqueFileIds: string[]) {
  const { language } = useTranslation()
  const [citationCache, setCitationCache] = useState<Record<string, CachedCitation>>({})
  const [loadingCitations, setLoadingCitations] = useState<Set<string>>(new Set())
  const [fileTextCache, setFileTextCache] = useState<Record<string, string>>({})
  const [loadingFiles, setLoadingFiles] = useState<Set<string>>(new Set())

  // Guard against stale closures: the latest cache/loading sets read inside
  // callbacks via a ref, so useCallback doesn't re-create every render.
  const refs = useRef({ citationCache, loadingCitations, fileTextCache, loadingFiles })
  refs.current = { citationCache, loadingCitations, fileTextCache, loadingFiles }

  const fetchCitationsBatch = useCallback(async (citationIds: string[]) => {
    const { citationCache: cache, loadingCitations: loading } = refs.current
    const toFetch = citationIds.filter(id => !cache[id] && !loading.has(id))
    if (toFetch.length === 0) return

    const citations = toFetch.map(citationId => {
      const { fileId, chunkIndex } = parseCitationId(citationId)
      return [fileId, chunkIndex] as [string, number]
    })

    setLoadingCitations(prev => {
      const next = new Set(prev)
      toFetch.forEach(id => next.add(id))
      return next
    })

    try {
      const data = await apiFetchCitationsBatch(language, citations)
      setCitationCache(prev => {
        const next = { ...prev }
        for (const citation of data.successes) {
          next[formatCitationId(citation.file_id, citation.chunk_index)] = citation
        }
        for (const error of data.errors) {
          next[formatCitationId(error.file_id, error.chunk_index)] = { error: error.error }
        }
        return next
      })
    } catch {
      setCitationCache(prev => {
        const next = { ...prev }
        for (const id of toFetch) {
          next[id] = { error: `Failed to fetch citation ${id}` }
        }
        return next
      })
    } finally {
      setLoadingCitations(prev => {
        const next = new Set(prev)
        toFetch.forEach(id => next.delete(id))
        return next
      })
    }
  }, [language])

  const getCitedWorkInfo = useCallback((fileId: string): CitationResponse | null => {
    const cachedChunk = Object.entries(refs.current.citationCache)
      .find(([key]) => key.startsWith(`${fileId}:`))
    if (cachedChunk && !('error' in cachedChunk[1])) {
      return cachedChunk[1] as CitationResponse
    }
    return null
  }, [])

  const fetchFileText = useCallback(async (fileId: string) => {
    const { fileTextCache: ftCache, loadingFiles: lf } = refs.current
    if (ftCache[fileId] || lf.has(fileId)) return

    const cached = getCitedWorkInfo(fileId)
    if (!cached) return

    setLoadingFiles(prev => new Set(prev).add(fileId))
    try {
      const data = await fetchLibraryFile(
        cached.file_info.category,
        cached.file_info.id,
        language
      )
      setFileTextCache(prev => ({ ...prev, [fileId]: data.content }))
    } catch {
      // Silently fail; the popup shows the chunk view with load-gap buttons.
    } finally {
      setLoadingFiles(prev => {
        const next = new Set(prev)
        next.delete(fileId)
        return next
      })
    }
  }, [language, getCitedWorkInfo])

  // Prefetch citations for all unique file IDs to get titles immediately.
  useEffect(() => {
    const citationIds = uniqueFileIds.map(fileId => formatCitationId(fileId, 0))
    fetchCitationsBatch(citationIds)
  }, [uniqueFileIds, fetchCitationsBatch])

  return {
    citationCache,
    loadingCitations,
    fileTextCache,
    loadingFiles,
    fetchCitationsBatch,
    fetchFileText,
    getCitedWorkInfo
  }
}

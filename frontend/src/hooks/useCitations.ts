import { useCallback, useEffect, useState } from 'react'
import { useTranslation, useT } from '../contexts/LanguageContext'
import type { CitationResponse, LibraryFileInfo } from '../types/api'
import { ApiError, fetchCitationsBatch as apiFetchCitationsBatch, fetchLibraryFile } from '../utils/api'
import { formatCitationId, parseCitationId } from '../utils/citations'

export type CachedCitation = CitationResponse | { error: string }

export interface Citations {
  /** Cited chunks (or their fetch errors) keyed by citation id. */
  citationCache: Record<string, CachedCitation>
  loadingCitations: Set<string>
  /** Full file text keyed by fileId, fetched on demand to render the whole document around the cited span. */
  fileTextCache: Record<string, string>
  loadingFiles: Set<string>
  fetchCitationsBatch: (citationIds: string[]) => void
  fetchFileText: (fileId: string) => void
  /** File info for a cited work, from any already-loaded chunk of that file. */
  getCitedWorkInfo: (fileId: string) => LibraryFileInfo | null
}

/**
 * Citation-content store for a rendered answer: batch-fetches cited chunks
 * (prefetching chunk 0 of every cited file so titles show immediately) and, on
 * demand, the full file text for the sticky popup.
 */
export function useCitations(uniqueFileIds: string[]): Citations {
  const [citationCache, setCitationCache] = useState<Record<string, CachedCitation>>({})
  const [loadingCitations, setLoadingCitations] = useState<Set<string>>(new Set())
  const [fileTextCache, setFileTextCache] = useState<Record<string, string>>({})
  const [loadingFiles, setLoadingFiles] = useState<Set<string>>(new Set())
  const { language } = useTranslation()
  const t = useT()

  const errorMessage = useCallback(
    (error: unknown) =>
      error instanceof ApiError
        ? `${t('citation.fetchFailed')} (${error.status}): ${error.statusText}`
        : `${t('citation.networkError')}: ${error instanceof Error ? error.message : 'Unknown error'}`,
    [t]
  )

  const fetchCitationsBatch = useCallback(async (citationIds: string[]) => {
    const citationsToFetch = citationIds.filter(id => !citationCache[id] && !loadingCitations.has(id))
    if (citationsToFetch.length === 0) return

    setLoadingCitations(prev => {
      const newSet = new Set(prev)
      citationsToFetch.forEach(id => newSet.add(id))
      return newSet
    })

    try {
      const data = await apiFetchCitationsBatch(
        language,
        citationsToFetch.map(citationId => {
          const { fileId, chunkIndex } = parseCitationId(citationId)
          return [fileId, chunkIndex] as [string, number]
        })
      )
      setCitationCache(prev => {
        const newCache = { ...prev }
        data.successes.forEach(citation => {
          newCache[formatCitationId(citation.file_id, citation.chunk_index)] = citation
        })
        data.errors.forEach(error => {
          newCache[formatCitationId(error.file_id, error.chunk_index)] = { error: error.error }
        })
        return newCache
      })
    } catch (error) {
      // HTTP or network error - mark all as failed
      const message = errorMessage(error)
      console.error(message)
      setCitationCache(prev => {
        const newCache = { ...prev }
        citationsToFetch.forEach(citationId => {
          newCache[citationId] = { error: message }
        })
        return newCache
      })
    } finally {
      setLoadingCitations(prev => {
        const newSet = new Set(prev)
        citationsToFetch.forEach(id => newSet.delete(id))
        return newSet
      })
    }
  }, [citationCache, loadingCitations, language, errorMessage])

  const getCitedWorkInfo = useCallback((fileId: string): LibraryFileInfo | null => {
    const cached = Object.values(citationCache).find(
      (value): value is CitationResponse => !('error' in value) && value.file_id === fileId
    )
    return cached ? cached.file_info : null
  }, [citationCache])

  // Fetch the entire file text for a cited work so the sticky popup can render the
  // full document (no chunk overlap) with the cited span highlighted.
  const fetchFileText = useCallback(async (fileId: string) => {
    if (fileTextCache[fileId] || loadingFiles.has(fileId)) return

    // file_info (category/id) comes from any already-loaded chunk for this file.
    const fileInfo = getCitedWorkInfo(fileId)
    if (!fileInfo) return

    setLoadingFiles(prev => new Set(prev).add(fileId))
    try {
      const data = await fetchLibraryFile(fileInfo.category, fileInfo.id, language)
      setFileTextCache(prev => ({ ...prev, [fileId]: data.content }))
    } catch (error) {
      console.error(errorMessage(error))
    } finally {
      setLoadingFiles(prev => {
        const newSet = new Set(prev)
        newSet.delete(fileId)
        return newSet
      })
    }
  }, [fileTextCache, loadingFiles, getCitedWorkInfo, language, errorMessage])

  // Prefetch citations for all unique file IDs to get titles immediately
  useEffect(() => {
    fetchCitationsBatch(uniqueFileIds.map(fileId => formatCitationId(fileId, 0)))
  }, [uniqueFileIds, fetchCitationsBatch])

  return { citationCache, loadingCitations, fileTextCache, loadingFiles, fetchCitationsBatch, fetchFileText, getCitedWorkInfo }
}

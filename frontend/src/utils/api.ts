import type { CitationBatchRequest, CitationBatchResponse, CitationError, LibraryFileResponse } from '../types/api'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function fetchLibraryFile(
  category: string,
  id: string | number,
  language: string
): Promise<LibraryFileResponse> {
  const normalizedLanguage = language.toUpperCase()
  const res = await fetch(
    `/api/library/file/${encodeURIComponent(category)}/${encodeURIComponent(id)}?language=${normalizedLanguage}`
  )
  if (!res.ok) {
    throw new ApiError(res.status, `Failed to fetch library file: ${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<LibraryFileResponse>
}

export async function fetchCitationsBatch(
  language: string,
  citations: CitationBatchRequest['citations']
): Promise<CitationBatchResponse> {
  const res = await fetch('/api/citations/batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ language: language.toUpperCase(), citations }),
  })
  if (!res.ok) {
    throw new ApiError(res.status, `Failed to fetch citations: ${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<CitationBatchResponse>
}

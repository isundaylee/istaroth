import type { CitationBatchRequest, CitationBatchResponse, LibraryFileResponse } from '../types/api'

/** Non-2xx response from an API endpoint. Network errors propagate as-is. */
export class ApiError extends Error {
  constructor(readonly status: number, readonly statusText: string) {
    super(`API error ${status}: ${statusText}`)
  }
}

async function fetchJson<T>(input: string, init?: RequestInit): Promise<T> {
  const res = await fetch(input, init)
  if (!res.ok) throw new ApiError(res.status, res.statusText)
  return (await res.json()) as T
}

export function fetchLibraryFile(category: string, id: string | number, language: string): Promise<LibraryFileResponse> {
  return fetchJson(
    `/api/library/file/${encodeURIComponent(category)}/${encodeURIComponent(id)}?language=${encodeURIComponent(language.toUpperCase())}`
  )
}

export function fetchCitationsBatch(
  language: string,
  citations: CitationBatchRequest['citations']
): Promise<CitationBatchResponse> {
  return fetchJson('/api/citations/batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ language: language.toUpperCase(), citations } satisfies CitationBatchRequest)
  })
}

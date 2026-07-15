import { readNdjsonStream } from './ndjson'
import type { ProgressMessage, ProgressStepStart, QueryRequest, QueryResponse } from '../types/api'

/**
 * Pull an error message out of a parsed error body, trying the ``error`` then
 * ``detail`` shapes the backend can return, falling back to ``fallback``.
 */
export function getErrorMessage(data: unknown, fallback: string): string {
  if (data && typeof data === 'object') {
    if ('error' in data && typeof data.error === 'string') return data.error
    if ('detail' in data && typeof data.detail === 'string') return data.detail
  }
  return fallback
}

/** Result of {@link postQueryStream}: either the readable stream body or an error message. */
export type PostQueryStreamResult =
  | { body: ReadableStream<Uint8Array> }
  | { error: string }

/**
 * POST a query to ``/api/query/stream`` and unwrap the handshake: on a
 * non-OK/bodyless response, read the JSON error body and return its message;
 * otherwise return the stream body ready for {@link consumeQueryStream}.
 */
export async function postQueryStream(
  request: QueryRequest,
  unknownError: string
): Promise<PostQueryStreamResult> {
  const res = await fetch('/api/query/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok || !res.body) {
    return { error: getErrorMessage(await res.json().catch(() => null), unknownError) }
  }
  return { body: res.body }
}

interface QueryStreamHandlers {
  onStepStart: (step: ProgressStepStart) => void
  onStepEnd: (id: string) => void
  onAnswerChunk: (text: string) => void
  onDone: (result: QueryResponse) => void
  onError: (error: string) => void
  noConnectionError: string
  unknownError: string
}

export async function consumeQueryStream(
  body: ReadableStream<Uint8Array>,
  handlers: QueryStreamHandlers
) {
  let settled = false
  for await (const event of readNdjsonStream<ProgressMessage>(body)) {
    if (event.type === 'step_start') {
      handlers.onStepStart(event)
    } else if (event.type === 'step_end') {
      handlers.onStepEnd(event.id)
    } else if (event.type === 'answer_chunk') {
      handlers.onAnswerChunk(event.text)
    } else if (event.type === 'done') {
      settled = true
      handlers.onDone(event.result)
    } else {
      settled = true
      handlers.onError(event.error || handlers.unknownError)
    }
  }

  if (!settled) {
    handlers.onError(handlers.noConnectionError)
  }
}

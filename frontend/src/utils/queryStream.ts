import { readNdjsonStream } from './ndjson'
import type { ProgressMessage, ProgressStepStart, QueryResponse } from '../types/api'

interface QueryStreamHandlers {
  onStepStart: (step: ProgressStepStart) => void
  onStepEnd: (id: string) => void
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

/**
 * Read a newline-delimited JSON (application/x-ndjson) response body, yielding
 * each parsed object as it arrives.
 *
 * Buffers across chunk boundaries so a JSON object split across reads is only
 * parsed once complete. The caller is responsible for checking the response is
 * OK and has a body before passing it in.
 */
export async function* readNdjsonStream<T>(body: ReadableStream<Uint8Array>): AsyncGenerator<T> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        if (line.trim()) yield JSON.parse(line) as T
      }
    }
    // Flush a trailing line not terminated by a newline.
    if (buffer.trim()) yield JSON.parse(buffer) as T
  } finally {
    reader.releaseLock()
  }
}

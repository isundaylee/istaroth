export interface CitationReference {
  fileId: string
  chunkIndex: number
}

/**
 * Parse XML citation format to extract file ID and chunk index.
 * Expected format: <citation file_id="..." chunk_index="ck##"/>
 */
export function parseCitation(xmlCitation: string): CitationReference | null {
  const regex = /<citation\s+file_id="([^"]+)"\s+chunk_index="ck(\d+)"\s*\/>/
  const match = xmlCitation.match(regex)

  if (!match) {
    return null
  }

  return {
    fileId: match[1],
    chunkIndex: parseInt(match[2], 10)
  }
}

/**
 * Create citation ID for caching purposes.
 * Format: fileId:ck##
 */
export function formatCitationId(fileId: string, chunkIndex: number): string {
  return `${fileId}:ck${chunkIndex}`
}

/**
 * Convert XML citations to markdown links for display.
 * Maps file IDs to document indices in order of appearance.
 */
export function preprocessCitationsForDisplay(text: string): string {
  const regex = /<citation\s+file_id="([^"]+)"\s+chunk_index="ck(\d+)"\s*\/>/g
  const fileIdToDocIndex = new Map<string, number>()
  let match: RegExpExecArray | null
  let documentCounter = 0

  // First pass: assign document indices to unique file IDs in order of appearance
  const textCopy = text
  const firstPassRegex = /<citation\s+file_id="([^"]+)"\s+chunk_index="ck(\d+)"\s*\/>/g
  while ((match = firstPassRegex.exec(textCopy)) !== null) {
    const fileId = match[1]
    if (!fileIdToDocIndex.has(fileId)) {
      documentCounter++
      fileIdToDocIndex.set(fileId, documentCounter)
    }
  }

  // Second pass: replace citations with document_index:chunk_index format
  return text.replace(regex, (_, fileId, chunkIndex) => {
    const docIndex = fileIdToDocIndex.get(fileId)!
    return `[${docIndex}:${chunkIndex}](http://istaroth.markdown/citation/${fileId}/${chunkIndex})`
  })
}

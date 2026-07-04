import { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'
import { buildProperNounMatcher } from '../utils/properNouns'
import { rehypeProperNouns } from '../utils/rehypeProperNouns'

interface HighlightedMarkdownProps {
  content: string
  /** Proper nouns to highlight in the rendered text (code/links are left untouched). */
  properNouns?: string[]
  /** Custom element renderers (e.g. citation links). */
  components?: Components
}

/** Shared markdown renderer (GFM + hard line breaks) with proper-noun highlighting. */
function HighlightedMarkdown({ content, properNouns, components }: HighlightedMarkdownProps) {
  const matcher = useMemo(
    () => (properNouns && properNouns.length > 0 ? buildProperNounMatcher(properNouns) : null),
    [properNouns]
  )

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm, remarkBreaks]}
      rehypePlugins={matcher ? [rehypeProperNouns(matcher)] : []}
      components={components}
    >{content}</ReactMarkdown>
  )
}

export default HighlightedMarkdown

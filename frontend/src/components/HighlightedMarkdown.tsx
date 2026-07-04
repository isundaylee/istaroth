import { useMemo, type ComponentProps } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'
import { buildProperNounMatcher } from '../utils/properNouns'
import { rehypeProperNouns } from '../utils/rehypeProperNouns'

interface Props {
  content: string
  properNouns?: string[]
  components?: Components
}

export function HighlightedMarkdown({ content, properNouns, components }: Props) {
  const properNounMatcher = useMemo(
    () => (properNouns && properNouns.length > 0 ? buildProperNounMatcher(properNouns) : null),
    [properNouns]
  )

  const remarkPlugins = useMemo(() => [remarkGfm, remarkBreaks], [])
  const rehypePlugins = useMemo(
    () => (properNounMatcher ? [rehypeProperNouns(properNounMatcher)] : []),
    [properNounMatcher]
  )

  return (
    <ReactMarkdown
      remarkPlugins={remarkPlugins}
      rehypePlugins={rehypePlugins}
      components={components}
    >{content}</ReactMarkdown>
  )
}

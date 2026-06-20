/**
 * react-markdown rehype plugin that wraps proper-noun occurrences in the
 * rendered text in `<span class="proper-noun">` for highlighting.
 *
 * Operates on the parsed hast tree (not raw markdown) so tables, line breaks
 * and other structure stay intact. Text inside code/links is left untouched.
 */

import type { ProperNounMatcher } from './properNouns'

// Minimal hast node shape; we only touch the fields we mutate.
interface HastNode {
  type: string
  tagName?: string
  value?: string
  children?: HastNode[]
  properties?: Record<string, unknown>
}

const _SKIP_TAGS = new Set(['code', 'pre', 'a'])

function _highlightSpan(term: string): HastNode {
  return {
    type: 'element',
    tagName: 'span',
    properties: { className: ['proper-noun'] },
    children: [{ type: 'text', value: term }],
  }
}

function _visit(node: HastNode, matcher: ProperNounMatcher): void {
  if (!node.children) return
  const next: HastNode[] = []
  for (const child of node.children) {
    if (child.type === 'text' && typeof child.value === 'string') {
      const segments = matcher.splitText(child.value)
      if (segments.length === 1 && segments[0].term === null) {
        next.push(child)
        continue
      }
      for (const segment of segments) {
        next.push(
          segment.term === null
            ? { type: 'text', value: segment.text }
            : _highlightSpan(segment.term)
        )
      }
    } else if (child.type === 'element' && child.tagName && _SKIP_TAGS.has(child.tagName)) {
      next.push(child)
    } else {
      _visit(child, matcher)
      next.push(child)
    }
  }
  node.children = next
}

/** Build a configured rehype plugin for the given matcher. */
export function rehypeProperNouns(matcher: ProperNounMatcher) {
  return () => (tree: HastNode) => _visit(tree, matcher)
}

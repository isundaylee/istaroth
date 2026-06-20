/**
 * Longest-match matcher for highlighting Genshin proper nouns in library text.
 *
 * Chinese has no word boundaries, so we scan character-by-character against a
 * trie built from the proper-noun list and emit the longest dictionary term at
 * each position (e.g. prefer "蒙德城" over "蒙德").
 */

interface TrieNode {
  children: Map<string, TrieNode>
  isWord: boolean
}

export interface TextSegment {
  text: string
  /** The matched proper noun when this segment is a highlight, else null. */
  term: string | null
}

export interface ProperNounMatcher {
  splitText(text: string): TextSegment[]
}

function _buildTrie(nouns: string[]): TrieNode {
  const root: TrieNode = { children: new Map(), isWord: false }
  for (const noun of nouns) {
    if (!noun) continue
    let node = root
    for (const ch of noun) {
      let next = node.children.get(ch)
      if (!next) {
        next = { children: new Map(), isWord: false }
        node.children.set(ch, next)
      }
      node = next
    }
    node.isWord = true
  }
  return root
}

export function buildProperNounMatcher(nouns: string[]): ProperNounMatcher {
  const root = _buildTrie(nouns)
  // Iterate by code points so multi-unit characters are handled correctly.
  const splitText = (text: string): TextSegment[] => {
    const chars = Array.from(text)
    const segments: TextSegment[] = []
    let plain = ''
    let i = 0
    while (i < chars.length) {
      let node = root
      let matchEnd = -1
      for (let j = i; j < chars.length; j++) {
        const next = node.children.get(chars[j])
        if (!next) break
        node = next
        if (node.isWord) matchEnd = j + 1
      }
      if (matchEnd === -1) {
        plain += chars[i]
        i += 1
        continue
      }
      if (plain) {
        segments.push({ text: plain, term: null })
        plain = ''
      }
      const term = chars.slice(i, matchEnd).join('')
      segments.push({ text: term, term })
      i = matchEnd
    }
    if (plain) segments.push({ text: plain, term: null })
    return segments
  }
  return { splitText }
}

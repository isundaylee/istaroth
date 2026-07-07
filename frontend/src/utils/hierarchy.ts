import type { HierarchyNode, LibraryCategoryHierarchy } from '../types/api'

type T = (key: string) => string

export function nodeLabel(node: HierarchyNode): string {
  return node.title || node.key
}

// Resolve a category value (e.g. "agd_quest") to its hierarchy entry, which
// carries the localized display title. The hierarchy response covers every
// category in the corpus, so a miss is a bug rather than a display fallback.
export function findCategory(
  categories: LibraryCategoryHierarchy[],
  category: string
): LibraryCategoryHierarchy {
  const entry = categories.find((item) => item.category === category)
  if (!entry) throw new Error(`Category missing from hierarchy: ${category}`)
  return entry
}

export function isLeaf(node: HierarchyNode): boolean {
  return node.file_id != null
}

// The shared breadcrumb prefix for any in-category view: the Library root, the
// category, then one clickable crumb per ancestor group node (each linking to
// its browse path). Callers append their own trailing "current" crumb. Used by
// both the hierarchy listing pages and the file viewer.
export function hierarchyCrumbs(
  entry: LibraryCategoryHierarchy,
  ancestors: HierarchyNode[],
  t: T
): { label: string; to: string }[] {
  return [
    { label: t('library.title'), to: '/library' },
    { label: entry.title, to: `/library/${encodeURIComponent(entry.category)}` },
    ...ancestors.map((node, index) => ({
      label: nodeLabel(node) || t('library.noFileName'),
      to: `/library/${encodeURIComponent(entry.category)}/browse/${ancestors
        .slice(0, index + 1)
        .map((ancestor) => ancestor.key)
        .join('/')}`,
    })),
  ]
}

// Total number of leaf files under a node (the node itself if it is a leaf).
export function countLeaves(node: HierarchyNode): number {
  if (node.children == null) return isLeaf(node) ? 1 : 0
  return node.children.reduce((sum, child) => sum + countLeaves(child), 0)
}

export interface LeafSearchEntry {
  fileId: number
  title: string
  context: string
}

// Flatten every leaf into a searchable entry whose `context` is the ` / `-joined
// trail of ancestor labels, so a query matching an ancestor surfaces its leaves.
export function flattenLeafEntries(nodes: HierarchyNode[]): LeafSearchEntry[] {
  const entries: LeafSearchEntry[] = []
  const walk = (node: HierarchyNode, ancestors: string[]) => {
    if (node.children == null) {
      if (node.file_id != null) {
        entries.push({ fileId: node.file_id, title: node.title || '', context: ancestors.join(' / ') })
      }
      return
    }
    const next = [...ancestors, nodeLabel(node)]
    node.children.forEach((child) => walk(child, next))
  }
  nodes.forEach((node) => walk(node, []))
  return entries
}

// The chain of nodes from a root down to (and including) the leaf with `fileId`,
// or null when no such leaf exists.
export function findLeafPath(nodes: HierarchyNode[], fileId: number): HierarchyNode[] | null {
  for (const node of nodes) {
    if (node.file_id === fileId) return [node]
    if (node.children != null) {
      const sub = findLeafPath(node.children, fileId)
      if (sub) return [node, ...sub]
    }
  }
  return null
}

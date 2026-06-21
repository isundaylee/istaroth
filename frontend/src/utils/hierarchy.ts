import type { HierarchyNode } from '../types/api'

type T = (key: string) => string

export function nodeLabel(node: HierarchyNode): string {
  return node.title || node.key
}

// Translate a category value (e.g. "agd_quest") via i18n, falling back to the raw
// value when there is no translation.
export function categoryLabel(category: string, t: T): string {
  const key = `library.categories.${category}`
  const translated = t(key)
  return translated === key ? category : translated
}

export function isLeaf(node: HierarchyNode): boolean {
  return node.file_id != null
}

// The shared breadcrumb prefix for any in-category view: the Library root, the
// category, then one clickable crumb per ancestor group node (each linking to
// its browse path). Callers append their own trailing "current" crumb. Used by
// both the hierarchy listing pages and the file viewer.
export function hierarchyCrumbs(
  category: string,
  ancestors: HierarchyNode[],
  t: T
): { label: string; to: string }[] {
  return [
    { label: t('library.title'), to: '/library' },
    { label: categoryLabel(category, t), to: `/library/${encodeURIComponent(category)}` },
    ...ancestors.map((node, index) => ({
      label: nodeLabel(node) || t('library.noFileName'),
      to: `/library/${encodeURIComponent(category)}/browse/${ancestors
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

// All leaf nodes under `nodes`, in depth-first order.
export function flattenLeaves(nodes: HierarchyNode[]): HierarchyNode[] {
  const leaves: HierarchyNode[] = []
  const walk = (node: HierarchyNode) => {
    if (node.children == null) {
      if (isLeaf(node)) leaves.push(node)
      return
    }
    node.children.forEach(walk)
  }
  nodes.forEach(walk)
  return leaves
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

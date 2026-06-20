import type { HierarchyNode } from '../types/api'

type T = (key: string) => string

// Resolve a node's display label: a frontend i18n key (quest type, "standalone",
// …) wins, then a baked data title, then the raw key as a last resort.
export function nodeLabel(node: HierarchyNode, t: T): string {
  if (node.title_key) {
    const translated = t(node.title_key)
    if (translated !== node.title_key) return translated
  }
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
export function flattenLeafEntries(nodes: HierarchyNode[], t: T): LeafSearchEntry[] {
  const entries: LeafSearchEntry[] = []
  const walk = (node: HierarchyNode, ancestors: string[]) => {
    if (node.children == null) {
      if (node.file_id != null) {
        entries.push({ fileId: node.file_id, title: node.title || '', context: ancestors.join(' / ') })
      }
      return
    }
    const next = [...ancestors, nodeLabel(node, t)]
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

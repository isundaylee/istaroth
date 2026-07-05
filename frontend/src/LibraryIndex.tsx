import React from 'react'
import clsx from 'clsx'
import { ChevronDown, ChevronRight, Search } from 'lucide-react'
import { useT } from './contexts/LanguageContext'
import TextInput from './components/TextInput'
import { useCloseSidebarDrawer } from './components/PageShell'
import { useAppNavigate } from './hooks/useAppNavigate'
import {
  categoryLabel,
  countLeaves,
  findLeafPath,
  flattenLeafEntries,
  isLeaf,
  nodeLabel,
} from './utils/hierarchy'
import styles from './LibraryIndex.module.css'
import type { HierarchyNode, LibraryCategoryHierarchy } from './types/api'

// Broad filter queries can match thousands of leaves; rendering them all makes
// the rail janky, so cut off and say how many were hidden.
const MAX_FILTER_RESULTS = 200

interface LibraryIndexProps {
  categories: LibraryCategoryHierarchy[]
  // The category containing the open file / browsed group (null at the root).
  activeCategory: string | null
  // The file currently open in the Folio (null when browsing a group / the root).
  activeFileId: number | null
  // The key trail of the group currently browsed in the Folio (empty otherwise).
  activeBrowseKeys: string[]
}

// The persistent hierarchical navigator: one unified tree over the whole
// library, with a top-level group per category, the branch leading to the open
// file/group auto-expanded, and the current leaf marked. Groups expand/collapse
// in place; a filter flattens to matching leaves across all categories.
function LibraryIndex({ categories, activeCategory, activeFileId, activeBrowseKeys }: LibraryIndexProps) {
  const t = useT()
  const navigate = useAppNavigate()
  const closeDrawer = useCloseSidebarDrawer()
  const [query, setQuery] = React.useState('')

  // Each category renders as a synthetic top-level group node; a node's
  // category is always the first segment of its tree path.
  const roots = React.useMemo<HierarchyNode[]>(
    () =>
      categories.map((entry) => ({
        key: entry.category,
        title: categoryLabel(entry.category, t),
        children: entry.nodes,
        file_id: null,
        toc_eligible: false,
      })),
    [categories, t]
  )

  // The group path-keys that must be open to reveal the current position: the
  // active category, then every ancestor of the open file or the browsed
  // group's own trail. File ids are only unique within a category, so the leaf
  // lookup is scoped to the active category's subtree.
  const activeNodes = activeCategory
    ? categories.find((entry) => entry.category === activeCategory)?.nodes ?? null
    : null
  const activePath = activeFileId != null && activeNodes ? findLeafPath(activeNodes, activeFileId) : null
  const activeTrail = activePath ? activePath.slice(0, -1).map((node) => node.key) : activeBrowseKeys
  const forcedOpen = (activeCategory ? [activeCategory, ...activeTrail] : []).map(
    (_, index, keys) => keys.slice(0, index + 1).join('/')
  )

  const [expanded, setExpanded] = React.useState<Set<string>>(() => new Set(forcedOpen))
  // Re-reveal the active branch on navigation without collapsing manual toggles.
  const forcedKey = forcedOpen.join('|')
  React.useEffect(() => {
    setExpanded((prev) => new Set([...prev, ...forcedKey.split('|').filter(Boolean)]))
  }, [forcedKey])

  const currentRef = React.useRef<HTMLElement | null>(null)
  // The browsed group's full tree path (its category root when at the category
  // index), marked current when no file is open.
  const activeKey =
    activeCategory && activeFileId == null ? [activeCategory, ...activeBrowseKeys].join('/') : ''
  React.useEffect(() => {
    currentRef.current?.scrollIntoView({ block: 'nearest' })
  }, [activeFileId, activeKey])

  const toggle = (pathKey: string) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(pathKey) ? next.delete(pathKey) : next.add(pathKey)
      return next
    })

  // Opening a document closes the mobile drawer. Groups only expand/collapse the
  // rail; the Folio stays put until a leaf document is selected.
  const openLeaf = (category: string, fileId: number) => {
    closeDrawer()
    navigate(`/library/${encodeURIComponent(category)}/${encodeURIComponent(fileId)}`)
  }

  const renderNodes = (items: HierarchyNode[], parentPath: string): React.ReactNode => (
    <ul className={parentPath ? styles.children : styles.list}>
      {items.map((node, index) => {
        const pathKey = parentPath ? `${parentPath}/${node.key}` : node.key
        // agd_talk_group merges two id spaces (ActivityGroup + NpcGroup) that
        // overlap, so node.key/file_id can repeat across siblings; disambiguate
        // the React key by sibling index. pathKey still drives expand state.
        const rowKey = `${pathKey}#${index}`
        if (isLeaf(node)) {
          const category = pathKey.split('/')[0]
          const current = node.file_id === activeFileId && category === activeCategory
          return (
            <li key={rowKey}>
              <button
                ref={current ? (el) => (currentRef.current = el) : undefined}
                className={clsx(styles.row, styles.leaf, current && styles.current)}
                onClick={() => openLeaf(category, node.file_id!)}
              >
                <span className={styles.label}>{nodeLabel(node) || t('library.noFileName')}</span>
              </button>
            </li>
          )
        }
        const open = expanded.has(pathKey)
        const current = activeKey === pathKey
        return (
          <li key={rowKey}>
            <button
              ref={current ? (el) => (currentRef.current = el) : undefined}
              className={clsx(styles.row, styles.group, current && styles.current)}
              onClick={() => toggle(pathKey)}
              aria-expanded={open}
            >
              <span className={styles.caret}>
                {open ? <ChevronDown size={12} aria-hidden /> : <ChevronRight size={12} aria-hidden />}
              </span>
              <span className={styles.groupBody}>
                <span className={styles.label}>{nodeLabel(node) || t('library.noFileName')}</span>
                <span className={styles.count}>{countLeaves(node)}</span>
              </span>
            </button>
            {open && renderNodes(node.children!, pathKey)}
          </li>
        )
      })}
    </ul>
  )

  // Every leaf in the library, with its category label leading the context
  // trail, so the filter searches across all categories at once.
  const allEntries = React.useMemo(
    () =>
      categories.flatMap((entry) => {
        const label = categoryLabel(entry.category, t)
        return flattenLeafEntries(entry.nodes).map((leaf) => ({
          ...leaf,
          category: entry.category,
          context: leaf.context ? `${label} / ${leaf.context}` : label,
        }))
      }),
    [categories, t]
  )

  const trimmed = query.trim().toLowerCase()
  const results = trimmed
    ? allEntries.filter((entry) =>
        [entry.title, entry.context].join(' ').toLowerCase().includes(trimmed)
      )
    : []
  const hiddenResults = results.length - MAX_FILTER_RESULTS

  return (
    <div className={styles.tree}>
      <div className={styles.search}>
        <Search size={13} aria-hidden className={styles.searchIcon} />
        <TextInput
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t('library.filterPlaceholder')}
        />
      </div>

      {trimmed ? (
        results.length === 0 ? (
          <p className={styles.empty}>{t('library.noFilterResults')}</p>
        ) : (
          <>
            <ul className={styles.list}>
              {results.slice(0, MAX_FILTER_RESULTS).map((entry, index) => (
                <li key={`${entry.category}-${entry.fileId}#${index}`}>
                  <button
                    className={clsx(
                      styles.row,
                      entry.fileId === activeFileId && entry.category === activeCategory && styles.current
                    )}
                    onClick={() => openLeaf(entry.category, entry.fileId)}
                  >
                    <span className={styles.label}>
                      {entry.title || t('library.noFileName')}
                      {entry.context && <span className={styles.context}>{entry.context}</span>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            {hiddenResults > 0 && (
              <p className={styles.empty}>
                {hiddenResults} {t('library.filterMoreHidden')}
              </p>
            )}
          </>
        )
      ) : (
        renderNodes(roots, '')
      )}
    </div>
  )
}

export default LibraryIndex

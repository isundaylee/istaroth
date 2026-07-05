import React from 'react'
import clsx from 'clsx'
import { ChevronDown, ChevronRight, Search } from 'lucide-react'
import { useT } from './contexts/LanguageContext'
import { AppLink } from './components/AppLink'
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
import type { HierarchyNode } from './types/api'

interface LibraryIndexProps {
  category: string
  nodes: HierarchyNode[]
  // The file currently open in the Folio (null when browsing a group / the root).
  activeFileId: number | null
  // The key trail of the group currently browsed in the Folio (empty otherwise).
  activeBrowseKeys: string[]
}

// The persistent hierarchical navigator: the current category's whole tree, with
// the branch leading to the open file/group auto-expanded and the current leaf
// marked. Groups expand/collapse in place; a filter flattens to matching leaves.
function LibraryIndex({ category, nodes, activeFileId, activeBrowseKeys }: LibraryIndexProps) {
  const t = useT()
  const navigate = useAppNavigate()
  const closeDrawer = useCloseSidebarDrawer()
  const [query, setQuery] = React.useState('')

  // Only reserve the caret-slot indent for leaves when the category actually has
  // groups; a flat leaf list (no carets anywhere) should not be indented.
  const hasGroups = nodes.some((node) => node.children != null)

  // The group path-keys that must be open to reveal the current position: every
  // ancestor of the open file, or the browsed group's own trail.
  const activePath = activeFileId != null ? findLeafPath(nodes, activeFileId) : null
  const forcedOpen = (activePath ? activePath.slice(0, -1).map((node) => node.key) : activeBrowseKeys).map(
    (_, index, keys) => keys.slice(0, index + 1).join('/')
  )

  const [expanded, setExpanded] = React.useState<Set<string>>(() => new Set(forcedOpen))
  // Re-reveal the active branch on navigation without collapsing manual toggles.
  const forcedKey = forcedOpen.join('|')
  React.useEffect(() => {
    setExpanded((prev) => new Set([...prev, ...forcedKey.split('|').filter(Boolean)]))
  }, [forcedKey])

  const currentRef = React.useRef<HTMLElement | null>(null)
  const activeKey = activeBrowseKeys.join('/')
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
  const openLeaf = (fileId: number) => {
    closeDrawer()
    navigate(`/library/${encodeURIComponent(category)}/${encodeURIComponent(fileId)}`)
  }

  const openGroup = (pathKey: string) => {
    setExpanded((prev) => new Set(prev).add(pathKey))
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
          const current = node.file_id === activeFileId
          return (
            <li key={rowKey}>
              <button
                ref={current ? (el) => (currentRef.current = el) : undefined}
                className={clsx(styles.row, hasGroups && styles.leaf, current && styles.current)}
                onClick={() => openLeaf(node.file_id!)}
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
            <div
              ref={current ? (el) => (currentRef.current = el) : undefined}
              className={clsx(styles.row, styles.group, current && styles.current)}
            >
              <button
                className={styles.caret}
                onClick={() => toggle(pathKey)}
                aria-label={open ? t('library.collapse') : t('library.expand')}
              >
                {open ? <ChevronDown size={12} aria-hidden /> : <ChevronRight size={12} aria-hidden />}
              </button>
              <button className={styles.labelBtn} onClick={() => openGroup(pathKey)}>
                <span className={styles.label}>{nodeLabel(node) || t('library.noFileName')}</span>
                <span className={styles.count}>{countLeaves(node)}</span>
              </button>
            </div>
            {open && renderNodes(node.children!, pathKey)}
          </li>
        )
      })}
    </ul>
  )

  const trimmed = query.trim().toLowerCase()
  const results = trimmed
    ? flattenLeafEntries(nodes).filter((entry) =>
        [entry.title, entry.context].join(' ').toLowerCase().includes(trimmed)
      )
    : []

  return (
    <div className={styles.tree}>
      <div className={styles.head}>
        <AppLink to="/library" className={styles.back}>
          ‹ {t('library.allCategories')}
        </AppLink>
        <p className={styles.cat}>{categoryLabel(category, t)}</p>
      </div>

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
          <ul className={styles.list}>
            {results.map((entry, index) => (
              <li key={`${entry.fileId}#${index}`}>
                <button
                  className={clsx(styles.row, entry.fileId === activeFileId && styles.current)}
                  onClick={() => openLeaf(entry.fileId)}
                >
                  <span className={styles.label}>
                    {entry.title || t('library.noFileName')}
                    {entry.context && <span className={styles.context}>{entry.context}</span>}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )
      ) : (
        renderNodes(nodes, '')
      )}
    </div>
  )
}

export default LibraryIndex

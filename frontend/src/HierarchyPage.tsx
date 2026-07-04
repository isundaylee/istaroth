import React from 'react'
import { useParams, useRouteLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import { useT } from './contexts/LanguageContext'
import Card from './components/Card'
import HierarchyBrowser, { NavCard, CardGrid } from './components/HierarchyBrowser'
import { type Crumb } from './components/Breadcrumbs'
import { translate } from './i18n'
import { getLanguageFromUrl } from './utils/language'
import { useAppNavigate } from './hooks/useAppNavigate'
import {
  countLeaves,
  flattenLeafEntries,
  hierarchyCrumbs,
  nodeLabel,
} from './utils/hierarchy'
import type { HierarchyNode, HierarchyResponse } from './types/api'

// Loads a category's whole document tree once for the parent route; the index,
// browse, and file-viewer children all read it via useRouteLoaderData.
export async function libraryCategoryLoader({
  params,
  request,
}: LoaderFunctionArgs): Promise<HierarchyResponse> {
  const { category } = params
  if (!category) {
    throw new Response(translate(getLanguageFromUrl(request.url), 'library.errors.invalidCategory'), {
      status: 400,
    })
  }
  const language = getLanguageFromUrl(request.url)
  const res = await fetch(`/api/library/hierarchy/${encodeURIComponent(category)}?language=${language}`)
  if (!res.ok) {
    throw new Response(translate(language, 'library.errors.loadFailed'), { status: res.status })
  }
  return (await res.json()) as HierarchyResponse
}

function searchPlaceholderKey(category: string): string {
  if (category === 'agd_quest') return 'library.questSearchPlaceholder'
  if (category === 'agd_hangout') return 'library.hangoutSearchPlaceholder'
  return 'library.filterPlaceholder'
}

function HierarchyPage() {
  const t = useT()
  const navigate = useAppNavigate()
  const { nodes } = useRouteLoaderData('library-category') as HierarchyResponse
  const params = useParams()
  const category = params.category!
  const splat = params['*'] ?? ''
  const [search, setSearch] = React.useState('')

  const keys = splat.split('/').filter(Boolean)

  // Walk the path keys down the tree to the current group node; `children` is the
  // node set to render and `trail` the group nodes leading there.
  let children = nodes
  const trail: HierarchyNode[] = []
  for (const key of keys) {
    const next = children.find((node) => node.key === key && node.children != null)
    if (!next || next.children == null) break
    trail.push(next)
    children = next.children
  }

  const crumbs: Crumb[] = hierarchyCrumbs(category, trail, t)

  const openLeaf = (fileId: number) =>
    navigate(`/library/${encodeURIComponent(category)}/${encodeURIComponent(fileId)}`)

  const openChild = (node: HierarchyNode) => {
    if (node.children != null) {
      navigate(`/library/${encodeURIComponent(category)}/browse/${[...keys, node.key].join('/')}`)
    } else if (node.file_id != null) {
      openLeaf(node.file_id)
    }
  }

  const query = search.trim().toLowerCase()
  const searchResults = query
    ? flattenLeafEntries(nodes).filter((entry) =>
        [entry.title, entry.context].join(' ').toLowerCase().includes(query)
      )
    : []

  let content: React.ReactNode
  if (query) {
    content =
      searchResults.length === 0 ? (
        <Card style={{ margin: '1rem 0' }}>
          <p>{t('library.noFilterResults')}</p>
        </Card>
      ) : (
        <CardGrid>
          {/* agd_talk_group merges ActivityGroup + NpcGroup id spaces, which
              overlap, so fileId/key can repeat: disambiguate keys by index. */}
          {searchResults.map((entry, index) => (
            <NavCard
              key={`${entry.fileId}#${index}`}
              label={entry.title || t('library.noFileName')}
              sublabel={entry.context || undefined}
              onClick={() => openLeaf(entry.fileId)}
            />
          ))}
        </CardGrid>
      )
  } else if (children.length === 0) {
    content = (
      <Card style={{ margin: '1rem 0' }}>
        <p>{t('library.noFiles')}</p>
      </Card>
    )
  } else {
    content = (
      <CardGrid>
        {children.map((node, index) => (
          <NavCard
            key={`${node.key}#${index}`}
            label={nodeLabel(node) || t('library.noFileName')}
            count={node.children != null ? countLeaves(node) : undefined}
            onClick={() => openChild(node)}
          />
        ))}
      </CardGrid>
    )
  }

  return (
    <HierarchyBrowser
      search={search}
      onSearchChange={setSearch}
      searchPlaceholder={t(searchPlaceholderKey(category))}
      crumbs={crumbs}
    >
      {content}
    </HierarchyBrowser>
  )
}

export default HierarchyPage

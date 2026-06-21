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
  categoryLabel,
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
  if (category === 'agd_coop') return 'library.coopSearchPlaceholder'
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

  const catLabel = categoryLabel(category, t)
  const browsePath = (depth: number) =>
    `/library/${encodeURIComponent(category)}/browse/${keys.slice(0, depth).join('/')}`

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
    ? flattenLeafEntries(nodes, t).filter((entry) =>
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
          {searchResults.map((entry) => (
            <NavCard
              key={entry.fileId}
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
        {children.map((node) => (
          <NavCard
            key={node.key}
            label={nodeLabel(node, t) || t('library.noFileName')}
            count={node.children != null ? countLeaves(node) : undefined}
            onClick={() => openChild(node)}
          />
        ))}
      </CardGrid>
    )
  }

  // The back button climbs one path level at a time, leaving for the category
  // root and then the library only once at the top.
  let backPath: string
  let backText: string
  if (keys.length === 0) {
    backPath = '/library'
    backText = t('library.backToCategories')
  } else if (keys.length === 1) {
    backPath = `/library/${encodeURIComponent(category)}`
    backText = catLabel
  } else {
    backPath = browsePath(keys.length - 1)
    backText = nodeLabel(trail[trail.length - 2], t) || t('library.noFileName')
  }

  return (
    <HierarchyBrowser
      title={catLabel}
      backText={backText}
      backPath={backPath}
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

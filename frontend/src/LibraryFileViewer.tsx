import { useEffect, useMemo, useState } from 'react'
import { useLoaderData, useRouteLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import { useTranslation, useT } from './contexts/LanguageContext'
import { MinimizedPopupRegion } from './contexts/MinimizedPopupContext'
import styles from './LibraryFileViewer.module.css'
import Breadcrumbs, { type Crumb } from './components/Breadcrumbs'
import NavButton from './components/NavButton'
import { HighlightedMarkdown } from './components/HighlightedMarkdown'
import { translate } from './i18n'
import { getLanguageFromUrl } from './utils/language'
import { useAppNavigate } from './hooks/useAppNavigate'
import { SelectableAnswer } from './components/SelectableAnswer'
import { recordLibraryView } from './utils/libraryRecents'
import {
  categoryLabel,
  findLeafPath,
  flattenLeaves,
  hierarchyCrumbs,
  nodeLabel,
} from './utils/hierarchy'
import type {
  HierarchyResponse,
  LibraryFileResponse,
  ProperNounsResponse,
} from './types/api'

interface LoaderData {
  fileContent: string
  fileTitle: string
  fileId: string
  category: string
  currentId: number
}

export async function libraryFileViewerLoader({ params, request }: LoaderFunctionArgs): Promise<LoaderData> {
  const { category, id } = params
  if (!category || !id) {
    throw new Response(translate(getLanguageFromUrl(request.url), 'library.errors.invalidCategory'), { status: 400 })
  }

  const language = getLanguageFromUrl(request.url)
  const res = await fetch(
    `/api/library/file/${encodeURIComponent(category)}/${encodeURIComponent(id)}?language=${language}`
  )
  if (!res.ok) {
    throw new Response(translate(language, 'library.errors.loadFailed'), { status: res.status })
  }

  const fileData = (await res.json()) as LibraryFileResponse
  return {
    fileContent: fileData.content,
    fileTitle: fileData.file_info.title,
    fileId: id,
    category,
    currentId: parseInt(id, 10),
  }
}

function LibraryFileViewer() {
  const t = useT()
  const { language } = useTranslation()
  const navigate = useAppNavigate()
  const { fileContent, fileTitle, fileId, category, currentId } = useLoaderData() as LoaderData
  const { nodes } = useRouteLoaderData('library-category') as HierarchyResponse
  // Static curated list (per language, fast) and the per-file LLM extraction
  // (null = still in flight). We highlight nothing for the first 2s, then fall
  // back to the static list; the LLM result replaces it whenever it arrives.
  const [staticNouns, setStaticNouns] = useState<string[]>([])
  const [llmNouns, setLlmNouns] = useState<string[] | null>(null)
  const [fallbackElapsed, setFallbackElapsed] = useState(false)
  const properNouns = useMemo(() => {
    if (llmNouns !== null) return llmNouns
    if (fallbackElapsed) return staticNouns
    return []
  }, [llmNouns, fallbackElapsed, staticNouns])

  const catLabel = categoryLabel(category, t)

  // Locate the file within the shared category tree to derive the breadcrumb
  // trail and prev/next. A file absent from the tree (e.g. a quest with no
  // hierarchy placement) simply degrades to no ancestors.
  const path = findLeafPath(nodes, currentId)
  const ancestors = path ? path.slice(0, -1) : []
  const browseTo = (depth: number) =>
    `/library/${encodeURIComponent(category)}/browse/${ancestors
      .slice(0, depth)
      .map((node) => node.key)
      .join('/')}`

  const crumbs: Crumb[] = [
    ...hierarchyCrumbs(category, ancestors, t),
    { label: fileTitle || catLabel },
  ]

  const backPath =
    ancestors.length > 0 ? browseTo(ancestors.length) : `/library/${encodeURIComponent(category)}`
  const backText =
    ancestors.length > 0 ? nodeLabel(ancestors[ancestors.length - 1]) || catLabel : catLabel

  // prev/next span the whole category in tree (depth-first) order.
  const leaves = flattenLeaves(nodes)
  const currentIndex = leaves.findIndex((leaf) => leaf.file_id === currentId)
  const previousFile = currentIndex > 0 ? leaves[currentIndex - 1] : null
  const nextFile =
    currentIndex >= 0 && currentIndex < leaves.length - 1 ? leaves[currentIndex + 1] : null

  useEffect(() => {
    recordLibraryView({ category, fileId: currentId, title: fileTitle })
  }, [category, currentId, fileTitle])

  // Static curated list: fetched once per language, reused across files.
  useEffect(() => {
    let cancelled = false
    fetch(`/api/library/proper-nouns?language=${encodeURIComponent(language.toUpperCase())}`)
      .then((res) => (res.ok ? (res.json() as Promise<ProperNounsResponse>) : null))
      .then((data) => {
        if (!cancelled) setStaticNouns(data?.nouns ?? [])
      })
      .catch(() => {
        if (!cancelled) setStaticNouns([])
      })
    return () => {
      cancelled = true
    }
  }, [language])

  // Per-file LLM extraction: show nothing for 2s, then fall back to the static
  // list; replace with the LLM result whenever it arrives. On failure we leave
  // llmNouns null so the static fallback stays.
  useEffect(() => {
    let cancelled = false
    setLlmNouns(null)
    setFallbackElapsed(false)
    const timer = window.setTimeout(() => {
      if (!cancelled) setFallbackElapsed(true)
    }, 2000)
    fetch(
      `/api/library/file/${encodeURIComponent(category)}/${encodeURIComponent(fileId)}/proper-nouns?language=${encodeURIComponent(language.toUpperCase())}`
    )
      .then((res) => (res.ok ? (res.json() as Promise<ProperNounsResponse>) : null))
      .then((data) => {
        if (!cancelled && data) setLlmNouns(data.nouns)
      })
      .catch(() => {})
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [language, category, fileId])

  return (
    <>
      <MinimizedPopupRegion className={styles.measure}>
        <Breadcrumbs crumbs={crumbs} />

          <SelectableAnswer resetKey={fileContent}>
            <HighlightedMarkdown content={fileContent} properNouns={properNouns} />
          </SelectableAnswer>
          {previousFile && (
            <NavButton
              onClick={() => navigate(`/library/${encodeURIComponent(category)}/${encodeURIComponent(previousFile.file_id!)}`)}
              label={t('library.previous')}
              title={previousFile.title || t('library.noFileName')}
              marginTop="2rem"
            />
          )}
          {nextFile && (
            <NavButton
              onClick={() => navigate(`/library/${encodeURIComponent(category)}/${encodeURIComponent(nextFile.file_id!)}`)}
              label={t('library.next')}
              title={nextFile.title || t('library.noFileName')}
              marginTop={previousFile ? '1rem' : '2rem'}
            />
          )}
          <NavButton
            onClick={() => navigate(backPath)}
            label={t('library.backToFiles')}
            title={backText}
            marginTop={previousFile || nextFile ? '1rem' : '2rem'}
          />
      </MinimizedPopupRegion>
    </>
  )
}

export default LibraryFileViewer

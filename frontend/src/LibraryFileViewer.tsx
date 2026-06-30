import { useEffect, useMemo, useState } from 'react'
import { useLoaderData, useRouteLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'
import { useTranslation, useT } from './contexts/LanguageContext'
import PageShell, { PageSection } from './components/PageShell'
import { MinimizedPopupRegion } from './contexts/MinimizedPopupContext'
import Breadcrumbs, { type Crumb } from './components/Breadcrumbs'
import NavButton from './components/NavButton'
import { translate } from './i18n'
import { getLanguageFromUrl } from './utils/language'
import { useAppNavigate } from './hooks/useAppNavigate'
import { useProperNounSelection } from './hooks/useProperNounSelection'
import { buildProperNounMatcher } from './utils/properNouns'
import { rehypeProperNouns } from './utils/rehypeProperNouns'
import {
  categoryLabel,
  findLeafPath,
  flattenLeaves,
  hierarchyCrumbs,
  nodeLabel,
} from './utils/hierarchy'
import type {
  HierarchyNode,
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
  const { answerRef, answerHandlers, selectionUi } = useProperNounSelection(fileContent)
  // Static curated list (per language, fast) and the per-file LLM extraction
  // (null = still in flight). We highlight nothing for the first 2s, then fall
  // back to the static list; the LLM result replaces it whenever it arrives.
  const [staticNouns, setStaticNouns] = useState<string[]>([])
  const [llmNouns, setLlmNouns] = useState<string[] | null>(null)
  const [fallbackElapsed, setFallbackElapsed] = useState(false)
  const properNounMatcher = useMemo(() => {
    const nouns = llmNouns !== null ? llmNouns : fallbackElapsed ? staticNouns : []
    return nouns.length > 0 ? buildProperNounMatcher(nouns) : null
  }, [llmNouns, fallbackElapsed, staticNouns])

  const catLabel = categoryLabel(category, t)

  // Locate the file within the shared category tree to derive the breadcrumb
  // trail, the table of contents, and prev/next. A file absent from the tree
  // (e.g. a quest with no hierarchy placement) simply degrades to no ancestors.
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

  // TOC: rooted at the "section" node (the series/chapter/character grouping),
  // i.e. the ancestor just below the top-level type/character node. Only sections
  // that mark themselves TOC-eligible get one; synthetic buckets of unrelated
  // files (e.g. the "standalone" group) opt out.
  const tocCandidate: HierarchyNode | null =
    ancestors.length >= 2 ? ancestors[1] : ancestors.length === 1 ? ancestors[0] : null
  const tocRoot = tocCandidate?.toc_eligible ? tocCandidate : null
  let tocSections: { title: string; leaves: HierarchyNode[] }[] = []
  let tocTitle = ''
  if (tocRoot?.children) {
    tocSections = tocRoot.children.some((child) => child.children != null)
      ? tocRoot.children.map((group) => ({ title: nodeLabel(group), leaves: flattenLeaves([group]) }))
      : [{ title: '', leaves: tocRoot.children }]
    tocTitle = nodeLabel(tocRoot) || t('library.tableOfContents')
  }
  const tocLeafCount = tocSections.reduce((sum, section) => sum + section.leaves.length, 0)

  // prev/next span the whole category in tree (depth-first) order.
  const leaves = flattenLeaves(nodes)
  const currentIndex = leaves.findIndex((leaf) => leaf.file_id === currentId)
  const previousFile = currentIndex > 0 ? leaves[currentIndex - 1] : null
  const nextFile =
    currentIndex >= 0 && currentIndex < leaves.length - 1 ? leaves[currentIndex + 1] : null

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
    <PageShell flush>
      <MinimizedPopupRegion>
        <PageSection>
        <Breadcrumbs crumbs={crumbs} />

          {tocLeafCount > 1 && (
            <details
              open
              style={{
                margin: '0 0 1.5rem',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-md)',
                padding: '0.75rem 1rem'
              }}
            >
              <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
                {tocTitle}
              </summary>
              <div style={{ marginTop: '0.5rem' }}>
                {tocSections.map((section, sectionIndex) => (
                  <div key={sectionIndex} style={{ marginBottom: '0.5rem' }}>
                    {tocSections.length > 1 && (
                      <p style={{ margin: '0.25rem 0', color: 'var(--color-text-secondary)', fontSize: 'var(--font-sm)' }}>
                        {section.title}
                      </p>
                    )}
                    <div style={{ fontSize: 'var(--font-sm)', lineHeight: 1.8 }}>
                      {section.leaves.map((leaf, leafIndex) => (
                        <span key={leaf.key}>
                          {leafIndex > 0 && <span style={{ color: 'var(--color-text-muted)' }}> / </span>}
                          {leaf.file_id === currentId ? (
                            <span style={{ fontWeight: 600, color: 'var(--color-primary-text)' }}>
                              {leaf.title || t('library.noFileName')}
                            </span>
                          ) : (
                            <button
                              onClick={() => navigate(`/library/${encodeURIComponent(category)}/${encodeURIComponent(leaf.file_id!)}`)}
                              style={{
                                background: 'none',
                                border: 'none',
                                padding: 0,
                                cursor: 'pointer',
                                color: 'var(--color-text)',
                                fontSize: 'inherit',
                                textAlign: 'left'
                              }}
                            >
                              {leaf.title || t('library.noFileName')}
                            </button>
                          )}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </details>
          )}

          <div ref={answerRef} className="answer" onMouseUp={answerHandlers.onMouseUp} onKeyUp={answerHandlers.onKeyUp} onClick={answerHandlers.onClick}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkBreaks]}
              rehypePlugins={properNounMatcher ? [rehypeProperNouns(properNounMatcher)] : []}
            >
              {fileContent}
            </ReactMarkdown>
          </div>
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
        </PageSection>
        </MinimizedPopupRegion>
        {selectionUi}
    </PageShell>
  )
}

export default LibraryFileViewer

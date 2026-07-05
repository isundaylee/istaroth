import { useEffect } from 'react'
import { useLoaderData, useRouteLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import { useT } from './contexts/LanguageContext'
import { MinimizedPopupRegion } from './contexts/PopupCoordinatorContext'
import styles from './LibraryFileViewer.module.css'
import Breadcrumbs, { type Crumb } from './components/Breadcrumbs'
import HighlightedMarkdown from './components/HighlightedMarkdown'
import NavButton from './components/NavButton'
import SelectableAnswer from './components/SelectableAnswer'
import { translate } from './i18n'
import { ApiError, fetchLibraryFile } from './utils/api'
import { getLanguageFromUrl } from './utils/language'
import { useAppNavigate } from './hooks/useAppNavigate'
import { useLibraryProperNouns } from './hooks/useLibraryProperNouns'
import { recordLibraryView } from './utils/libraryRecents'
import {
  categoryLabel,
  findLeafPath,
  hierarchyCrumbs,
  nodeLabel,
} from './utils/hierarchy'
import type { HierarchyResponse, LibraryFileResponse } from './types/api'

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
  let fileData: LibraryFileResponse
  try {
    fileData = await fetchLibraryFile(category, id, language)
  } catch (error) {
    if (error instanceof ApiError) {
      throw new Response(translate(language, 'library.errors.loadFailed'), { status: error.status })
    }
    throw error
  }
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
  const navigate = useAppNavigate()
  const { fileContent, fileTitle, fileId, category, currentId } = useLoaderData() as LoaderData
  const { nodes } = useRouteLoaderData('library-category') as HierarchyResponse
  const properNouns = useLibraryProperNouns(category, fileId)

  const catLabel = categoryLabel(category, t)

  // Locate the file within the shared category tree to derive the breadcrumb
  // trail. A file absent from the tree (e.g. a quest with no hierarchy
  // placement) simply degrades to no ancestors.
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

  useEffect(() => {
    recordLibraryView({ category, fileId: currentId, title: fileTitle })
  }, [category, currentId, fileTitle])

  return (
    <>
      <MinimizedPopupRegion className={styles.measure}>
        <Breadcrumbs crumbs={crumbs} />

          <SelectableAnswer resetKey={fileContent}>
            <HighlightedMarkdown content={fileContent} properNouns={properNouns} />
          </SelectableAnswer>
          <NavButton
            onClick={() => navigate(backPath)}
            label={t('library.backToFiles')}
            title={backText}
            marginTop="2rem"
          />
      </MinimizedPopupRegion>
    </>
  )
}

export default LibraryFileViewer

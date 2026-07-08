import { useEffect } from 'react'
import { useLoaderData, useRouteLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import { useT, useTranslation } from './contexts/LanguageContext'
import { MinimizedPopupRegion } from './contexts/PopupCoordinatorContext'
import Breadcrumbs, { type Crumb } from './components/Breadcrumbs'
import HighlightedMarkdown from './components/HighlightedMarkdown'
import NavButton from './components/NavButton'
import SelectableAnswer from './components/SelectableAnswer'
import ShareLinkButton from './components/ShareLinkButton'
import { translate } from './i18n'
import { ApiError, fetchLibraryFile } from './utils/api'
import { buildUrlWithLanguage, getLanguageFromUrl } from './utils/language'
import { useAppNavigate } from './hooks/useAppNavigate'
import { useLibraryProperNouns } from './hooks/useLibraryProperNouns'
import { recordLibraryView } from './utils/libraryRecents'
import {
  findCategory,
  findLeafPath,
  hierarchyCrumbs,
  nodeLabel,
} from './utils/hierarchy'
import type { LibraryHierarchyResponse, LibraryFileResponse } from './types/api'

interface LoaderData {
  fileContent: string
  fileTitle: string
  fileId: string
  category: string
  currentId: number
  minVersion: string | null
  maxVersion: string | null
}

// AGD history starts at 1.4, so a 1.4 bound means "1.4 or earlier".
const AGD_HISTORY_FLOOR = '1.4'

function formatVersionRange(min: string, max: string): string {
  const minLabel = min === AGD_HISTORY_FLOOR ? `≤${min}` : min
  return min === max ? minLabel : `${minLabel}–${max}`
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
    minVersion: fileData.file_info.min_version,
    maxVersion: fileData.file_info.max_version,
  }
}

function LibraryFileViewer() {
  const t = useT()
  const { language } = useTranslation()
  const navigate = useAppNavigate()
  const { fileContent, fileTitle, fileId, category, currentId, minVersion, maxVersion } =
    useLoaderData() as LoaderData
  const { categories } = useRouteLoaderData('library-root') as LibraryHierarchyResponse
  const categoryEntry = findCategory(categories, category)
  const properNouns = useLibraryProperNouns(category, fileId)

  const catLabel = categoryEntry.title

  // Locate the file within the shared category tree to derive the breadcrumb
  // trail. A file absent from the tree (e.g. a quest with no hierarchy
  // placement) simply degrades to no ancestors.
  const path = findLeafPath(categoryEntry.nodes, currentId)
  const ancestors = path ? path.slice(0, -1) : []
  const browseTo = (depth: number) =>
    `/library/${encodeURIComponent(category)}/browse/${ancestors
      .slice(0, depth)
      .map((node) => node.key)
      .join('/')}`

  const crumbs: Crumb[] = [
    ...hierarchyCrumbs(categoryEntry, ancestors, t),
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
      <MinimizedPopupRegion>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
          <Breadcrumbs
            crumbs={crumbs}
            trailing={
              minVersion !== null && maxVersion !== null
                ? t(
                    // A min/max spread means the file's content accrued across
                    // versions, so phrase it as "added over" rather than "added in".
                    minVersion === maxVersion
                      ? 'library.versionBadge'
                      : 'library.versionBadgeRange'
                  ).replace(
                    '{version}',
                    formatVersionRange(minVersion, maxVersion)
                  )
                : undefined
            }
          />
          <ShareLinkButton
            targetPath={buildUrlWithLanguage(
              `/library/${encodeURIComponent(category)}/${fileId}`,
              '',
              language
            )}
          />
        </div>

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

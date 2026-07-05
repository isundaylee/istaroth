import { Outlet, useParams, useRouteLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import PageShell from './components/PageShell'
import LibraryIndex from './LibraryIndex'
import { useT } from './contexts/LanguageContext'
import { translate } from './i18n'
import { getLanguageFromUrl } from './utils/language'
import type { LibraryHierarchyResponse } from './types/api'

// Loads the whole library once at the root route: every category's document
// tree in a single response. The rail, browse, and file-viewer descendants all
// read it via useRouteLoaderData('library-root').
export async function libraryHierarchyLoader({
  request,
}: LoaderFunctionArgs): Promise<LibraryHierarchyResponse> {
  const language = getLanguageFromUrl(request.url)
  const res = await fetch(`/api/library/hierarchy?language=${language}`)
  if (!res.ok) {
    throw new Response(translate(language, 'library.errors.loadFailed'), { status: res.status })
  }
  return (await res.json()) as LibraryHierarchyResponse
}

// Supplies the library's navigation rail to PageShell's wide two-pane variant:
// one unified tree with a top-level group per category. The frame, split, and
// responsive behavior live in PageShell; only the rail content here is
// library-specific.
function LibraryLayout() {
  const t = useT()
  const params = useParams()
  const { categories } = useRouteLoaderData('library-root') as LibraryHierarchyResponse

  const category = params.category ?? null
  const activeFileId = params.id ? parseInt(params.id, 10) : null
  const activeBrowseKeys = (params['*'] ?? '').split('/').filter(Boolean)

  return (
    <PageShell
      sidebar={
        <LibraryIndex
          categories={categories}
          activeCategory={category}
          activeFileId={activeFileId}
          activeBrowseKeys={activeBrowseKeys}
        />
      }
      sidebarSizing="natural"
      sidebarLabel={t('library.navMenu')}
      hideMobileSidebarToggle={!category}
    >
      <Outlet />
    </PageShell>
  )
}

export default LibraryLayout

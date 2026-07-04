import { Outlet, useParams, useRouteLoaderData } from 'react-router-dom'
import clsx from 'clsx'
import PageShell from './components/PageShell'
import { AppLink } from './components/AppLink'
import LibraryIndex from './LibraryIndex'
import { useT } from './contexts/LanguageContext'
import { categoryLabel } from './utils/hierarchy'
import styles from './LibraryLayout.module.css'
import type { HierarchyResponse, LibraryCategoriesResponse } from './types/api'

// Supplies the library's navigation rail to PageShell's wide two-pane variant:
// the current category's tree inside a category, or the category list at the
// bare /library root. The frame, split, and responsive behavior live in
// PageShell; only the rail content here is library-specific.
function LibraryLayout() {
  const t = useT()
  const params = useParams()
  const { categories } = useRouteLoaderData('library-root') as LibraryCategoriesResponse
  // Present only inside a category (its route loads the whole tree once).
  const tree = useRouteLoaderData('library-category') as HierarchyResponse | undefined

  const category = params.category
  const activeFileId = params.id ? parseInt(params.id, 10) : null
  const activeBrowseKeys = (params['*'] ?? '').split('/').filter(Boolean)

  const sidebar =
    category && tree ? (
      <LibraryIndex
        category={category}
        nodes={tree.nodes}
        activeFileId={activeFileId}
        activeBrowseKeys={activeBrowseKeys}
      />
    ) : (
      <>
        <p className={styles.railHead}>{t('library.title')}</p>
        <nav className={styles.railNav}>
          {categories.map((value) => (
            <AppLink
              key={value}
              to={`/library/${encodeURIComponent(value)}`}
              className={clsx(styles.railItem, value === category && styles.railItemActive)}
            >
              {categoryLabel(value, t)}
            </AppLink>
          ))}
        </nav>
      </>
    )

  return (
    <PageShell sidebar={sidebar} sidebarLabel={t('library.navMenu')} hideMobileSidebarToggle={!category}>
      <Outlet />
    </PageShell>
  )
}

export default LibraryLayout

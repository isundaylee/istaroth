import { Outlet, useParams, useRouteLoaderData } from 'react-router-dom'
import clsx from 'clsx'
import Navigation from './components/Navigation'
import { AppLink } from './components/AppLink'
import LibraryIndex from './LibraryIndex'
import { useT } from './contexts/LanguageContext'
import { categoryLabel } from './utils/hierarchy'
import styles from './LibraryLayout.module.css'
import type { HierarchyResponse, LibraryCategoriesResponse } from './types/api'

// The connected two-pane frame for the whole library section: the embedded nav
// strip, the persistent navigation rail, and the Folio (child routes via
// <Outlet/>) share one hairline-bordered panel. The rail lists the categories
// and highlights the current one; later stages deepen it into the full tree.
function LibraryLayout() {
  const t = useT()
  const params = useParams()
  const { categories } = useRouteLoaderData('library-root') as LibraryCategoriesResponse
  // Present only inside a category (its route loads the whole tree once).
  const tree = useRouteLoaderData('library-category') as HierarchyResponse | undefined

  const category = params.category
  const activeFileId = params.id ? parseInt(params.id, 10) : null
  const activeBrowseKeys = (params['*'] ?? '').split('/').filter(Boolean)

  return (
    <div className={styles.frame}>
      <div className={styles.panel}>
        <Navigation embedded />
        <div className={styles.split}>
          <aside className={styles.rail}>
            {category && tree ? (
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
            )}
          </aside>
          <div className={styles.folio}>
            <Outlet />
          </div>
        </div>
      </div>
    </div>
  )
}

export default LibraryLayout

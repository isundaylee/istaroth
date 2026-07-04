import { useState } from 'react'
import { useRouteLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import Button from './components/Button'
import { useT, useTranslation } from './contexts/LanguageContext'
import { translate } from './i18n'
import { getLanguageFromUrl } from './utils/language'
import { useAppNavigate } from './hooks/useAppNavigate'
import { getLibraryRecents } from './utils/libraryRecents'
import { categoryLabel, flattenLeaves } from './utils/hierarchy'
import styles from './LibraryEntry.module.css'
import type { HierarchyResponse, LibraryCategoriesResponse } from './types/api'

export async function libraryEntryLoader({ request }: LoaderFunctionArgs): Promise<LibraryCategoriesResponse> {
  const language = getLanguageFromUrl(request.url)

  const res = await fetch(`/api/library/categories?language=${language}`)
  if (!res.ok) {
    throw new Response(translate(language, 'library.errors.loadFailed'), { status: res.status })
  }
  return (await res.json()) as LibraryCategoriesResponse
}

function LibraryEntry() {
  const t = useT()
  const { language } = useTranslation()
  const navigate = useAppNavigate()
  const { categories } = useRouteLoaderData('library-root') as LibraryCategoriesResponse
  const [recents] = useState(getLibraryRecents)

  const openRandom = async () => {
    const category = categories[Math.floor(Math.random() * categories.length)]
    if (!category) return

    const res = await fetch(`/api/library/hierarchy/${encodeURIComponent(category)}?language=${language}`)
    if (!res.ok) return

    const leaves = flattenLeaves(((await res.json()) as HierarchyResponse).nodes)
    const leaf = leaves[Math.floor(Math.random() * leaves.length)]
    if (leaf?.file_id == null) return

    navigate(`/library/${encodeURIComponent(category)}/${encodeURIComponent(leaf.file_id)}`)
  }

  return (
    <div className={styles.frontDesk}>
      <div className={styles.intro}>
        <p className={styles.kicker}>{t('library.frontDesk.kicker')}</p>
        <h1 className={styles.title}>{t('library.frontDesk.title')}</h1>
        <p className={styles.subtitle}>{t('library.frontDesk.subtitle')}</p>
      </div>

      {recents.length > 0 && (
        <section className={styles.section}>
          <p className={styles.sectionHead}>{t('library.frontDesk.continueReading')}</p>
          <div className={styles.recents}>
            {recents.map((recent) => (
              <button
                key={`${recent.category}-${recent.fileId}`}
                className={styles.recentCard}
                type="button"
                onClick={() =>
                  navigate(`/library/${encodeURIComponent(recent.category)}/${encodeURIComponent(recent.fileId)}`)
                }
              >
                <span className={styles.recentCategory}>{categoryLabel(recent.category, t)}</span>
                <span className={styles.recentTitle}>{recent.title || t('library.noFileName')}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      <div className={styles.actions}>
        <Button type="button" variant="ghost" onClick={openRandom}>
          {t('library.frontDesk.random')}
        </Button>
      </div>
    </div>
  )
}

export default LibraryEntry

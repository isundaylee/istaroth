import { useMemo, useState, type ReactNode } from 'react'
import { useRouteLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import { AppLink } from './components/AppLink'
import Button from './components/Button'
import Card from './components/Card'
import Composer from './components/Composer'
import ErrorDisplay from './components/ErrorDisplay'
import Toggle from './components/Toggle'
import { useT, useTranslation } from './contexts/LanguageContext'
import { useLibraryRetrieve } from './hooks/useLibraryRetrieve'
import { translate } from './i18n'
import { getLanguageFromUrl } from './utils/language'
import { useAppNavigate } from './hooks/useAppNavigate'
import { getLibraryRecents } from './utils/libraryRecents'
import { categoryLabel, flattenLeaves } from './utils/hierarchy'
import styles from './LibraryEntry.module.css'
import type { HierarchyResponse, LibraryCategoriesResponse } from './types/api'

const _escapeRegExp = (value: string): string =>
  value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const _highlightSnippet = (snippet: string, query: string): ReactNode => {
  const tokens = Array.from(new Set(query.split(/\s+/).map((token) => token.trim()).filter(Boolean)))
  if (tokens.length === 0) return snippet

  const escapedTokens = tokens.map(_escapeRegExp).join('|')
  const splitRegex = new RegExp(`(${escapedTokens})`, 'gi')
  const matchRegex = new RegExp(`^(${escapedTokens})$`, 'i')

  return snippet.split(splitRegex).map((part, index) => (
    matchRegex.test(part)
      ? <span key={`${part}-${index}`} className={styles.highlight}>{part}</span>
      : part
  ))
}

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
  const {
    formParams,
    setFormParams,
    submittedParams,
    results,
    error,
    loading,
    submit,
  } = useLibraryRetrieve()

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

  const resultsContent = useMemo(() => {
    if (!submittedParams || loading) return null
    if (results.length === 0) {
      return (
        <Card style={{ margin: 0 }}>
          <p>{t('retrieve.noResults')}</p>
        </Card>
      )
    }
    return (
      <div className={styles.results}>
        {results.map((result) => (
          <Card key={`${result.file_info.category}-${result.file_info.id}`} style={{ margin: 0 }}>
            <div className={styles.resultCard}>
              <AppLink to={`/library/${encodeURIComponent(result.file_info.category)}/${encodeURIComponent(result.file_info.id)}`} className={styles.resultTitle}>
                {result.file_info.title || t('library.noFileName')}
              </AppLink>
              <p className={styles.snippet}>{_highlightSnippet(result.snippet, submittedParams.query)}</p>
            </div>
          </Card>
        ))}
      </div>
    )
  }, [loading, results, submittedParams, t])

  const landing = (
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
  const hasActiveSearch = submittedParams !== null || loading

  return (
    <div className={styles.entry}>
      <section className={styles.search}>
        <Composer
          submitOnEnter
          value={formParams.query}
          onChange={(query) => setFormParams({ ...formParams, query })}
          onSubmit={submit}
          placeholder={t('retrieve.placeholder')}
          disabled={loading}
          controls={
            <Toggle
              value={formParams.semantic ? 'semantic' : 'bm25'}
              onChange={(mode) => setFormParams({ ...formParams, semantic: mode === 'semantic' })}
              options={[
                { value: 'bm25', label: t('retrieve.searchModeBm25') },
                { value: 'semantic', label: t('retrieve.searchModeSemantic') },
              ]}
              disabled={loading}
              aria-label={t('retrieve.searchMode')}
            />
          }
          actions={
            <Button
              type="submit"
              variant="submit"
              disabled={loading || (Boolean(formParams.query.trim()) && formParams.query.trim() === submittedParams?.query && formParams.semantic === submittedParams?.semantic)}
            >
              {loading ? t('retrieve.submitting') : t('retrieve.submitButton')}
            </Button>
          }
        />
        {error && <ErrorDisplay error={error} />}
      </section>

      {hasActiveSearch ? resultsContent : landing}
    </div>
  )
}

export default LibraryEntry

import { useMemo, useState, type ReactNode } from 'react'
import { useParams, type LoaderFunctionArgs } from 'react-router-dom'
import { AppLink } from './components/AppLink'
import Button from './components/Button'
import Card from './components/Card'
import Composer from './components/Composer'
import ErrorDisplay from './components/ErrorDisplay'
import { useOpenSidebarDrawer } from './components/PageShell'
import Toggle from './components/Toggle'
import { useT } from './contexts/LanguageContext'
import { useLibraryRetrieve } from './hooks/useLibraryRetrieve'
import { translate } from './i18n'
import { getLanguageFromUrl } from './utils/language'
import { useAppNavigate } from './hooks/useAppNavigate'
import { getLibraryRecents } from './utils/libraryRecents'
import { categoryLabel } from './utils/hierarchy'
import styles from './LibraryEntry.module.css'
import type { LibraryCategoriesResponse } from './types/api'

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
  const navigate = useAppNavigate()
  const openSidebarDrawer = useOpenSidebarDrawer()
  const params = useParams()
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

  const openEntry = (entry: { category: string; fileId: number }) =>
    navigate(`/library/${encodeURIComponent(entry.category)}/${encodeURIComponent(entry.fileId)}`)

  const resultsContent = useMemo(() => {
    if (!submittedParams || loading) return null
    if (results.length === 0) {
      return (
        <Card style={{ margin: 0 }}>
          <p>{t('library.search.noResults')}</p>
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

  const hasActiveSearch = submittedParams !== null || loading

  return (
    <div className={styles.entry}>
      <div className={styles.intro}>
        <h1 className={styles.title}>{t('library.frontDesk.title')}</h1>
        <p className={styles.subtitle}>{t('library.frontDesk.subtitle')}</p>
        {!params.category && (
          <button type="button" className={styles.contentsButton} onClick={openSidebarDrawer}>
            <span aria-hidden>☰</span>
            {t('library.frontDesk.openContents')}
          </button>
        )}
      </div>

      <section className={styles.section}>
        <div className={styles.sectionTitleRow}>
          <h2 className={styles.sectionHead}>{t('library.frontDesk.search')}</h2>
        </div>
        <Composer
          submitOnEnter
          value={formParams.query}
          onChange={(query) => setFormParams({ ...formParams, query })}
          onSubmit={submit}
          placeholder={t('library.search.placeholder')}
          disabled={loading}
          controls={
            <Toggle
              value={formParams.semantic ? 'semantic' : 'bm25'}
              onChange={(mode) => setFormParams({ ...formParams, semantic: mode === 'semantic' })}
              options={[
                { value: 'bm25', label: t('library.search.searchModeBm25') },
                { value: 'semantic', label: t('library.search.searchModeSemantic') },
              ]}
              disabled={loading}
              aria-label={t('library.search.searchMode')}
            />
          }
          actions={
            <Button
              type="submit"
              variant="submit"
              disabled={loading || (Boolean(formParams.query.trim()) && formParams.query.trim() === submittedParams?.query && formParams.semantic === submittedParams?.semantic)}
            >
              {loading ? t('library.search.submitting') : t('library.search.submitButton')}
            </Button>
          }
        />
        {error && <ErrorDisplay error={error} />}
      </section>

      {!hasActiveSearch && (
        <section className={styles.section}>
          <div className={styles.sectionTitleRow}>
            <h2 className={styles.sectionHead}>{t('library.frontDesk.continueReading')}</h2>
          </div>
          {recents.length > 0 ? (
            <div className={styles.cardRow}>
              {recents.slice(0, 4).map((recent) => (
                <button
                  key={`${recent.category}-${recent.fileId}`}
                  className={styles.entryCard}
                  type="button"
                  onClick={() => openEntry({ category: recent.category, fileId: recent.fileId })}
                >
                  <span className={styles.cardCategory}>{categoryLabel(recent.category, t)}</span>
                  <span className={styles.cardTitle}>{recent.title || t('library.noFileName')}</span>
                </button>
              ))}
            </div>
          ) : (
            <p className={styles.emptyText}>{t('library.frontDesk.noRecents')}</p>
          )}
        </section>
      )}
      {hasActiveSearch && resultsContent}
    </div>
  )
}

export default LibraryEntry

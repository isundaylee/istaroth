import { useMemo, useState, type ReactNode } from 'react'
import { useParams, useRouteLoaderData } from 'react-router-dom'
import { AppLink } from './components/AppLink'
import Button from './components/Button'
import Card from './components/Card'
import Composer from './components/Composer'
import { useOpenSidebarDrawer } from './components/PageShell'
import Toggle from './components/Toggle'
import { useT } from './contexts/LanguageContext'
import { useLibraryRetrieve } from './hooks/useLibraryRetrieve'
import { useAppNavigate } from './hooks/useAppNavigate'
import { getLibraryRecents } from './utils/libraryRecents'
import { findCategory } from './utils/hierarchy'
import styles from './LibraryEntry.module.css'
import type { LibraryHierarchyResponse, LibraryRetrieveResponse } from './types/api'

interface _ResultGroup {
  fileInfo: LibraryRetrieveResponse['results'][number]['file_info']
  passages: string[]
}

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

function _groupByDocument(results: LibraryRetrieveResponse['results']): _ResultGroup[] {
  const groups: _ResultGroup[] = []
  const byKey = new Map<string, _ResultGroup>()
  for (const result of results) {
    const key = `${result.file_info.category}-${result.file_info.id}`
    let group = byKey.get(key)
    if (!group) {
      group = { fileInfo: result.file_info, passages: [] }
      byKey.set(key, group)
      groups.push(group)
    }
    group.passages.push(result.snippet)
  }
  return groups
}

function LibraryEntry() {
  const t = useT()
  const navigate = useAppNavigate()
  const openSidebarDrawer = useOpenSidebarDrawer()
  const params = useParams()
  const { categories } = useRouteLoaderData('library-root') as LibraryHierarchyResponse
  // A recent stored before a corpus change may reference a category that no
  // longer exists; such an entry is dead (opening it would 404), so drop it.
  const [recents] = useState(() =>
    getLibraryRecents().filter((recent) =>
      categories.some((entry) => entry.category === recent.category)
    )
  )
  const {
    formParams,
    setFormParams,
    submittedParams,
    results,
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
    const groups = _groupByDocument(results)
    return (
      <div className={styles.results}>
        {groups.map((group) => (
          <article key={`${group.fileInfo.category}-${group.fileInfo.id}`} className={styles.result}>
            <header className={styles.resultHead}>
              <AppLink to={`/library/${encodeURIComponent(group.fileInfo.category)}/${encodeURIComponent(group.fileInfo.id)}`} className={styles.resultTitle}>
                {group.fileInfo.title || t('library.noFileName')}
              </AppLink>
              <span className={styles.resultCat}>{findCategory(categories, group.fileInfo.category).title}</span>
              {group.passages.length > 1 && (
                <span className={styles.resultCat}>
                  {group.passages.length} {t('library.frontDesk.matches')}
                </span>
              )}
            </header>
            {group.passages.map((passage, index) => (
              <p key={index} className={styles.excerpt}>{_highlightSnippet(passage, submittedParams.query)}</p>
            ))}
          </article>
        ))}
      </div>
    )
  }, [categories, loading, results, submittedParams, t])

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
                  <span className={styles.cardCategory}>{findCategory(categories, recent.category).title}</span>
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

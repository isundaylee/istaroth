import React from 'react'
import { useNavigate, useLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import { useT } from './contexts/LanguageContext'
import Navigation from './components/Navigation'
import Card from './components/Card'
import PageCard from './components/PageCard'
import ErrorDisplay from './components/ErrorDisplay'
import LibraryHeader from './components/LibraryHeader'
import { getLanguageFromUrl } from './utils/language'
import type { LibraryFilesResponse, LibraryFileInfo } from './types/api'

interface LoaderData {
  files: LibraryFileInfo[]
  category: string
  error?: string
}

export async function libraryFilesPageLoader({ params, request }: LoaderFunctionArgs): Promise<LoaderData> {
  const { category } = params
  if (!category) {
    return { files: [], category: '', error: 'Invalid category' }
  }

  const language = getLanguageFromUrl(request.url)

  try {
    const res = await fetch(
      `/api/library/files/${encodeURIComponent(category)}?language=${language}`
    )
    if (!res.ok) {
      return { files: [], category, error: 'Failed to load files' }
    }
    const data = (await res.json()) as LibraryFilesResponse
    return { files: data.files, category }
  } catch (err) {
    return { files: [], category, error: err instanceof Error ? err.message : 'Failed to load files' }
  }
}

function LibraryFilesPage() {
  const t = useT()
  const navigate = useNavigate()
  const { files, category, error } = useLoaderData() as LoaderData

  const translateCategory = (category: string): string => {
    const translationKey = `library.categories.${category}`
    const translated = t(translationKey)
    return translated === translationKey ? category : translated
  }

  return (
    <div className="app">
      <Navigation />
      <main className="main">
        {error && <ErrorDisplay error={error} />}
        <PageCard>
          <LibraryHeader
            title={category ? translateCategory(category) : ''}
            backPath="/library"
            backText={t('library.backToCategories')}
          />

          {!error && files.length === 0 && (
            <Card style={{ margin: '1rem 0' }}>
              <p>{t('library.noFiles')}</p>
            </Card>
          )}

          {!error && files.length > 0 && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
                gap: '1rem'
              }}
            >
              {files.map((file) => (
                <div
                  key={file.id}
                  onClick={() => category && navigate(`/library/${encodeURIComponent(category)}/${encodeURIComponent(file.id)}`)}
                  onMouseEnter={(e: React.MouseEvent<HTMLDivElement>) => {
                    const card = e.currentTarget.querySelector('.card') as HTMLElement
                    if (card) {
                      card.style.backgroundColor = '#f0f0f0'
                      card.style.transform = 'translateY(-2px)'
                    }
                  }}
                  onMouseLeave={(e: React.MouseEvent<HTMLDivElement>) => {
                    const card = e.currentTarget.querySelector('.card') as HTMLElement
                    if (card) {
                      card.style.backgroundColor = '#f8f9fa'
                      card.style.transform = 'translateY(0)'
                    }
                  }}
                >
                  <Card
                    style={{
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                      padding: '1rem',
                      margin: 0
                    }}
                  >
                    <p style={{ margin: 0, wordBreak: 'break-word' }}>
                      {file.title || t('library.noFileName')}
                    </p>
                  </Card>
                </div>
              ))}
            </div>
          )}
        </PageCard>
      </main>
    </div>
  )
}

export default LibraryFilesPage

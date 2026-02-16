import React from 'react'
import { useLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import { useT } from './contexts/LanguageContext'
import Navigation from './components/Navigation'
import Card from './components/Card'
import PageCard from './components/PageCard'
import LibraryHeader from './components/LibraryHeader'
import { translate } from './i18n'
import { getLanguageFromUrl } from './utils/language'
import { useAppNavigate } from './hooks/useAppNavigate'
import type { LibraryFilesResponse, LibraryFileInfo } from './types/api'

interface LoaderData {
  files: LibraryFileInfo[]
  category: string
}

export async function libraryFilesPageLoader({ params, request }: LoaderFunctionArgs): Promise<LoaderData> {
  const { category } = params
  if (!category) {
    throw new Response(translate(getLanguageFromUrl(request.url), 'library.errors.invalidCategory'), { status: 400 })
  }

  const language = getLanguageFromUrl(request.url)

  const res = await fetch(
    `/api/library/files/${encodeURIComponent(category)}?language=${language}`
  )
  if (!res.ok) {
    throw new Response(translate(language, 'library.errors.loadFailed'), { status: res.status })
  }
  const data = (await res.json()) as LibraryFilesResponse
  return { files: data.files, category }
}

function LibraryFilesPage() {
  const t = useT()
  const navigate = useAppNavigate()
  const { files, category } = useLoaderData() as LoaderData
  const [filter, setFilter] = React.useState('')

  const filteredFiles = files.filter((file) =>
    (file.title || '').toLowerCase().includes(filter.toLowerCase())
  )

  const translateCategory = (category: string): string => {
    const translationKey = `library.categories.${category}`
    const translated = t(translationKey)
    return translated === translationKey ? category : translated
  }

  return (
    <>
      <Navigation />
      <main className="main">
        <PageCard>
          <LibraryHeader
            title={translateCategory(category)}
            backPath="/library"
            backText={t('library.backToCategories')}
          />

          {files.length === 0 && (
            <Card style={{ margin: '1rem 0' }}>
              <p>{t('library.noFiles')}</p>
            </Card>
          )}

          {files.length > 0 && (
            <>
            <input
              type="text"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder={t('library.filterPlaceholder')}
              style={{
                width: '100%',
                padding: '0.6rem 1rem',
                marginBottom: '1rem',
                border: '1px solid #ddd',
                borderRadius: '8px',
                fontSize: '0.95rem',
                boxSizing: 'border-box',
                outline: 'none'
              }}
            />

            {filteredFiles.length === 0 ? (
              <Card style={{ margin: '1rem 0' }}>
                <p>{t('library.noFilterResults')}</p>
              </Card>
            ) : (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
                gap: '1rem'
              }}
            >
              {filteredFiles.map((file) => (
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
            </>
          )}
        </PageCard>
      </main>
    </>
  )
}

export default LibraryFilesPage

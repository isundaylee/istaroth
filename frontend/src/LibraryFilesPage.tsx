import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useT, useTranslation } from './contexts/LanguageContext'
import Navigation from './components/Navigation'
import Card from './components/Card'
import PageCard from './components/PageCard'
import ErrorDisplay from './components/ErrorDisplay'
import LibraryHeader from './components/LibraryHeader'
import type { LibraryFilesResponse } from './types/api'

function LibraryFilesPage() {
  const t = useT()
  const { language } = useTranslation()
  const { category } = useParams<{ category: string }>()
  const navigate = useNavigate()
  const [files, setFiles] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const translateCategory = (category: string): string => {
    const translationKey = `library.categories.${category}`
    const translated = t(translationKey)
    return translated === translationKey ? category : translated
  }

  useEffect(() => {
    const fetchFiles = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(
          `/api/library/files/${encodeURIComponent(category)}?language=${language}`
        )
        if (!res.ok) {
          throw new Error(t('library.errors.loadFailed'))
        }
        const data = (await res.json()) as LibraryFilesResponse
        setFiles(data.files)
      } catch (err) {
        setError(err instanceof Error ? err.message : t('library.errors.unknown'))
      } finally {
        setLoading(false)
      }
    }

    fetchFiles()
  }, [category, language, t])

  return (
    <div className="app">
      <Navigation />
      <main className="main">
        {error && <ErrorDisplay error={error} />}
        <PageCard>
          <LibraryHeader
            title={translateCategory(category)}
            backPath="/library"
            backText={t('library.backToCategories')}
          />

          {loading && (
            <div style={{ textAlign: 'center', padding: '2rem' }}>
              {t('common.loading')}
            </div>
          )}

          {!loading && files.length === 0 && (
            <Card style={{ margin: '1rem 0' }}>
              <p>{t('library.noFiles')}</p>
            </Card>
          )}

          {!loading && files.length > 0 && (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
                gap: '1rem'
              }}
            >
              {files.map((file) => (
                <div
                  key={file}
                  onClick={() => navigate(`/library/${encodeURIComponent(category)}/${encodeURIComponent(file)}`)}
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
                    <p style={{ margin: 0, wordBreak: 'break-word' }}>{file}</p>
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

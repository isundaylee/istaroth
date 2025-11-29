import React, { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import { useT, useTranslation } from './contexts/LanguageContext'
import Navigation from './components/Navigation'
import Card from './components/Card'
import PageCard from './components/PageCard'
import ErrorDisplay from './components/ErrorDisplay'
import type {
  LibraryCategoriesResponse,
  LibraryFilesResponse,
  LibraryFileResponse
} from './types/api'

function LibraryPage() {
  const t = useT()
  const { language } = useTranslation()
  const [categories, setCategories] = useState<string[]>([])
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [files, setFiles] = useState<string[]>([])
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [fileContent, setFileContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const translateCategory = (category: string): string => {
    const translationKey = `library.categories.${category}`
    const translated = t(translationKey)
    return translated === translationKey ? category : translated
  }

  useEffect(() => {
    const fetchCategories = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(`/api/library/categories?language=${language}`)
        if (!res.ok) {
          throw new Error(t('library.errors.loadFailed'))
        }
        const data = (await res.json()) as LibraryCategoriesResponse
        setCategories(data.categories)
      } catch (err) {
        setError(err instanceof Error ? err.message : t('library.errors.unknown'))
      } finally {
        setLoading(false)
      }
    }

    fetchCategories()
  }, [language, t])

  useEffect(() => {
    if (!selectedCategory) {
      setFiles([])
      return
    }

    const fetchFiles = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(
          `/api/library/files/${encodeURIComponent(selectedCategory)}?language=${language}`
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
  }, [selectedCategory, language, t])

  useEffect(() => {
    if (!selectedCategory || !selectedFile) {
      setFileContent(null)
      return
    }

    const fetchFileContent = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(
          `/api/library/file/${encodeURIComponent(selectedCategory)}/${encodeURIComponent(selectedFile)}?language=${language}`
        )
        if (!res.ok) {
          throw new Error(t('library.errors.loadFailed'))
        }
        const data = (await res.json()) as LibraryFileResponse
        setFileContent(data.content)
      } catch (err) {
        setError(err instanceof Error ? err.message : t('library.errors.unknown'))
      } finally {
        setLoading(false)
      }
    }

    fetchFileContent()
  }, [selectedCategory, selectedFile, language, t])

  return (
    <div className="app">
      <Navigation />
      <main className="main">
          {error && <ErrorDisplay error={error} />}
          <PageCard>
            {!selectedCategory && (
              <h1 style={{ marginBottom: '2rem', textAlign: 'center', fontSize: '2.5rem', color: '#2c3e50' }}>
                {t('library.title')}
              </h1>
            )}

            {selectedCategory && (
              <div style={{ marginBottom: '2rem', display: 'flex', justifyContent: 'center', alignItems: 'center', position: 'relative' }}>
                <h1 style={{ margin: 0, fontSize: '2.5rem', color: '#2c3e50', textAlign: 'center' }}>
                  {translateCategory(selectedCategory)}
                </h1>
                <button
                  onClick={() => {
                    if (selectedFile) {
                      setSelectedFile(null)
                      setFileContent(null)
                    } else {
                      setSelectedCategory(null)
                      setFiles([])
                    }
                  }}
                  style={{
                    padding: '0.5rem 1rem',
                    border: '1px solid #ddd',
                    borderRadius: '4px',
                    backgroundColor: 'white',
                    cursor: 'pointer',
                    position: 'absolute',
                    right: 0
                  }}
                >
                  ← {selectedFile ? t('library.backToFiles') : t('library.backToCategories')}
                </button>
              </div>
            )}

            {loading && !selectedCategory && (
              <div style={{ textAlign: 'center', padding: '2rem' }}>
                {t('common.loading')}
              </div>
            )}

            {!loading && !error && !selectedCategory && (
              <div>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: '1.5rem'
                  }}
                >
                  {categories.map((category) => (
                    <div
                      key={category}
                      onClick={() => setSelectedCategory(category)}
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
                      style={{
                        aspectRatio: '1',
                        minHeight: 0
                      }}
                    >
                      <Card
                        style={{
                          cursor: 'pointer',
                          transition: 'all 0.2s',
                          padding: '1.5rem',
                          margin: 0,
                          height: '100%',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          borderRadius: '12px'
                        }}
                      >
                        <h3 style={{ margin: 0, textAlign: 'center', fontSize: '1.1rem', color: '#2c3e50' }}>
                          {translateCategory(category)}
                        </h3>
                      </Card>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {selectedCategory && !selectedFile && (
              <div>
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
                        onClick={() => setSelectedFile(file)}
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
              </div>
            )}

            {selectedCategory && selectedFile && (
              <div>
                {loading && (
                  <div style={{ textAlign: 'center', padding: '2rem' }}>
                    {t('common.loading')}
                  </div>
                )}

                {!loading && fileContent && (
                  <div className="answer">
                    <ReactMarkdown>{fileContent}</ReactMarkdown>
                  </div>
                )}

                {!loading && !fileContent && error && (
                  <Card style={{ margin: '1rem 0', backgroundColor: '#fee', borderColor: '#f00' }}>
                    <p style={{ color: '#c00' }}>{error}</p>
                  </Card>
                )}
              </div>
            )}
          </PageCard>
      </main>
    </div>
  )
}

export default LibraryPage

import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { useT, useTranslation } from './contexts/LanguageContext'
import Navigation from './components/Navigation'
import Card from './components/Card'
import PageCard from './components/PageCard'
import ErrorDisplay from './components/ErrorDisplay'
import type { LibraryFileResponse } from './types/api'

function LibraryFileViewer() {
  const t = useT()
  const { language } = useTranslation()
  const { category, filename } = useParams<{ category: string; filename: string }>()
  const navigate = useNavigate()
  const [fileContent, setFileContent] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const translateCategory = (category: string): string => {
    const translationKey = `library.categories.${category}`
    const translated = t(translationKey)
    return translated === translationKey ? category : translated
  }

  useEffect(() => {
    const fetchFileContent = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(
          `/api/library/file/${encodeURIComponent(category)}/${encodeURIComponent(filename)}?language=${language}`
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
  }, [category, filename, language, t])

  return (
    <div className="app">
      <Navigation />
      <main className="main">
        {error && <ErrorDisplay error={error} />}
        <PageCard>
          <div style={{ marginBottom: '2rem', display: 'flex', justifyContent: 'center', alignItems: 'center', position: 'relative' }}>
            <h1 style={{ margin: 0, fontSize: '2.5rem', color: '#2c3e50', textAlign: 'center' }}>
              {translateCategory(category)}
            </h1>
            <button
              onClick={() => navigate(`/library/${encodeURIComponent(category)}`)}
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
              ← {t('library.backToFiles')}
            </button>
          </div>

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
        </PageCard>
      </main>
    </div>
  )
}

export default LibraryFileViewer

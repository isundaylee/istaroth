import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import { useT, useTranslation } from './contexts/LanguageContext'
import Navigation from './components/Navigation'
import Card from './components/Card'
import PageCard from './components/PageCard'
import ErrorDisplay from './components/ErrorDisplay'
import LibraryHeader from './components/LibraryHeader'
import NavButton from './components/NavButton'
import type { LibraryFileResponse, LibraryFilesResponse, LibraryFileInfo } from './types/api'

function LibraryFileViewer() {
  const t = useT()
  const { language } = useTranslation()
  const navigate = useNavigate()
  const { category, id } = useParams<{ category: string; id: string }>()
  const [fileContent, setFileContent] = useState<string | null>(null)
  const [fileTitle, setFileTitle] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [previousFile, setPreviousFile] = useState<LibraryFileInfo | null>(null)
  const [nextFile, setNextFile] = useState<LibraryFileInfo | null>(null)

  const translateCategory = (category: string): string => {
    const translationKey = `library.categories.${category}`
    const translated = t(translationKey)
    return translated === translationKey ? category : translated
  }

  useEffect(() => {
    if (!category || !id) {
      setError(t('library.errors.unknown'))
      setLoading(false)
      return
    }

    const fetchFileContent = async () => {
      setLoading(true)
      setError(null)
      setPreviousFile(null)
      setNextFile(null)
      try {
        const res = await fetch(
          `/api/library/file/${encodeURIComponent(category)}/${encodeURIComponent(id)}?language=${language}`
        )
        if (!res.ok) {
          throw new Error(t('library.errors.loadFailed'))
        }
        const data = (await res.json()) as LibraryFileResponse
        setFileContent(data.content)
        setFileTitle(data.file_info.title)
      } catch (err) {
        setError(err instanceof Error ? err.message : t('library.errors.unknown'))
      } finally {
        setLoading(false)
      }
    }

    const fetchNavigationFiles = async () => {
      try {
        const res = await fetch(
          `/api/library/files/${encodeURIComponent(category)}?language=${language}`
        )
        if (!res.ok) {
          return
        }
        const data = (await res.json()) as LibraryFilesResponse
        const currentId = parseInt(id, 10)
        const currentIndex = data.files.findIndex((file) => file.id === currentId)

        if (currentIndex > 0) {
          setPreviousFile(data.files[currentIndex - 1])
        } else {
          setPreviousFile(null)
        }

        if (currentIndex >= 0 && currentIndex < data.files.length - 1) {
          setNextFile(data.files[currentIndex + 1])
        } else {
          setNextFile(null)
        }
      } catch (err) {
        // Silently fail - navigation is optional
      }
    }

    fetchFileContent()
    fetchNavigationFiles()
  }, [category, id, language, t])

  if (!category || !id) {
    return (
      <div className="app">
        <Navigation />
        <main className="main">
          <ErrorDisplay error={t('library.errors.unknown')} />
        </main>
      </div>
    )
  }

  return (
    <div className="app">
      <Navigation />
      <main className="main">
        {error && <ErrorDisplay error={error} />}
        <PageCard>
          <LibraryHeader
            title={fileTitle || translateCategory(category)}
            backPath={`/library/${encodeURIComponent(category)}`}
            backText={t('library.backToFiles')}
          />

          {loading && (
            <div style={{ textAlign: 'center', padding: '2rem' }}>
              {t('common.loading')}
            </div>
          )}

          {!loading && fileContent && (
            <>
              <div className="answer">
                <ReactMarkdown remarkPlugins={[remarkBreaks]}>{fileContent}</ReactMarkdown>
              </div>
              {previousFile && (
                <NavButton
                  onClick={() => navigate(`/library/${encodeURIComponent(category)}/${encodeURIComponent(previousFile.id)}`)}
                  label={t('library.previous')}
                  title={previousFile.title || t('library.noFileName')}
                  marginTop="2rem"
                />
              )}
              {nextFile && (
                <NavButton
                  onClick={() => navigate(`/library/${encodeURIComponent(category)}/${encodeURIComponent(nextFile.id)}`)}
                  label={t('library.next')}
                  title={nextFile.title || t('library.noFileName')}
                  marginTop={previousFile ? '1rem' : '2rem'}
                />
              )}
            </>
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

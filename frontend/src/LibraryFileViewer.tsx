import { useNavigate, useLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import { useT } from './contexts/LanguageContext'
import Navigation from './components/Navigation'
import Card from './components/Card'
import PageCard from './components/PageCard'
import ErrorDisplay from './components/ErrorDisplay'
import LibraryHeader from './components/LibraryHeader'
import NavButton from './components/NavButton'
import { getLanguageFromUrl } from './utils/language'
import type { LibraryFileResponse, LibraryFilesResponse, LibraryFileInfo } from './types/api'

interface LoaderData {
  fileContent: string
  fileTitle: string
  previousFile: LibraryFileInfo | null
  nextFile: LibraryFileInfo | null
  category: string
  error?: string
}

export async function libraryFileViewerLoader({ params, request }: LoaderFunctionArgs): Promise<LoaderData> {
  const { category, id } = params
  if (!category || !id) {
    return { fileContent: '', fileTitle: '', previousFile: null, nextFile: null, category: '', error: 'Invalid params' }
  }

  const language = getLanguageFromUrl(request.url)

  const [fileRes, filesRes] = await Promise.all([
    fetch(`/api/library/file/${encodeURIComponent(category)}/${encodeURIComponent(id)}?language=${language}`),
    fetch(`/api/library/files/${encodeURIComponent(category)}?language=${language}`)
  ])

  if (!fileRes.ok) {
    return { fileContent: '', fileTitle: '', previousFile: null, nextFile: null, category, error: 'Failed to load file' }
  }

  const fileData = (await fileRes.json()) as LibraryFileResponse
  let previousFile: LibraryFileInfo | null = null
  let nextFile: LibraryFileInfo | null = null

  if (filesRes.ok) {
    const filesData = (await filesRes.json()) as LibraryFilesResponse
    const currentId = parseInt(id, 10)
    const currentIndex = filesData.files.findIndex((file) => file.id === currentId)
    if (currentIndex > 0) previousFile = filesData.files[currentIndex - 1]
    if (currentIndex >= 0 && currentIndex < filesData.files.length - 1) nextFile = filesData.files[currentIndex + 1]
  }

  return {
    fileContent: fileData.content,
    fileTitle: fileData.file_info.title,
    previousFile,
    nextFile,
    category
  }
}

function LibraryFileViewer() {
  const t = useT()
  const navigate = useNavigate()
  const { fileContent, fileTitle, previousFile, nextFile, category, error } = useLoaderData() as LoaderData

  const translateCategory = (category: string): string => {
    const translationKey = `library.categories.${category}`
    const translated = t(translationKey)
    return translated === translationKey ? category : translated
  }

  return (
    <div className="app">
      <Navigation />
      <main className="main">
        {error && <ErrorDisplay error={t('library.errors.loadFailed')} />}
        <PageCard>
          <LibraryHeader
            title={fileTitle || translateCategory(category)}
            backPath={`/library/${encodeURIComponent(category)}`}
            backText={t('library.backToFiles')}
          />

          {!error && fileContent && (
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

          {!fileContent && error && (
            <Card style={{ margin: '1rem 0', backgroundColor: '#fee', borderColor: '#f00' }}>
              <p style={{ color: '#c00' }}>{t('library.errors.loadFailed')}</p>
            </Card>
          )}
        </PageCard>
      </main>
    </div>
  )
}

export default LibraryFileViewer

import { useLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import { useT } from './contexts/LanguageContext'
import Navigation from './components/Navigation'
import PageCard from './components/PageCard'
import LibraryHeader from './components/LibraryHeader'
import NavButton from './components/NavButton'
import { translate } from './i18n'
import { getLanguageFromUrl } from './utils/language'
import { useAppNavigate } from './hooks/useAppNavigate'
import type { LibraryFileResponse, LibraryFilesResponse, LibraryFileInfo } from './types/api'

interface LoaderData {
  fileContent: string
  fileTitle: string
  previousFile: LibraryFileInfo | null
  nextFile: LibraryFileInfo | null
  category: string
}

export async function libraryFileViewerLoader({ params, request }: LoaderFunctionArgs): Promise<LoaderData> {
  const { category, id } = params
  if (!category || !id) {
    throw new Response(translate(getLanguageFromUrl(request.url), 'library.errors.invalidCategory'), { status: 400 })
  }

  const language = getLanguageFromUrl(request.url)

  const [fileRes, filesRes] = await Promise.all([
    fetch(`/api/library/file/${encodeURIComponent(category)}/${encodeURIComponent(id)}?language=${language}`),
    fetch(`/api/library/files/${encodeURIComponent(category)}?language=${language}`)
  ])

  if (!fileRes.ok) {
    throw new Response(translate(language, 'library.errors.loadFailed'), { status: fileRes.status })
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
  const navigate = useAppNavigate()
  const { fileContent, fileTitle, previousFile, nextFile, category } = useLoaderData() as LoaderData

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
            title={fileTitle || translateCategory(category)}
            backPath={`/library/${encodeURIComponent(category)}`}
            backText={t('library.backToFiles')}
          />

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
        </PageCard>
      </main>
    </>
  )
}

export default LibraryFileViewer

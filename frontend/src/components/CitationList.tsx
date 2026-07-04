import { useT } from '../contexts/LanguageContext'
import type { LibraryFileInfo } from '../types/api'
import { formatCitationId } from '../utils/citations'
import { buildLibraryFilePath } from '../utils/library'
import styles from './CitationList.module.css'

interface CitationListProps {
  /** Cited works in order of first appearance. */
  fileIds: string[]
  loadingCitations: Set<string>
  getFileInfo: (fileId: string) => LibraryFileInfo | null
  /** Open the citation popup (fullscreen) for the given file's first chunk. */
  onOpenCitation: (e: React.MouseEvent<HTMLElement>, citationId: string) => void
}

/** Numbered list of cited works with a per-entry open-in-library link. */
function CitationList({ fileIds, loadingCitations, getFileInfo, onOpenCitation }: CitationListProps) {
  const t = useT()

  return (
    <>
      <h3 className={styles.title}>{t('citation.list.title')}</h3>
      <ul className={styles.list}>
        {fileIds.map((fileId, index) => {
          const fileInfo = getFileInfo(fileId)
          const isLoading = loadingCitations.has(formatCitationId(fileId, 0))

          return (
            <li key={fileId} className={styles.item}>
              <span className={styles.name} onClick={(e) => onOpenCitation(e, formatCitationId(fileId, 0))}>
                {isLoading ? t('citation.loading') : `${index + 1}. ${fileInfo?.title ?? fileId}`}
              </span>
              {fileInfo && (
                <a
                  href={buildLibraryFilePath(fileInfo)}
                  className={styles.libLink}
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    window.open(buildLibraryFilePath(fileInfo), '_blank', 'noopener,noreferrer')
                  }}
                  title={t('citation.openInLibrary')}
                  aria-label={t('citation.openInLibrary')}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                    <polyline points="15 3 21 3 21 9" />
                    <line x1="10" y1="14" x2="21" y2="3" />
                  </svg>
                </a>
              )}
            </li>
          )
        })}
      </ul>
    </>
  )
}

export default CitationList

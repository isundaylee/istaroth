import { ExternalLink } from 'lucide-react'
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
                  <ExternalLink size={14} aria-hidden />
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

import type { CitationResponse } from '../types/api'
import { useT } from '../contexts/LanguageContext'
import { formatCitationId } from '../utils/citations'
import { buildLibraryFilePath } from '../utils/library'
import styles from './CitationList.module.css'

interface CitationListProps {
  uniqueCitedWorks: string[]
  loadingCitations: Set<string>
  getCitedWorkInfo: (fileId: string) => CitationResponse | null
  onCitationListClick: (e: React.MouseEvent<HTMLElement>, citationId: string) => void
}

export function CitationList({
  uniqueCitedWorks,
  loadingCitations,
  getCitedWorkInfo,
  onCitationListClick
}: CitationListProps) {
  const t = useT()

  if (uniqueCitedWorks.length === 0) return null

  return (
    <div className={styles.container}>
      <h3 className={styles.heading}>{t('citation.list.title')}</h3>
      <ul className={styles.list}>
        {uniqueCitedWorks.map((fileId, index) => {
          const isLoading = loadingCitations.has(formatCitationId(fileId, 0))
          const fileInfo = getCitedWorkInfo(fileId)
          const title = fileInfo?.file_info.title ?? fileId

          const handleLibraryLinkClick = (e: React.MouseEvent<HTMLElement>) => {
            e.preventDefault()
            e.stopPropagation()
            if (fileInfo) {
              window.open(buildLibraryFilePath(fileInfo.file_info), '_blank', 'noopener,noreferrer')
            }
          }

          return (
            <li key={fileId} className={styles.item}>
              <span
                className={styles.title}
                onClick={(e) => onCitationListClick(e, formatCitationId(fileId, 0))}
              >
                {isLoading ? t('citation.loading') : `${index + 1}. ${title}`}
              </span>
              {fileInfo && (
                <a
                  className={styles.libLink}
                  href={buildLibraryFilePath(fileInfo.file_info)}
                  onClick={handleLibraryLinkClick}
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
    </div>
  )
}

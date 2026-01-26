import type { LibraryFileInfo } from '../types/api'

export function buildLibraryFilePath(fileInfo: LibraryFileInfo): string {
  return `/library/${encodeURIComponent(fileInfo.category)}/${encodeURIComponent(fileInfo.id)}`
}

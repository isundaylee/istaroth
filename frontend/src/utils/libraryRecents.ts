export interface LibraryRecent {
  category: string
  fileId: number
  title: string
}

const _KEY = 'istaroth_library_recents'
const _MAX = 8

export function getLibraryRecents(): LibraryRecent[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(_KEY) ?? '[]')
    return Array.isArray(parsed) ? (parsed as LibraryRecent[]) : []
  } catch {
    return []
  }
}

export function recordLibraryView(recent: LibraryRecent): void {
  try {
    const rest = getLibraryRecents().filter(
      (item) => !(item.category === recent.category && item.fileId === recent.fileId)
    )
    localStorage.setItem(_KEY, JSON.stringify([recent, ...rest].slice(0, _MAX)))
  } catch {
    /* ignore unavailable storage */
  }
}

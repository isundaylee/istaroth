import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'

const STORAGE_KEY = 'istaroth_history_rail_open'

interface HistoryRailContextValue {
  open: boolean
  toggle: () => void
}

const HistoryRailContext = createContext<HistoryRailContextValue | null>(null)

export function useHistoryRail() {
  const ctx = useContext(HistoryRailContext)
  if (!ctx) throw new Error('useHistoryRail must be used within HistoryRailProvider')
  return ctx
}

export function HistoryRailProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState<boolean>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true'
    } catch {
      return false
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(open))
    } catch { /* ignore unavailable storage */ }
  }, [open])

  const toggle = useCallback(() => setOpen((v) => !v), [])

  return (
    <HistoryRailContext.Provider value={{ open, toggle }}>
      {children}
    </HistoryRailContext.Provider>
  )
}

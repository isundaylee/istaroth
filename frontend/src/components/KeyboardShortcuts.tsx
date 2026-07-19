import { useEffect, useRef, useState } from 'react'
import { useAppNavigate } from '../hooks/useAppNavigate'
import { dispatchEscape, findShortcut, isEditable, shouldIgnoreShortcut } from '../utils/keyboard'
import KeyboardShortcutsModal from './KeyboardShortcutsModal'

const G_CHORD_TIMEOUT_MS = 1500

const G_CHORD_ROUTES: Record<string, string> = {
  q: '/',
  l: '/library'
}

/**
 * The app's single document-level keydown listener. Owns the global shortcuts
 * (`?` help, `/` focus search, `g` chords) and dispatches everything else
 * through the registry in `utils/keyboard`: Escape goes to the topmost
 * registered layer (popups, drawers, dropdowns — see `useKeyboardLayer`), and
 * unclaimed single keys fall through to layer shortcuts, then global
 * registrations (see `useGlobalShortcuts`), then the shortcuts here.
 */
function KeyboardShortcuts() {
  const navigate = useAppNavigate()
  const [helpOpen, setHelpOpen] = useState(false)
  const gPendingRef = useRef(false)
  const gTimerRef = useRef<number>()

  useEffect(() => {
    const clearGChord = () => {
      gPendingRef.current = false
      if (gTimerRef.current !== undefined) {
        window.clearTimeout(gTimerRef.current)
        gTimerRef.current = undefined
      }
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        clearGChord()
        if (dispatchEscape()) return
        if (helpOpen) {
          setHelpOpen(false)
          return
        }
        const active = document.activeElement
        if (active instanceof HTMLElement && isEditable(active)) {
          active.blur()
        }
        return
      }

      if (shouldIgnoreShortcut(e)) {
        return
      }

      if (gPendingRef.current) {
        const path = G_CHORD_ROUTES[e.key]
        if (path) {
          e.preventDefault()
          navigate(path)
        }
        clearGChord()
        return
      }

      const shortcut = findShortcut(e.key)
      if (shortcut) {
        e.preventDefault()
        shortcut()
        return
      }

      switch (e.key) {
        case '?':
          e.preventDefault()
          setHelpOpen((open) => !open)
          break
        case '/':
          e.preventDefault()
          // Each page opts exactly one input into the marker (e.g. the library
          // composer passes slashFocusTarget={false} so the sidebar search wins).
          document.querySelector<HTMLElement>('[data-text-input]')?.focus()
          break
        case 'g':
          gPendingRef.current = true
          gTimerRef.current = window.setTimeout(clearGChord, G_CHORD_TIMEOUT_MS)
          break
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      clearGChord()
    }
  }, [navigate, helpOpen])

  return <KeyboardShortcutsModal open={helpOpen} onClose={() => setHelpOpen(false)} />
}

export default KeyboardShortcuts

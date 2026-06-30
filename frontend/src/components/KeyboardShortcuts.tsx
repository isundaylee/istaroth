import { useEffect, useRef, useState } from 'react'
import { useAppNavigate } from '../hooks/useAppNavigate'
import KeyboardShortcutsModal from './KeyboardShortcutsModal'

const G_CHORD_TIMEOUT_MS = 1500

const G_CHORD_ROUTES: Record<string, string> = {
  q: '/',
  r: '/retrieve',
  l: '/library'
}

function isEditable(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false
  }
  return (
    target.tagName === 'INPUT' ||
    target.tagName === 'TEXTAREA' ||
    target.tagName === 'SELECT' ||
    target.isContentEditable
  )
}

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
        const active = document.activeElement
        if (helpOpen) {
          setHelpOpen(false)
        } else if (active instanceof HTMLElement && isEditable(active)) {
          active.blur()
        }
        clearGChord()
        return
      }

      if (isEditable(e.target) || e.metaKey || e.ctrlKey || e.altKey) {
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

      switch (e.key) {
        case '?':
          e.preventDefault()
          setHelpOpen((open) => !open)
          break
        case '/':
          e.preventDefault()
          document.querySelector<HTMLInputElement>('input[data-text-input]')?.focus()
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

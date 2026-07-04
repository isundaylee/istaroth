import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from '../contexts/LanguageContext'
import type { ProperNounsResponse } from '../types/api'

interface LibraryProperNounsArgs {
  category: string
  fileId: string
}

export function useLibraryProperNouns({ category, fileId }: LibraryProperNounsArgs): string[] {
  const { language } = useTranslation()
  const [staticNouns, setStaticNouns] = useState<string[]>([])
  const [llmNouns, setLlmNouns] = useState<string[] | null>(null)
  const [fallbackElapsed, setFallbackElapsed] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetch(`/api/library/proper-nouns?language=${encodeURIComponent(language.toUpperCase())}`)
      .then((res) => (res.ok ? (res.json() as Promise<ProperNounsResponse>) : null))
      .then((data) => {
        if (!cancelled) setStaticNouns(data?.nouns ?? [])
      })
      .catch(() => {
        if (!cancelled) setStaticNouns([])
      })
    return () => {
      cancelled = true
    }
  }, [language])

  useEffect(() => {
    let cancelled = false
    setLlmNouns(null)
    setFallbackElapsed(false)
    const timer = window.setTimeout(() => {
      if (!cancelled) setFallbackElapsed(true)
    }, 2000)
    fetch(
      `/api/library/file/${encodeURIComponent(category)}/${encodeURIComponent(fileId)}/proper-nouns?language=${encodeURIComponent(language.toUpperCase())}`
    )
      .then((res) => (res.ok ? (res.json() as Promise<ProperNounsResponse>) : null))
      .then((data) => {
        if (!cancelled && data) setLlmNouns(data.nouns)
      })
      .catch(() => {})
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [language, category, fileId])

  return useMemo(() => llmNouns !== null ? llmNouns : fallbackElapsed ? staticNouns : [], [llmNouns, fallbackElapsed, staticNouns])
}

import { useEffect, useState } from 'react'
import { useTranslation } from '../contexts/LanguageContext'
import type { ProperNounsResponse } from '../types/api'

/**
 * Static curated list (per language, fast) and per-file LLM extraction.
 * Shows nothing for the first 2s, then falls back to the static list;
 * the LLM result replaces it whenever it arrives. On failure the static
 * list stays in effect.
 */
export function useLibraryProperNouns(category: string, fileId: string): string[] {
  const { language } = useTranslation()
  const [staticNouns, setStaticNouns] = useState<string[]>([])
  const [llmNouns, setLlmNouns] = useState<string[] | null>(null)
  const [fallbackElapsed, setFallbackElapsed] = useState(false)

  // Static curated list: fetched once per language, reused across files.
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

  // Per-file LLM extraction: show nothing for 2s, then fall back to the static
  // list; replace with the LLM result whenever it arrives. On failure we leave
  // llmNouns null so the static fallback stays.
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

  if (llmNouns !== null) return llmNouns
  if (fallbackElapsed) return staticNouns
  return []
}

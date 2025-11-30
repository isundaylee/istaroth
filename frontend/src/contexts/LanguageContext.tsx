import { createContext, useContext, useCallback, ReactNode, useMemo } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { translations, Language, TranslationKey } from '../i18n'
import { getLanguageFromUrl, buildUrlWithLanguage } from '../utils/language'

interface LanguageContextType {
  language: Language
  setLanguage: (lang: Language) => void
  t: TranslationKey
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined)

interface LanguageProviderProps {
  children: ReactNode
}

export function LanguageProvider({ children }: LanguageProviderProps) {
  const location = useLocation()
  const navigate = useNavigate()

  const language = useMemo(() => {
    const url = `${window.location.origin}${location.pathname}${location.search}`
    return getLanguageFromUrl(url)
  }, [location.pathname, location.search])

  const setLanguage = useCallback((lang: Language) => {
    const newUrl = buildUrlWithLanguage(location.pathname, location.search, lang)
    navigate(newUrl, { replace: true })
  }, [location.pathname, location.search, navigate])

  const contextValue: LanguageContextType = useMemo(() => ({
    language,
    setLanguage,
    t: translations[language]
  }), [language, setLanguage])

  return (
    <LanguageContext.Provider value={contextValue}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useTranslation() {
  const context = useContext(LanguageContext)
  if (context === undefined) {
    throw new Error('useTranslation must be used within a LanguageProvider')
  }
  return context
}

// Helper hook for getting nested translation values
export function useT() {
  const { t } = useTranslation()

  return useCallback(function translate(path: string): string {
    const keys = path.split('.')
    let result: any = t

    for (const key of keys) {
      if (result && typeof result === 'object' && key in result) {
        result = result[key]
      } else {
        console.warn(`Translation key not found: ${path}`)
        return path // Return the path as fallback
      }
    }

    return typeof result === 'string' ? result : path
  }, [t])
}

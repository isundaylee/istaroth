import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react'
import { translations, Language, TranslationKey } from '../i18n'

interface LanguageContextType {
  language: Language
  setLanguage: (lang: Language) => void
  t: TranslationKey
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined)

const LANGUAGE_STORAGE_KEY = 'istaroth-language'

const getInitialLanguage = (): Language => {
  // Try to get from localStorage first
  const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY)
  if (stored && (stored === 'chs' || stored === 'eng')) {
    return stored as Language
  }

  // Fallback to browser language
  const browserLang = navigator.language.toLowerCase()
  if (browserLang.startsWith('zh')) {
    return 'chs'
  }

  // Default to Chinese
  return 'chs'
}

interface LanguageProviderProps {
  children: ReactNode
}

export function LanguageProvider({ children }: LanguageProviderProps) {
  const [language, setLanguage] = useState<Language>(getInitialLanguage)

  useEffect(() => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, language)
  }, [language])

  const contextValue: LanguageContextType = {
    language,
    setLanguage,
    t: translations[language]
  }

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

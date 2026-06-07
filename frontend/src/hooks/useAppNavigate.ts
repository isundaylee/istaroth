import { useCallback } from 'react'
import { useNavigate, type NavigateOptions } from 'react-router-dom'
import { useTranslation } from '../contexts/LanguageContext'
import { buildUrlWithLanguage } from '../utils/language'

export function useAppNavigate() {
  const navigate = useNavigate()
  const { language } = useTranslation()

  return useCallback(
    (to: string, options?: NavigateOptions) => {
      const [pathname, search = ''] = to.split('?')
      navigate(buildUrlWithLanguage(pathname, search, language), options)
    },
    [navigate, language]
  )
}

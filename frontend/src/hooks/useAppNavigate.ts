import { useCallback } from 'react'
import { useNavigate, useLocation, type NavigateOptions } from 'react-router-dom'
import { useTranslation } from '../contexts/LanguageContext'
import { buildUrlWithLanguage } from '../utils/language'

export function useAppNavigate() {
  const navigate = useNavigate()
  const { language } = useTranslation()
  const location = useLocation()

  return useCallback(
    (to: string, options?: NavigateOptions) => {
      const url = buildUrlWithLanguage(to, location.search, language)
      navigate(url, options)
    },
    [navigate, language, location.search]
  )
}

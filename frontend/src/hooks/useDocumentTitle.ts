import { useEffect } from 'react'
import { useT } from '../contexts/LanguageContext'

export function useDocumentTitle(titleKey: string = 'meta.title') {
  const t = useT()

  useEffect(() => {
    const title = t(titleKey)
    document.title = title
  }, [t, titleKey])
}

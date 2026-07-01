import { useLocation, useNavigate } from 'react-router-dom'
import type { Language } from '../i18n'
import { getLanguageFromUrl, buildUrlWithLanguage } from '../utils/language'
import Toggle from './Toggle'

function LanguageSwitcher() {
  const location = useLocation()
  const navigate = useNavigate()
  const language = getLanguageFromUrl(`${window.location.origin}${location.pathname}${location.search}`)

  const handleLanguageChange = (lang: Language) => {
    const newUrl = buildUrlWithLanguage(location.pathname, location.search, lang)
    navigate(newUrl, { replace: true })
  }

  return (
    <Toggle
      options={[
        { value: 'chs', label: '中文' },
        { value: 'eng', label: 'English' }
      ]}
      value={language}
      onChange={handleLanguageChange}
    />
  )
}

export default LanguageSwitcher

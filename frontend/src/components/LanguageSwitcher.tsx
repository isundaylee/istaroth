import { useLocation, useNavigate } from 'react-router-dom'
import type { Language } from '../i18n'
import { getLanguageFromUrl, buildUrlWithLanguage } from '../utils/language'
import Button from './Button'
import styles from './LanguageSwitcher.module.css'

const LANGUAGES: Array<{ lang: Language; label: string }> = [
  { lang: 'chs', label: '中文' },
  { lang: 'eng', label: 'English' },
]

function LanguageSwitcher() {
  const location = useLocation()
  const navigate = useNavigate()
  const language = getLanguageFromUrl(`${window.location.origin}${location.pathname}${location.search}`)

  const handleLanguageChange = (lang: Language) => {
    const newUrl = buildUrlWithLanguage(location.pathname, location.search, lang)
    navigate(newUrl, { replace: true })
  }

  return (
    <div className={styles.switcher}>
      {LANGUAGES.map(({ lang, label }) => (
        <Button
          key={lang}
          variant="ghost"
          onClick={() => handleLanguageChange(lang)}
          className={`${styles.languageButton} ${language === lang ? styles.active : ''}`}
        >
          {label}
        </Button>
      ))}
    </div>
  )
}

export default LanguageSwitcher

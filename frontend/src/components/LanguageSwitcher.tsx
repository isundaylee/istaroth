import { useLocation, useNavigate } from 'react-router-dom'
import type { Language } from '../i18n'
import { getLanguageFromUrl, buildUrlWithLanguage } from '../utils/language'

interface LanguageButtonProps {
  label: string
  isActive: boolean
  onClick: () => void
}

function LanguageButton({ label, isActive, onClick }: LanguageButtonProps) {
  return (
    <button
      onClick={onClick}
      style={{
        background: isActive ? '#007bff' : 'transparent',
        color: isActive ? 'white' : '#666',
        border: '1px solid #ddd',
        borderRadius: 'var(--radius-md)',
        padding: '0.25rem 0.5rem',
        cursor: 'pointer',
        fontSize: '0.8rem',
        fontWeight: isActive ? 'bold' : 'normal',
        transition: 'all 0.2s'
      }}
      onMouseOver={(e) => {
        if (!isActive) {
          e.currentTarget.style.backgroundColor = '#f8f9fa'
        }
      }}
      onMouseOut={(e) => {
        if (!isActive) {
          e.currentTarget.style.backgroundColor = 'transparent'
        }
      }}
    >
      {label}
    </button>
  )
}

function LanguageSwitcher() {
  const location = useLocation()
  const navigate = useNavigate()
  const language = getLanguageFromUrl(`${window.location.origin}${location.pathname}${location.search}`)

  const handleLanguageChange = (lang: Language) => {
    const newUrl = buildUrlWithLanguage(location.pathname, location.search, lang)
    navigate(newUrl, { replace: true })
  }

  const languages: Array<{ lang: Language; label: string }> = [
    { lang: 'chs', label: '中文' },
    { lang: 'eng', label: 'English' }
  ]

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '0.5rem',
      fontSize: '0.9rem'
    }}>
      {languages.map(({ lang, label }) => (
        <LanguageButton
          key={lang}
          label={label}
          isActive={language === lang}
          onClick={() => handleLanguageChange(lang)}
        />
      ))}
    </div>
  )
}

export default LanguageSwitcher

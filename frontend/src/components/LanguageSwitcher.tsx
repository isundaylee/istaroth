import { useLocation, useNavigate } from 'react-router-dom'
import type { Language } from '../i18n'
import { getLanguageFromUrl, buildUrlWithLanguage } from '../utils/language'
import Button from './Button'

interface LanguageButtonProps {
  label: string
  isActive: boolean
  onClick: () => void
}

function LanguageButton({ label, isActive, onClick }: LanguageButtonProps) {
  return (
    <Button
      onClick={onClick}
      variant="ghost"
      style={{
        padding: '0.25rem 0.5rem',
        fontSize: 'var(--font-sm)',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--color-border)',
        fontWeight: isActive ? 600 : 'normal',
        background: isActive ? 'var(--color-primary-fill)' : 'transparent',
        color: isActive ? 'white' : 'var(--color-text-secondary)',
      }}
    >
      {label}
    </Button>
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
      fontSize: 'var(--font-sm)'
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

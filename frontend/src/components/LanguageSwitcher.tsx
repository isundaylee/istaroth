import { useTranslation } from '../contexts/LanguageContext'
import Button from './Button'

interface LanguageSwitcherProps {
  className?: string
}

// Single compact button labeled with the language it switches TO.
function LanguageSwitcher({ className }: LanguageSwitcherProps) {
  const { language, setLanguage, t } = useTranslation()

  return (
    <Button
      onClick={() => setLanguage(language === 'chs' ? 'eng' : 'chs')}
      variant="ghost"
      size="sm"
      className={className}
      title={t.language.toggle}
    >
      {language === 'chs' ? 'EN' : '中'}
    </Button>
  )
}

export default LanguageSwitcher

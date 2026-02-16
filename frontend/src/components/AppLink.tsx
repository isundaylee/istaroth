import { Link, type LinkProps } from 'react-router-dom'
import { useTranslation } from '../contexts/LanguageContext'
import { buildUrlWithLanguage } from '../utils/language'

export function AppLink({ to, ...props }: LinkProps) {
  const { language } = useTranslation()
  const href = typeof to === 'string' ? buildUrlWithLanguage(to, '', language) : to
  return <Link to={href} {...props} />
}

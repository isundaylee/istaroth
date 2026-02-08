import { Link, useLocation, type LinkProps } from 'react-router-dom'
import { useTranslation } from '../contexts/LanguageContext'
import { buildUrlWithLanguage } from '../utils/language'

export function AppLink({ to, ...props }: LinkProps) {
  const { language } = useTranslation()
  const location = useLocation()
  const href = typeof to === 'string' ? buildUrlWithLanguage(to, location.search, language) : to
  return <Link to={href} {...props} />
}

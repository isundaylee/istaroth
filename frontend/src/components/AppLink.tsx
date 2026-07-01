import { Link, type LinkProps } from 'react-router-dom'
import { useTranslation } from '../contexts/LanguageContext'
import { buildUrlWithLanguage } from '../utils/language'
import styles from './AppLink.module.css'

interface AppLinkProps extends LinkProps {
  // "plain": plain text link (color-accent hover) for pure navigation, e.g.
  // breadcrumbs and TOC entries. Omitted (default): no styling of its own —
  // most call sites (nav tabs, card-wrapper links, result lists, ...) style
  // their <AppLink> entirely themselves.
  variant?: 'plain'
}

export function AppLink({ to, variant, className, ...props }: AppLinkProps) {
  const { language } = useTranslation()
  const href = typeof to === 'string' ? buildUrlWithLanguage(to, '', language) : to
  return <Link to={href} className={[variant && styles[variant], className].filter(Boolean).join(' ')} {...props} />
}

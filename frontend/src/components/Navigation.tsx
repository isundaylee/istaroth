import { ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import clsx from 'clsx'
import { useT } from '../contexts/LanguageContext'
import { useRailPlacementGuide } from '../contexts/PopupCoordinatorContext'
import { useTheme } from '../contexts/ThemeContext'
import { AppLink } from './AppLink'
import Button from './Button'
import LanguageSwitcher from './LanguageSwitcher'
import styles from './Navigation.module.css'

interface NavigationProps {
  // When embedded inside a connected panel, drop the standalone card chrome
  // (border/radius/margin/shadow) and sit as the panel's top section, divided
  // from the rest by a single bottom hairline.
  embedded?: boolean
  // Optional leading control (PageShell's mobile drawer toggle) rendered before
  // the nav links. When present, the nav sticks to the viewport top on mobile
  // so the toggle stays reachable while scrolling.
  leading?: ReactNode
}

function Navigation({ embedded = false, leading }: NavigationProps = {}) {
  const t = useT()
  const location = useLocation()
  const { theme, toggleTheme } = useTheme()
  // While stuck to the viewport top (the mobile navSticky variant), the nav is
  // chrome the minimized-card rail must stick below. Registration is
  // unconditional; a non-sticky nav contributes nothing (see useRailPlacementGuide).
  const railGuideRef = useRailPlacementGuide()

  const isActive = (path: string) => location.pathname === path

  const navLinks = [
    { path: '/', key: 'home' },
    { path: '/library', key: 'library' }
  ]

  return (
    <nav ref={railGuideRef} className={clsx(styles.nav, embedded && styles.navEmbedded, leading != null && styles.navSticky)}>
      <div className={styles.links}>
        {leading != null && (
          <>
            {leading}
            <span className={styles.leadingDivider} aria-hidden />
          </>
        )}
        {navLinks.map(({ path, key }) => (
          <AppLink
            key={path}
            to={path}
            className={clsx(styles.link, isActive(path) && styles.linkActive)}
          >
            {t(`navigation.${key}`)}
          </AppLink>
        ))}
      </div>
      <div className={styles.controls}>
        <Button
          onClick={toggleTheme}
          variant="ghost"
          size="sm"
          className={styles.controlButton}
          title={theme === 'light' ? t('theme.toggleDark') : t('theme.toggleLight')}
        >
          {theme === 'light' ? '☾' : '☀'}
        </Button>
        <LanguageSwitcher className={styles.controlButton} />
      </div>
    </nav>
  )
}

export default Navigation

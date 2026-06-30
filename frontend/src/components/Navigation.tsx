import { useLocation } from 'react-router-dom'
import clsx from 'clsx'
import { useT } from '../contexts/LanguageContext'
import { useTheme } from '../contexts/ThemeContext'
import { AppLink } from './AppLink'
import LanguageSwitcher from './LanguageSwitcher'
import styles from './Navigation.module.css'

function Navigation() {
  const t = useT()
  const location = useLocation()
  const { theme, toggleTheme } = useTheme()

  const isActive = (path: string) => location.pathname === path

  const navLinks = [
    { path: '/', key: 'home' },
    { path: '/retrieve', key: 'retrieve' },
    { path: '/library', key: 'library' },
    { path: '/history', key: 'history' }
  ]

  return (
    <nav className={styles.nav}>
      <div className={styles.links}>
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
        <button
          onClick={toggleTheme}
          title={theme === 'light' ? t('theme.toggleDark') : t('theme.toggleLight')}
          className={styles.themeButton}
        >
          {theme === 'light' ? '☾' : '☀'}
        </button>
        <LanguageSwitcher />
      </div>
    </nav>
  )
}

export default Navigation

import { useLocation } from 'react-router-dom'
import { useT } from '../contexts/LanguageContext'
import { useTheme } from '../contexts/ThemeContext'
import { AppLink } from './AppLink'
import LanguageSwitcher from './LanguageSwitcher'

function Navigation() {
  const t = useT()
  const location = useLocation()
  const { theme, toggleTheme } = useTheme()

  const isActive = (path: string) => location.pathname === path

  const navLinks = [
    { path: '/', key: 'home' },
    { path: '/retrieve', key: 'retrieve' },
    { path: '/library', key: 'library' }
  ]

  return (
    <nav
      style={{
        backgroundColor: 'var(--color-surface)',
        borderRadius: 'var(--radius-md)',
        padding: '0.5rem 1rem',
        marginBottom: '1.25rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        boxShadow: 'var(--shadow)',
        flexWrap: 'wrap',
        gap: '0.75rem'
      }}
    >
      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
        {navLinks.map(({ path, key }) => {
          const active = isActive(path)
          return (
            <AppLink
              key={path}
              to={path}
              style={{
                textDecoration: 'none',
                color: active ? 'var(--color-primary-link)' : 'var(--color-text-secondary)',
                backgroundColor: active ? 'var(--color-primary-active-bg)' : 'transparent',
                border: 'none',
                borderRadius: 'var(--radius-md)',
                padding: '0.3rem 1rem',
                fontSize: 'var(--font-base)',
                fontWeight: active ? '600' : 'normal',
                transition: 'all 0.2s',
                cursor: 'pointer',
                whiteSpace: 'nowrap'
              }}
              onMouseEnter={(e) => {
                if (!active) {
                  e.currentTarget.style.backgroundColor = 'var(--color-surface-hover)'
                  e.currentTarget.style.color = 'var(--color-primary-link)'
                }
              }}
              onMouseLeave={(e) => {
                if (!active) {
                  e.currentTarget.style.backgroundColor = 'transparent'
                  e.currentTarget.style.color = 'var(--color-text-secondary)'
                }
              }}
            >
              {t(`navigation.${key}`)}
            </AppLink>
          )
        })}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <button
          onClick={toggleTheme}
          title={theme === 'light' ? t('theme.toggleDark') : t('theme.toggleLight')}
          style={{
            background: 'transparent',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            padding: '0.25rem 0.5rem',
            cursor: 'pointer',
            fontSize: 'var(--font-sm)',
            color: 'var(--color-text-secondary)',
            transition: 'all 0.2s',
            lineHeight: 1
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--color-surface-hover)'
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent'
          }}
        >
          {theme === 'light' ? '☾' : '☀'}
        </button>
        <LanguageSwitcher />
      </div>
    </nav>
  )
}

export default Navigation

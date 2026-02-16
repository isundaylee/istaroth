import { useLocation } from 'react-router-dom'
import { useT } from '../contexts/LanguageContext'
import { AppLink } from './AppLink'
import LanguageSwitcher from './LanguageSwitcher'

function Navigation() {
  const t = useT()
  const location = useLocation()

  const isActive = (path: string) => location.pathname === path

  const navLinks = [
    { path: '/', key: 'home' },
    { path: '/retrieve', key: 'retrieve' },
    { path: '/library', key: 'library' }
  ]

  return (
    <nav
      style={{
        backgroundColor: '#fff',
        borderRadius: 'var(--radius-md)',
        padding: '0.75rem 1.5rem',
        marginBottom: '1.5rem',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
        flexWrap: 'wrap',
        gap: '0.75rem'
      }}
    >
      <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
        {navLinks.map(({ path, key }) => {
          const active = isActive(path)
          return (
            <AppLink
              key={path}
              to={path}
              style={{
                textDecoration: 'none',
                color: active ? '#007bff' : '#666',
                backgroundColor: active ? '#e7f3ff' : 'transparent',
                border: 'none',
                borderRadius: 'var(--radius-md)',
                padding: '0.5rem 1.75rem',
                fontSize: '1rem',
                fontWeight: active ? '600' : 'normal',
                transition: 'all 0.2s',
                cursor: 'pointer',
                whiteSpace: 'nowrap'
              }}
              onMouseEnter={(e) => {
                if (!active) {
                  e.currentTarget.style.backgroundColor = '#f8f9fa'
                  e.currentTarget.style.color = '#007bff'
                }
              }}
              onMouseLeave={(e) => {
                if (!active) {
                  e.currentTarget.style.backgroundColor = 'transparent'
                  e.currentTarget.style.color = '#666'
                }
              }}
            >
              {t(`navigation.${key}`)}
            </AppLink>
          )
        })}
      </div>
      <LanguageSwitcher />
    </nav>
  )
}

export default Navigation

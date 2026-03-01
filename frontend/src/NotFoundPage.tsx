import { useT } from './contexts/LanguageContext'
import Card from './components/Card'
import LanguageSwitcher from './components/LanguageSwitcher'
import PageTitle from './components/PageTitle'
import { AppLink } from './components/AppLink'

function NotFoundPage() {
  const t = useT()

  return (
    <>
      <main className="main">
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          padding: '0.5rem 0 1rem 0'
        }}>
          <LanguageSwitcher />
        </div>
        <Card>
          <div style={{ textAlign: 'center', padding: '2rem 0' }}>
            <h1 style={{ fontSize: 'var(--font-hero)', margin: '0', color: 'var(--color-text-secondary)' }}>{t('notFound.title')}</h1>
            <PageTitle as="h2">
              {t('notFound.heading')}
            </PageTitle>
            <p style={{ margin: '1rem 0', color: 'var(--color-text-secondary)' }}>
              {t('notFound.message')}
            </p>
            <AppLink
              to="/"
              className="back-link"
              style={{
                display: 'inline-block',
                marginTop: '1rem',
                padding: '0.5rem 1rem',
                backgroundColor: 'var(--color-primary-link)',
                color: 'white',
                textDecoration: 'none',
                borderRadius: 'var(--radius-md)',
                transition: 'background-color 0.2s'
              }}
              onMouseOver={(e) => e.currentTarget.style.backgroundColor = 'var(--color-primary-link-hover)'}
              onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'var(--color-primary-link)'}
            >
              {t('notFound.backButton')}
            </AppLink>
          </div>
        </Card>
      </main>
    </>
  )
}

export default NotFoundPage

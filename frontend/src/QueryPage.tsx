import { useT } from './contexts/LanguageContext'
import QueryForm from './QueryForm'
import Navigation from './components/Navigation'
import PageCard from './components/PageCard'
import PageTitle from './components/PageTitle'

function QueryPage() {
  const t = useT()

  return (
    <>
      <Navigation />
      <main className="main">

        <QueryForm />

        <div style={{
          textAlign: 'center',
        }}>
          <PageCard>
            <PageTitle>
              {t('query.title')}
            </PageTitle>
            <p style={{
              fontSize: 'var(--font-base)',
              color: '#5a6c7d',
              lineHeight: '1.6',
              maxWidth: '600px',
              margin: '0 auto 25px auto'
            }}>
              {t('meta.description')}
            </p>
            <img
              src="/istaroth-logo.png"
              alt="Istaroth Logo"
              style={{ width: '300px', height: '300px', margin: '0 auto 20px auto', display: 'block' }}
            />
            <div style={{ marginTop: '20px' }}>
              <a
                href="https://github.com/isundaylee/istaroth"
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: 'var(--font-sm)',
                  color: '#0366d6',
                  textDecoration: 'none',
                  padding: '6px 12px',
                  border: '1px solid #d1d9e0',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: '#f6f8fa',
                  transition: 'all 0.2s ease'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#e1e4e8'
                  e.currentTarget.style.borderColor = '#c1c8cd'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#f6f8fa'
                  e.currentTarget.style.borderColor = '#d1d9e0'
                }}
              >
                <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
                </svg>
                {t('meta.githubLink')}
              </a>
            </div>
          </PageCard>
        </div>
      </main>
    </>
  )
}

export default QueryPage

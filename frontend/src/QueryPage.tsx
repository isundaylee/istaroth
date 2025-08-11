import { useT } from './contexts/LanguageContext'
import QueryForm from './QueryForm'
import Card from './components/Card'
import LanguageSwitcher from './components/LanguageSwitcher'

function QueryPage() {
  const t = useT()

  return (
    <div className="app">
      <main className="main">
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          padding: '0.5rem 0 1rem 0'
        }}>
          <LanguageSwitcher />
        </div>

        <QueryForm />

        <div style={{
          textAlign: 'center',
          marginBottom: '40px'
        }}>
          <Card style={{
            backgroundColor: 'white',
            borderRadius: '12px',
            boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
            padding: '30px',
            margin: '0'
          }}>
            <h1 style={{ fontSize: '2.5rem', color: '#2c3e50', marginBottom: '15px' }}>
              {t('query.title')}
            </h1>
            <p style={{
              fontSize: '1.1rem',
              color: '#5a6c7d',
              lineHeight: '1.6',
              marginBottom: '25px',
              maxWidth: '600px',
              margin: '0 auto 25px auto'
            }}>
              {t('query.description')}
            </p>
            <img
              src="/istaroth-logo.png"
              alt="Istaroth Logo"
              style={{ width: '300px', height: '300px', borderRadius: '12px', margin: '0 auto', display: 'block' }}
            />
          </Card>
        </div>
      </main>
    </div>
  )
}

export default QueryPage

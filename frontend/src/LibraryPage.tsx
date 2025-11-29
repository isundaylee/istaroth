import { useT } from './contexts/LanguageContext'
import Navigation from './components/Navigation'

function LibraryPage() {
  const t = useT()

  return (
    <div className="app">
      <Navigation />
      <main className="main">
        <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
          <h1 style={{ marginBottom: '2rem', textAlign: 'center' }}>
            {t('library.title')}
          </h1>
          <p style={{ textAlign: 'center', color: '#666' }}>
            {t('library.placeholder')}
          </p>
        </div>
      </main>
    </div>
  )
}

export default LibraryPage

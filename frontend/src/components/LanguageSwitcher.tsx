import { useTranslation } from '../contexts/LanguageContext'

function LanguageSwitcher() {
  const { language, setLanguage } = useTranslation()

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '0.5rem',
      fontSize: '0.9rem'
    }}>
      <button
        onClick={() => setLanguage('chs')}
        style={{
          background: language === 'chs' ? '#007bff' : 'transparent',
          color: language === 'chs' ? 'white' : '#666',
          border: '1px solid #ddd',
          borderRadius: '4px',
          padding: '0.25rem 0.5rem',
          cursor: 'pointer',
          fontSize: '0.8rem',
          fontWeight: language === 'chs' ? 'bold' : 'normal',
          transition: 'all 0.2s'
        }}
        onMouseOver={(e) => {
          if (language !== 'chs') {
            e.currentTarget.style.backgroundColor = '#f8f9fa'
          }
        }}
        onMouseOut={(e) => {
          if (language !== 'chs') {
            e.currentTarget.style.backgroundColor = 'transparent'
          }
        }}
      >
        中文
      </button>
      <button
        onClick={() => setLanguage('eng')}
        style={{
          background: language === 'eng' ? '#007bff' : 'transparent',
          color: language === 'eng' ? 'white' : '#666',
          border: '1px solid #ddd',
          borderRadius: '4px',
          padding: '0.25rem 0.5rem',
          cursor: 'pointer',
          fontSize: '0.8rem',
          fontWeight: language === 'eng' ? 'bold' : 'normal',
          transition: 'all 0.2s'
        }}
        onMouseOver={(e) => {
          if (language !== 'eng') {
            e.currentTarget.style.backgroundColor = '#f8f9fa'
          }
        }}
        onMouseOut={(e) => {
          if (language !== 'eng') {
            e.currentTarget.style.backgroundColor = 'transparent'
          }
        }}
      >
        English
      </button>
    </div>
  )
}

export default LanguageSwitcher

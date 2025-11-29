import { useNavigate } from 'react-router-dom'

interface LibraryHeaderProps {
  title: string
  backPath: string
  backText: string
}

function LibraryHeader({ title, backPath, backText }: LibraryHeaderProps) {
  const navigate = useNavigate()

  return (
    <div className="library-header" style={{ marginBottom: '2rem', display: 'flex', justifyContent: 'center', alignItems: 'center', position: 'relative' }}>
      <h1 style={{ margin: 0, fontSize: '2.5rem', color: '#2c3e50', textAlign: 'center' }}>
        {title}
      </h1>
      <button
        onClick={() => navigate(backPath)}
        style={{
          padding: '0.5rem 1rem',
          border: '1px solid #ddd',
          borderRadius: '4px',
          backgroundColor: 'white',
          cursor: 'pointer',
          position: 'absolute',
          right: 0
        }}
      >
        ← {backText}
      </button>
    </div>
  )
}

export default LibraryHeader

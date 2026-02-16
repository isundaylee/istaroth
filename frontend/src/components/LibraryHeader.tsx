import { useState } from 'react'
import { useAppNavigate } from '../hooks/useAppNavigate'
import PageTitle from './PageTitle'

interface LibraryHeaderProps {
  title: string
  backPath: string
  backText: string
}

function LibraryHeader({ title, backPath, backText }: LibraryHeaderProps) {
  const navigate = useAppNavigate()
  const [isHovered, setIsHovered] = useState(false)

  const baseStyle: React.CSSProperties = {
    padding: '0.5rem 1rem',
    border: '1px solid #ddd',
    borderRadius: 'var(--radius-md)',
    backgroundColor: 'white',
    cursor: 'pointer',
    transition: 'all 0.2s ease',
    whiteSpace: 'nowrap',
    fontSize: '0.9rem',
    minWidth: 'fit-content'
  }

  const hoverStyle: React.CSSProperties = {
    backgroundColor: '#fafafa',
    borderColor: '#ccc'
  }

  const backButton = (
    <button
      onClick={() => navigate(backPath)}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{ ...baseStyle, ...(isHovered ? hoverStyle : {}) }}
    >
      ← {backText}
    </button>
  )

  return (
    <div className="library-header">
      <PageTitle rightElement={backButton}>
        {title}
      </PageTitle>
    </div>
  )
}

export default LibraryHeader

import { useState } from 'react'
import { useAppNavigate } from '../hooks/useAppNavigate'

interface LibraryHeaderProps {
  title: string
  backPath: string
  backText: string
}

function LibraryHeader({ title, backPath, backText }: LibraryHeaderProps) {
  const navigate = useAppNavigate()
  const [isHovered, setIsHovered] = useState(false)

  return (
    <div className="library-header">
      <span className="library-header__spacer" aria-hidden="true" />
      <h1 className="library-header__title">{title}</h1>
      <div className="library-header__actions">
        <button
          onClick={() => navigate(backPath)}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          style={{
            padding: '0.5rem 1rem',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-md)',
            backgroundColor: isHovered ? 'var(--color-surface-hover)' : 'var(--color-surface)',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            whiteSpace: 'nowrap',
            fontSize: 'var(--font-sm)'
          }}
        >
          ← {backText}
        </button>
      </div>
    </div>
  )
}

export default LibraryHeader

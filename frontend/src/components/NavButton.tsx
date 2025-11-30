import { useState } from 'react'

interface NavButtonProps {
  onClick: () => void
  label: string
  title: string
  marginTop: string
}

function NavButton({ onClick, label, title, marginTop }: NavButtonProps) {
  const [isHovered, setIsHovered] = useState(false)

  const baseStyle: React.CSSProperties = {
    padding: '0.75rem 1rem',
    border: '1px solid #ddd',
    borderRadius: '4px',
    backgroundColor: 'white',
    cursor: 'pointer',
    width: '100%',
    textAlign: 'left',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    transition: 'all 0.2s ease'
  }

  const hoverStyle: React.CSSProperties = {
    backgroundColor: '#fafafa',
    borderColor: '#ccc'
  }

  const labelStyle: React.CSSProperties = {
    fontSize: '0.875rem',
    color: '#666',
    marginBottom: '0.25rem'
  }

  const titleStyle: React.CSSProperties = {
    fontWeight: '500'
  }

  return (
    <div style={{ marginTop }}>
      <button
        onClick={onClick}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        style={{ ...baseStyle, ...(isHovered ? hoverStyle : {}) }}
      >
        <span style={{ flex: 1 }}>
          <div style={labelStyle}>{label}</div>
          <div style={titleStyle}>{title}</div>
        </span>
      </button>
    </div>
  )
}

export default NavButton

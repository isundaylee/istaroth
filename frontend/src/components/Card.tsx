import { ReactNode, CSSProperties } from 'react'

interface CardProps {
  children: ReactNode
  style?: CSSProperties
  borderColor?: 'green' | 'blue' | 'none'
}

function Card({
  children,
  style = {},
  borderColor = 'none'
}: CardProps) {
  const baseStyles: CSSProperties = {
    backgroundColor: '#f8f9fa',
    borderRadius: 'var(--radius-md)',
    boxShadow: 'var(--shadow)',
    padding: '0.75rem 1rem',
    margin: '1rem 0',
  }

  const borderStyles: CSSProperties = borderColor !== 'none' ? {
    borderLeft: `4px solid ${borderColor === 'green' ? '#28a745' : '#3498db'}`
  } : {}

  const combinedStyles = {
    ...baseStyles,
    ...borderStyles,
    ...style
  }

  return (
    <div className="card" style={combinedStyles}>
      {children}
    </div>
  )
}

export default Card

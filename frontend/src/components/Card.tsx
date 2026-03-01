import { ReactNode, CSSProperties } from 'react'

interface CardProps {
  children: ReactNode
  style?: CSSProperties
  borderColor?: 'green' | 'blue' | 'yellow' | 'none'
}

function Card({
  children,
  style = {},
  borderColor = 'none'
}: CardProps) {
  const baseStyles: CSSProperties = {
    backgroundColor: 'var(--color-surface-secondary)',
    borderRadius: 'var(--radius-md)',
    boxShadow: 'var(--shadow)',
    padding: '0.75rem 1rem',
    margin: '1rem 0',
  }

  const borderColors: Record<string, string> = {
    green: 'var(--color-card-border-green)',
    blue: 'var(--color-card-border-blue)',
    yellow: 'var(--color-card-border-yellow)'
  }
  const borderStyles: CSSProperties = borderColor !== 'none' && borderColor in borderColors
    ? { borderLeft: `3px solid ${borderColors[borderColor]}` }
    : {}

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

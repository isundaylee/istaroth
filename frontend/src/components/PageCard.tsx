import { ReactNode, CSSProperties } from 'react'
import Card from './Card'

interface PageCardProps {
  children: ReactNode
  style?: CSSProperties
}

function PageCard({ children, style = {} }: PageCardProps) {
  return (
    <Card
      style={{
        backgroundColor: 'white',
        borderRadius: 'var(--radius-md)',
        boxShadow: 'var(--shadow)',
        padding: '30px',
        margin: '0',
        ...style
      }}
    >
      {children}
    </Card>
  )
}

export default PageCard

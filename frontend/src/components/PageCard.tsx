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
        borderRadius: '12px',
        boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
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

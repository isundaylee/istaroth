import { ReactNode, CSSProperties } from 'react'
import styles from './Card.module.css'

interface CardProps {
  children: ReactNode
  // Kept for genuinely dynamic, per-instance overrides only; static styling
  // belongs in Card.module.css.
  style?: CSSProperties
}

function Card({ children, style }: CardProps) {
  return (
    <div className={styles.card} style={style}>
      {children}
    </div>
  )
}

export default Card

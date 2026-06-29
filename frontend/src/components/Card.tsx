import { ReactNode, CSSProperties } from 'react'
import clsx from 'clsx'
import styles from './Card.module.css'

interface CardProps {
  children: ReactNode
  // Kept for genuinely dynamic, per-instance overrides only; static styling
  // belongs in Card.module.css.
  style?: CSSProperties
  borderColor?: 'green' | 'blue' | 'yellow' | 'none'
}

function Card({ children, style, borderColor = 'none' }: CardProps) {
  return (
    <div
      className={clsx(styles.card, borderColor !== 'none' && styles[borderColor])}
      style={style}
    >
      {children}
    </div>
  )
}

export default Card

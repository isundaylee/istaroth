import { forwardRef } from 'react'
import styles from './Button.module.css'

interface ButtonProps extends React.ComponentPropsWithoutRef<'button'> {
  // "primary" (default): filled primary button.
  // "secondary": tonal outline button (share, export, load-more).
  // "ghost": transparent toolbar/inline button.
  // "icon": compact square icon-only button (close, fullscreen toggle).
  // "submit": fixed-width composer submit button.
  variant?: 'primary' | 'secondary' | 'ghost' | 'icon' | 'submit'
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', children, ...props }, ref) => (
    <button
      ref={ref}
      className={[styles.button, variant !== 'primary' && styles[variant], className].filter(Boolean).join(' ')}
      {...props}
    >
      {children}
    </button>
  )
)

Button.displayName = 'Button'

export default Button

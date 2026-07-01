import { forwardRef } from 'react'
import styles from './Button.module.css'

interface ButtonProps extends React.ComponentPropsWithoutRef<'button'> {
  // "submit": fixed-width composer submit button.
  // "secondary": tonal bordered button (share/export/load-more actions).
  // "ghost": transparent low-emphasis button (toolbar/link-style actions).
  // "icon": square icon-only button (close/fullscreen-toggle affordances).
  variant?: 'submit' | 'secondary' | 'ghost' | 'icon'
  // "sm": compact padding/font, layered on top of `variant`.
  size?: 'sm'
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, children, ...props }, ref) => (
    <button
      ref={ref}
      className={[styles.button, variant && styles[variant], size && styles[size], className].filter(Boolean).join(' ')}
      {...props}
    >
      {children}
    </button>
  )
)

Button.displayName = 'Button'

export default Button

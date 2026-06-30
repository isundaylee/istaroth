import { forwardRef } from 'react'
import styles from './Button.module.css'

interface ButtonProps extends React.ComponentPropsWithoutRef<'button'> {
  // "submit": fixed-width composer submit button.
  variant?: 'submit'
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, children, ...props }, ref) => (
    <button
      ref={ref}
      className={[styles.button, variant && styles[variant], className].filter(Boolean).join(' ')}
      {...props}
    >
      {children}
    </button>
  )
)

Button.displayName = 'Button'

export default Button

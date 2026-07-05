import { forwardRef } from 'react'
import styles from './Button.module.css'

interface ButtonProps extends React.ComponentPropsWithoutRef<'button'> {
  // "primary" (default): filled primary button.
  // "secondary": tonal outline button (share, export, load-more).
  // "ghost": transparent toolbar/inline button.
  // "icon": compact square icon-only button (close, fullscreen toggle).
  // "submit": fixed-width composer submit button.
  variant?: 'primary' | 'secondary' | 'ghost' | 'icon' | 'submit'
  // "md" (default): --control-height-md. "sm": --control-height-sm, layered
  // on top of any variant ("icon" instead shrinks its fixed square).
  size?: 'md' | 'sm'
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', children, ...props }, ref) => (
    <button
      ref={ref}
      className={[styles.button, variant !== 'primary' && styles[variant], size !== 'md' && styles[size], className]
        .filter(Boolean)
        .join(' ')}
      {...props}
    >
      {children}
    </button>
  )
)

Button.displayName = 'Button'

export default Button

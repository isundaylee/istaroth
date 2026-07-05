import { forwardRef } from 'react'
import styles from './Button.module.css'

interface ButtonProps extends React.ComponentPropsWithoutRef<'button'> {
  // "primary" (default): filled primary button.
  // "secondary": tonal outline button (share, export, load-more).
  // "ghost": transparent toolbar/inline button.
  // "icon": square icon-only button (close, fullscreen toggle).
  // "submit": fixed-width composer submit button.
  variant?: 'primary' | 'secondary' | 'ghost' | 'icon' | 'submit'
  // Owns the control height, layered on top of any variant ("icon" stays a
  // square of that height): "md" (default) --control-height-md, "sm"
  // --control-height-sm, "xs" --control-height-xs (dense chrome).
  size?: 'md' | 'sm' | 'xs'
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

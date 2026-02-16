import { forwardRef } from 'react'

const Button = forwardRef<HTMLButtonElement, React.ComponentPropsWithoutRef<'button'>>(
  ({ className, children, ...props }, ref) => (
    <button
      ref={ref}
      className={`button${className ? ` ${className}` : ''}`}
      {...props}
    >
      {children}
    </button>
  )
)

Button.displayName = 'Button'

export default Button

import { forwardRef } from 'react'

const Select = forwardRef<HTMLSelectElement, React.ComponentPropsWithoutRef<'select'>>(
  ({ className, children, ...props }, ref) => (
    <select
      ref={ref}
      className={`select${className ? ` ${className}` : ''}`}
      {...props}
    >
      {children}
    </select>
  )
)

Select.displayName = 'Select'

export default Select

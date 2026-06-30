import { forwardRef } from 'react'
import styles from './Select.module.css'

interface SelectProps extends React.ComponentPropsWithoutRef<'select'> {
  // "compact": muted-surface footer/options-row select used in the Composer footer.
  variant?: 'compact'
}

const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, variant, children, ...props }, ref) => (
    <select
      ref={ref}
      className={[styles.select, variant && styles[variant], className].filter(Boolean).join(' ')}
      {...props}
    >
      {children}
    </select>
  )
)

Select.displayName = 'Select'

export default Select

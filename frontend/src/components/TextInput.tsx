import { forwardRef } from 'react'
import styles from './TextInput.module.css'

const TextInput = forwardRef<HTMLInputElement, React.ComponentPropsWithoutRef<'input'>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      type="text"
      data-text-input=""
      className={[styles.textInput, className].filter(Boolean).join(' ')}
      {...props}
    />
  )
)

TextInput.displayName = 'TextInput'

export default TextInput

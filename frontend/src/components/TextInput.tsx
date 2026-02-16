import { forwardRef } from 'react'

const TextInput = forwardRef<HTMLInputElement, React.ComponentPropsWithoutRef<'input'>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      type="text"
      className={`text-input${className ? ` ${className}` : ''}`}
      {...props}
    />
  )
)

TextInput.displayName = 'TextInput'

export default TextInput

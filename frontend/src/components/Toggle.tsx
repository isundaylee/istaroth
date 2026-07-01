import styles from './Toggle.module.css'

interface ToggleOption<T extends string> {
  value: T
  label: React.ReactNode
}

// A segmented control: every option renders as its own button in a
// `role="group"`, not a `<select>`, so all choices stay visible at a glance
// rather than hidden behind a click.
interface ToggleProps<T extends string> extends Omit<React.ComponentPropsWithoutRef<'div'>, 'onChange'> {
  options: ToggleOption<T>[]
  value: T
  onChange: (value: T) => void
  disabled?: boolean
}

// Height/border/radius are meant to line up with <Select variant="compact">
// when both sit in the same control row.
function Toggle<T extends string>({ options, value, onChange, disabled = false, className, ...props }: ToggleProps<T>) {
  return (
    <div className={[styles.toggle, className].filter(Boolean).join(' ')} role="group" {...props}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`${styles.option} ${option.value === value ? styles.active : ''}`}
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
          disabled={disabled}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export default Toggle

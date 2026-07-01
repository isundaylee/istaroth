import styles from './Toggle.module.css'

interface ToggleOption<T extends string> {
  value: T
  label: React.ReactNode
}

interface ToggleProps<T extends string> extends Omit<React.ComponentPropsWithoutRef<'div'>, 'onChange'> {
  options: ToggleOption<T>[]
  value: T
  onChange: (value: T) => void
  disabled?: boolean
}

// Segmented toggle group for a small set of mutually-exclusive options (e.g.
// search mode, language). Renders as a `role="group"` of buttons rather than a
// <select>, since the whole point is showing every option at a glance.
function Toggle<T extends string>({ options, value, onChange, disabled, className, ...props }: ToggleProps<T>) {
  return (
    <div role="group" className={[styles.toggle, className].filter(Boolean).join(' ')} {...props}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={option.value === value ? styles.active : undefined}
          aria-pressed={option.value === value}
          disabled={disabled}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

export default Toggle

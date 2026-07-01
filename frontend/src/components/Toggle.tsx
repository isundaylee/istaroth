import { forwardRef } from 'react'
import styles from './Toggle.module.css'

interface ToggleProps {
  value: boolean
  onChange: (value: boolean) => void
  leftLabel: string
  rightLabel: string
  disabled?: boolean
  ariaLabel?: string
}

const Toggle = forwardRef<HTMLDivElement, ToggleProps>(
  ({ value, onChange, leftLabel, rightLabel, disabled = false, ariaLabel }, ref) => (
    <div
      ref={ref}
      className={styles.toggle}
      role="group"
      aria-label={ariaLabel}
    >
      <button
        type="button"
        className={`${styles.option} ${!value ? styles.active : ''}`}
        aria-pressed={!value}
        onClick={() => onChange(false)}
        disabled={disabled}
      >
        {leftLabel}
      </button>
      <button
        type="button"
        className={`${styles.option} ${value ? styles.active : ''}`}
        aria-pressed={value}
        onClick={() => onChange(true)}
        disabled={disabled}
      >
        {rightLabel}
      </button>
    </div>
  )
)

Toggle.displayName = 'Toggle'

export default Toggle

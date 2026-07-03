import { useEffect, useRef, useState } from 'react'
import styles from './SplitSelect.module.css'

export interface SplitSelectOption {
  value: string
  // Short label shown in the collapsed trigger and as the prominent left text of
  // the dropdown row.
  primary: string
  // Detail shown muted on the right of the dropdown row (not in the collapsed
  // trigger).
  secondary: string
}

interface SplitSelectProps {
  options: SplitSelectOption[]
  value: string
  onChange: (value: string) => void
  disabled?: boolean
  // Trigger text when nothing is selected yet (e.g. options still loading).
  placeholder: string
  ariaLabel: string
  className?: string
}

// A compact custom listbox for two-part options: the collapsed trigger shows only
// each option's short `primary` label, while the open dropdown lists both parts
// (`primary` prominent, `secondary` muted). A native <select> can't render
// different collapsed vs. list text, nor a two-part row, so this is hand-rolled.
function SplitSelect({ options, value, onChange, disabled, placeholder, ariaLabel, className }: SplitSelectProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const selected = options.find((o) => o.value === value)

  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  return (
    <div className={[styles.root, className].filter(Boolean).join(' ')} ref={rootRef}>
      <button
        type="button"
        className={styles.trigger}
        onClick={() => setOpen((o) => !o)}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        title={selected ? `${selected.primary} · ${selected.secondary}` : ariaLabel}
      >
        <span className={styles.triggerLabel}>{selected?.primary ?? placeholder}</span>
      </button>
      {open && (
        <ul className={styles.menu} role="listbox" aria-label={ariaLabel}>
          {options.map((opt) => (
            <li key={opt.value}>
              <button
                type="button"
                role="option"
                aria-selected={opt.value === value}
                className={[styles.option, opt.value === value ? styles.optionSelected : ''].filter(Boolean).join(' ')}
                onClick={() => {
                  onChange(opt.value)
                  setOpen(false)
                }}
              >
                <span className={styles.optionPrimary}>{opt.primary}</span>
                <span className={styles.optionSecondary}>{opt.secondary}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default SplitSelect

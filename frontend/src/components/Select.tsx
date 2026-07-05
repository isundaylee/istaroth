import { useEffect, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import styles from './Select.module.css'

export interface SelectOption {
  value: string
  // Shown in the collapsed trigger and as the row's main text.
  label: string
  // Optional detail shown muted on the right of the dropdown row only (not in the
  // collapsed trigger). Give it to abbreviate the trigger — e.g. show a model's
  // speed collapsed but its full name in the open list.
  detail?: string
}

interface SelectProps {
  options: SelectOption[]
  value: string
  onChange: (value: string) => void
  disabled?: boolean
  // Trigger text when nothing is selected yet (e.g. options still loading).
  placeholder?: string
  ariaLabel: string
  className?: string
}

// A compact custom-styled select: a trigger + hairline dropdown menu matching the
// Composer footer look, instead of the native browser control. The collapsed
// trigger shows the selected option's `label`; the open dropdown lists each
// option's `label` (and optional `detail`, muted).
function Select({ options, value, onChange, disabled, placeholder, ariaLabel, className }: SelectProps) {
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
        title={selected ? [selected.label, selected.detail].filter(Boolean).join(' · ') : ariaLabel}
      >
        <span className={styles.triggerLabel}>{selected?.label ?? placeholder ?? ''}</span>
        <ChevronDown className={styles.chevron} aria-hidden />
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
                <span className={styles.optionLabel}>{opt.label}</span>
                {opt.detail != null && <span className={styles.optionDetail}>{opt.detail}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default Select

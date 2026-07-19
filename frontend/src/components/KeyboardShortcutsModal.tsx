import { X } from 'lucide-react'
import { useT } from '../contexts/LanguageContext'
import Button from './Button'

interface KeyboardShortcutsModalProps {
  open: boolean
  onClose: () => void
}

function Keys({ keys }: { keys: string[] }) {
  return (
    <span style={{ display: 'flex', gap: '4px', flexShrink: 0 }}>
      {keys.map((key, index) => (
        <kbd
          key={index}
          style={{
            display: 'inline-block',
            minWidth: '1.5rem',
            padding: '2px 6px',
            textAlign: 'center',
            background: 'var(--color-bg)',
            border: '1px solid var(--color-border)',
            borderRadius: 'var(--radius-sm)',
            fontSize: 'var(--font-sm)',
            fontFamily: 'monospace',
            color: 'var(--color-text)'
          }}
        >
          {key}
        </kbd>
      ))}
    </span>
  )
}

function KeyboardShortcutsModal({ open, onClose }: KeyboardShortcutsModalProps) {
  const t = useT()

  if (!open) {
    return null
  }

  const rows: { keys: string[]; label: string }[] = [
    { keys: ['/'], label: t('keyboard.focusSearch') },
    { keys: ['Esc'], label: t('keyboard.deselect') },
    { keys: ['g', 'q'], label: t('keyboard.goQuery') },
    { keys: ['g', 'l'], label: t('keyboard.goLibrary') },
    { keys: ['s'], label: t('keyboard.toggleSidebar') },
    { keys: ['f'], label: t('keyboard.citationFullscreen') },
    { keys: ['e'], label: t('keyboard.citationLoadContext') },
    { keys: ['?'], label: t('keyboard.help') }
  ]

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        animation: 'fadeIn 0.2s ease',
        padding: '1rem'
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'var(--color-surface)',
          border: '1px solid var(--color-border)',
          borderRadius: 'var(--radius-md)',
          boxShadow: 'var(--shadow)',
          width: '100%',
          maxWidth: '420px',
          overflow: 'hidden'
        }}
      >
        <div
          style={{
            padding: '12px 16px',
            background: 'var(--color-primary-fill)',
            color: 'white',
            fontWeight: 600,
            fontSize: 'var(--font-sm)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}
        >
          <span>{t('keyboard.title')}</span>
          <Button
            type="button"
            variant="icon"
            size="xs"
            onClick={onClose}
            title={t('keyboard.close')}
            style={{ color: 'white' }}
          >
            <X aria-hidden />
          </Button>
        </div>
        <div style={{ padding: '0.25rem 1rem 0.25rem' }}>
          {rows.map(({ keys, label }, index) => (
            <div
              key={label}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '1rem',
                padding: '0.5rem 0',
                borderBottom: index < rows.length - 1 ? '1px solid var(--color-border)' : 'none'
              }}
            >
              <span style={{ color: 'var(--color-text)', fontSize: 'var(--font-base)' }}>{label}</span>
              <Keys keys={keys} />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default KeyboardShortcutsModal

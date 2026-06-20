import React from 'react'
import { useT } from '../contexts/LanguageContext'
import { useAppNavigate } from '../hooks/useAppNavigate'

export interface Crumb {
  label: string
  // Path to navigate to; the last crumb is always rendered as plain text and its
  // `to` (if any) is ignored.
  to?: string
}

// A clickable breadcrumb trail. Every crumb but the last navigates to its `to`;
// the last marks the current location and is plain text.
export default function Breadcrumbs({ crumbs }: { crumbs: Crumb[] }) {
  const t = useT()
  const navigate = useAppNavigate()
  if (crumbs.length === 0) return null
  return (
    <nav
      aria-label={t('library.breadcrumbAriaLabel')}
      style={{
        margin: '0 0 1rem',
        display: 'flex',
        flexWrap: 'wrap',
        gap: '0.25rem',
        alignItems: 'center',
      }}
    >
      {crumbs.map((crumb, index) => (
        <React.Fragment key={index}>
          {index > 0 && <span style={{ color: 'var(--color-text-secondary)' }}>/</span>}
          {index < crumbs.length - 1 && crumb.to ? (
            <button
              onClick={() => navigate(crumb.to!)}
              style={{
                background: 'none',
                border: 'none',
                padding: '0.25rem',
                cursor: 'pointer',
                color: 'var(--color-primary-text)',
                fontSize: 'var(--font-sm)',
              }}
            >
              {crumb.label}
            </button>
          ) : (
            <span style={{ padding: '0.25rem', fontSize: 'var(--font-sm)' }}>{crumb.label}</span>
          )}
        </React.Fragment>
      ))}
    </nav>
  )
}

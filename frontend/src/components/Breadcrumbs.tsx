import React from 'react'
import { useT } from '../contexts/LanguageContext'
import { useAppNavigate } from '../hooks/useAppNavigate'
import Button from './Button'

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
        gap: '0.5rem',
        alignItems: 'center',
      }}
    >
      {crumbs.map((crumb, index) => {
        const isLast = index === crumbs.length - 1
        return (
          <React.Fragment key={index}>
            {index > 0 && <span style={{ color: 'var(--color-text-muted)' }}>/</span>}
            {!isLast && crumb.to ? (
              <Button onClick={() => navigate(crumb.to!)} variant="ghost">
                {crumb.label}
              </Button>
            ) : (
              <span
                style={{
                  fontSize: 'var(--font-sm)',
                  fontWeight: 600,
                  color: 'var(--color-primary-text)',
                }}
              >
                {crumb.label}
              </span>
            )}
          </React.Fragment>
        )
      })}
    </nav>
  )
}

import React from 'react'
import { useT } from '../contexts/LanguageContext'
import Navigation from './Navigation'
import Card from './Card'
import TextInput from './TextInput'
import PageCard from './PageCard'
import LibraryHeader from './LibraryHeader'

// Shared presentation for the drill-down library hierarchies (quests, hangouts).
// The per-category pages own their data/drill-down state and just supply the
// search box, breadcrumb trail, and a grid of NavCards as children.

export interface Crumb {
  label: string
  onClick: () => void
}

interface NavCardProps {
  label: string
  count?: number
  sublabel?: string
  onClick: () => void
}

export function NavCard({ label, count, sublabel, onClick }: NavCardProps) {
  return (
    <div
      onClick={onClick}
      onMouseEnter={(e: React.MouseEvent<HTMLDivElement>) => {
        const card = e.currentTarget.querySelector('.card') as HTMLElement
        if (card) {
          card.style.backgroundColor = 'var(--color-surface-active)'
          card.style.transform = 'translateY(-2px)'
        }
      }}
      onMouseLeave={(e: React.MouseEvent<HTMLDivElement>) => {
        const card = e.currentTarget.querySelector('.card') as HTMLElement
        if (card) {
          card.style.backgroundColor = 'var(--color-surface-secondary)'
          card.style.transform = 'translateY(0)'
        }
      }}
    >
      <Card style={{ cursor: 'pointer', transition: 'all 0.2s', padding: '1rem', margin: 0 }}>
        <p style={{ margin: 0, wordBreak: 'break-word' }}>
          {label}
          {count !== undefined && (
            <span style={{ color: 'var(--color-text-secondary)' }}> ({count})</span>
          )}
        </p>
        {sublabel && (
          <p
            style={{
              margin: '0.25rem 0 0',
              wordBreak: 'break-word',
              color: 'var(--color-text-secondary)',
              fontSize: 'var(--font-sm)',
            }}
          >
            {sublabel}
          </p>
        )}
      </Card>
    </div>
  )
}

export function CardGrid({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
        gap: '1rem',
      }}
    >
      {children}
    </div>
  )
}

function Breadcrumbs({ crumbs }: { crumbs: Crumb[] }) {
  return (
    <div style={{ margin: '0 0 1rem', display: 'flex', flexWrap: 'wrap', gap: '0.25rem', alignItems: 'center' }}>
      {crumbs.map((crumb, index) => (
        <React.Fragment key={index}>
          {index > 0 && <span style={{ color: 'var(--color-text-secondary)' }}>/</span>}
          {index < crumbs.length - 1 ? (
            <button
              onClick={crumb.onClick}
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
    </div>
  )
}

interface HierarchyBrowserProps {
  title: string
  backText: string
  onBack?: () => void
  search: string
  onSearchChange: (value: string) => void
  searchPlaceholder: string
  // Shown only when more than one segment deep; pass [] (e.g. while searching) to hide.
  crumbs: Crumb[]
  children: React.ReactNode
}

export default function HierarchyBrowser({
  title,
  backText,
  onBack,
  search,
  onSearchChange,
  searchPlaceholder,
  crumbs,
  children,
}: HierarchyBrowserProps) {
  useT() // re-render on language change
  return (
    <>
      <Navigation />
      <main className="main">
        <PageCard>
          <LibraryHeader title={title} backPath="/library" backText={backText} onBack={onBack} />

          <TextInput
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={searchPlaceholder}
            style={{ width: '100%', marginBottom: '1rem' }}
          />

          {crumbs.length > 1 && <Breadcrumbs crumbs={crumbs} />}

          {children}
        </PageCard>
      </main>
    </>
  )
}

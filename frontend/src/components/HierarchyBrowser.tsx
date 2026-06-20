import React from 'react'
import { useT } from '../contexts/LanguageContext'
import Navigation from './Navigation'
import Card from './Card'
import TextInput from './TextInput'
import PageCard from './PageCard'
import LibraryHeader from './LibraryHeader'
import Breadcrumbs, { type Crumb } from './Breadcrumbs'

// Shared presentation for the drill-down library hierarchy. The HierarchyPage
// owns the tree/path state and just supplies the breadcrumb trail, search box,
// and a grid of NavCards as children.

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

interface HierarchyBrowserProps {
  title: string
  backText: string
  backPath: string
  search: string
  onSearchChange: (value: string) => void
  searchPlaceholder: string
  // The breadcrumb trail to the current view (rendered above the search box).
  crumbs: Crumb[]
  children: React.ReactNode
}

export default function HierarchyBrowser({
  title,
  backText,
  backPath,
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
          <LibraryHeader title={title} backPath={backPath} backText={backText} />

          <Breadcrumbs crumbs={crumbs} />

          <TextInput
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={searchPlaceholder}
            style={{ width: '100%', marginBottom: '1rem' }}
          />

          {children}
        </PageCard>
      </main>
    </>
  )
}

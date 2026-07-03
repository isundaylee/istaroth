import React from 'react'
import { useRouteLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import { useT } from './contexts/LanguageContext'
import Card from './components/Card'
import { translate } from './i18n'
import { getLanguageFromUrl } from './utils/language'
import { useAppNavigate } from './hooks/useAppNavigate'
import type { LibraryCategoriesResponse } from './types/api'

export async function libraryCategoriesPageLoader({ request }: LoaderFunctionArgs): Promise<LibraryCategoriesResponse> {
  const language = getLanguageFromUrl(request.url)

  const res = await fetch(`/api/library/categories?language=${language}`)
  if (!res.ok) {
    throw new Response(translate(language, 'library.errors.loadFailed'), { status: res.status })
  }
  return (await res.json()) as LibraryCategoriesResponse
}

// The Folio content at the bare /library entry. A placeholder catalogue until
// the front desk (continue reading / featured) replaces it; the categories also
// live in the layout rail, so this is intentionally simple for now.
function LibraryCategoriesPage() {
  const t = useT()
  const navigate = useAppNavigate()
  const { categories } = useRouteLoaderData('library-root') as LibraryCategoriesResponse

  const translateCategory = (category: string): string => {
    const translationKey = `library.categories.${category}`
    const translated = t(translationKey)
    return translated === translationKey ? category : translated
  }

  return (
    <div
      className="category-grid"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))',
        gap: '1rem'
      }}
    >
            {categories.map((category) => (
              <div
                key={category}
                onClick={() => navigate(`/library/${encodeURIComponent(category)}`)}
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
                <Card
                  style={{
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    padding: '1rem',
                    margin: 0
                  }}
                >
                  <p style={{ margin: 0, wordBreak: 'break-word' }}>
                    {translateCategory(category)}
                  </p>
                </Card>
              </div>
      ))}
    </div>
  )
}

export default LibraryCategoriesPage

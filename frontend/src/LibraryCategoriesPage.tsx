import React from 'react'
import { useNavigate, useLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import { useT } from './contexts/LanguageContext'
import Navigation from './components/Navigation'
import Card from './components/Card'
import PageCard from './components/PageCard'
import ErrorDisplay from './components/ErrorDisplay'
import { getLanguageFromUrl } from './utils/language'
import type { LibraryCategoriesResponse } from './types/api'

interface LoaderData {
  categories: string[]
  error?: string
}

export async function libraryCategoriesPageLoader({ request }: LoaderFunctionArgs): Promise<LoaderData> {
  const language = getLanguageFromUrl(request.url)

  try {
    const res = await fetch(`/api/library/categories?language=${language}`)
    if (!res.ok) {
      return { categories: [], error: 'Failed to load categories' }
    }
    const data = (await res.json()) as LibraryCategoriesResponse
    return { categories: data.categories }
  } catch (err) {
    return { categories: [], error: err instanceof Error ? err.message : 'Failed to load categories' }
  }
}

function LibraryCategoriesPage() {
  const t = useT()
  const navigate = useNavigate()
  const { categories, error } = useLoaderData() as LoaderData

  const translateCategory = (category: string): string => {
    const translationKey = `library.categories.${category}`
    const translated = t(translationKey)
    return translated === translationKey ? category : translated
  }

  return (
    <div className="app">
      <Navigation />
      <main className="main">
        {error && <ErrorDisplay error={error} />}
        <PageCard>
          <h1 style={{ marginBottom: '2rem', textAlign: 'center', fontSize: '2.5rem', color: '#2c3e50' }}>
            {t('library.title')}
          </h1>

          {!error && (
            <div>
              <div
                className="category-grid"
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(2, 1fr)',
                  gap: '1.5rem'
                }}
              >
                {categories.map((category) => (
                  <div
                    key={category}
                    onClick={() => navigate(`/library/${encodeURIComponent(category)}`)}
                    onMouseEnter={(e: React.MouseEvent<HTMLDivElement>) => {
                      const card = e.currentTarget.querySelector('.card') as HTMLElement
                      if (card) {
                        card.style.backgroundColor = '#f0f0f0'
                        card.style.transform = 'translateY(-2px)'
                      }
                    }}
                    onMouseLeave={(e: React.MouseEvent<HTMLDivElement>) => {
                      const card = e.currentTarget.querySelector('.card') as HTMLElement
                      if (card) {
                        card.style.backgroundColor = '#f8f9fa'
                        card.style.transform = 'translateY(0)'
                      }
                    }}
                    style={{
                      aspectRatio: '1',
                      minHeight: 0
                    }}
                  >
                    <Card
                      style={{
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                        padding: '1.5rem',
                        margin: 0,
                        height: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        borderRadius: '12px'
                      }}
                    >
                      <h3 style={{ margin: 0, textAlign: 'center', fontSize: '1.1rem', color: '#2c3e50' }}>
                        {translateCategory(category)}
                      </h3>
                    </Card>
                  </div>
                ))}
              </div>
            </div>
          )}
        </PageCard>
      </main>
    </div>
  )
}

export default LibraryCategoriesPage

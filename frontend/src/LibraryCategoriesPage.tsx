import React from 'react'
import { useLoaderData, type LoaderFunctionArgs } from 'react-router-dom'
import { useT } from './contexts/LanguageContext'
import Navigation from './components/Navigation'
import Card from './components/Card'
import PageCard from './components/PageCard'
import PageTitle from './components/PageTitle'
import { translate } from './i18n'
import { getLanguageFromUrl } from './utils/language'
import { useAppNavigate } from './hooks/useAppNavigate'
import type { LibraryCategoriesResponse } from './types/api'

interface LoaderData {
  categories: string[]
}

export async function libraryCategoriesPageLoader({ request }: LoaderFunctionArgs): Promise<LoaderData> {
  const language = getLanguageFromUrl(request.url)

  const res = await fetch(`/api/library/categories?language=${language}`)
  if (!res.ok) {
    throw new Response(translate(language, 'library.errors.loadFailed'), { status: res.status })
  }
  const data = (await res.json()) as LibraryCategoriesResponse
  return { categories: data.categories }
}

function LibraryCategoriesPage() {
  const t = useT()
  const navigate = useAppNavigate()
  const { categories } = useLoaderData() as LoaderData

  const translateCategory = (category: string): string => {
    const translationKey = `library.categories.${category}`
    const translated = t(translationKey)
    return translated === translationKey ? category : translated
  }

  return (
    <>
      <Navigation />
      <main className="main">
        <PageCard>
          <PageTitle>
            {t('library.title')}
          </PageTitle>

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
        </PageCard>
      </main>
    </>
  )
}

export default LibraryCategoriesPage

import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useT, useTranslation } from './contexts/LanguageContext'
import Navigation from './components/Navigation'
import Card from './components/Card'
import PageCard from './components/PageCard'
import ErrorDisplay from './components/ErrorDisplay'
import type { LibraryCategoriesResponse } from './types/api'

function LibraryCategoriesPage() {
  const t = useT()
  const { language } = useTranslation()
  const navigate = useNavigate()
  const [categories, setCategories] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const translateCategory = (category: string): string => {
    const translationKey = `library.categories.${category}`
    const translated = t(translationKey)
    return translated === translationKey ? category : translated
  }

  useEffect(() => {
    const fetchCategories = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(`/api/library/categories?language=${language}`)
        if (!res.ok) {
          throw new Error(t('library.errors.loadFailed'))
        }
        const data = (await res.json()) as LibraryCategoriesResponse
        setCategories(data.categories)
      } catch (err) {
        setError(err instanceof Error ? err.message : t('library.errors.unknown'))
      } finally {
        setLoading(false)
      }
    }

    fetchCategories()
  }, [language, t])

  return (
    <div className="app">
      <Navigation />
      <main className="main">
        {error && <ErrorDisplay error={error} />}
        <PageCard>
          <h1 style={{ marginBottom: '2rem', textAlign: 'center', fontSize: '2.5rem', color: '#2c3e50' }}>
            {t('library.title')}
          </h1>

          {loading && (
            <div style={{ textAlign: 'center', padding: '2rem' }}>
              {t('common.loading')}
            </div>
          )}

          {!loading && !error && (
            <div>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(3, 1fr)',
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

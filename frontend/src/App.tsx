import { useEffect, useRef } from 'react'
import { createBrowserRouter, RouterProvider, Outlet, ScrollRestoration, useLocation, useNavigate } from 'react-router-dom'
import { LanguageProvider, useTranslation } from './contexts/LanguageContext'
import DocumentTitle from './components/DocumentTitle'
import QueryPage from './QueryPage'
import ConversationPage from './ConversationPage'
import LibraryCategoriesPage from './LibraryCategoriesPage'
import LibraryFilesPage from './LibraryFilesPage'
import LibraryFileViewer, { libraryFileViewerLoader } from './LibraryFileViewer'
import NotFoundPage from './NotFoundPage'
import { getLanguageFromUrl, buildUrlWithLanguage, DEFAULT_LANGUAGE } from './utils/language'

function LanguageSync() {
  const { language, setLanguage } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()
  const isInitialMount = useRef(true)

  // On mount: sync URL language to context if URL has explicit lang param
  useEffect(() => {
    const urlLanguage = getLanguageFromUrl(window.location.href)
    if (urlLanguage !== DEFAULT_LANGUAGE && urlLanguage !== language) {
      setLanguage(urlLanguage)
    }
    isInitialMount.current = false
  }, [])

  // On language change: update URL
  useEffect(() => {
    if (isInitialMount.current) return
    const currentUrlLanguage = getLanguageFromUrl(window.location.href)
    if (currentUrlLanguage !== language) {
      const newUrl = buildUrlWithLanguage(location.pathname, location.search, language)
      navigate(newUrl, { replace: true })
    }
  }, [language, location.pathname, location.search, navigate])

  return null
}

function RootLayout() {
  return (
    <>
      <DocumentTitle />
      <LanguageSync />
      <Outlet />
      <ScrollRestoration getKey={(location) => location.pathname} />
    </>
  )
}

const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      { path: "/", element: <QueryPage /> },
      { path: "/conversation/:id", element: <ConversationPage /> },
      { path: "/library", element: <LibraryCategoriesPage /> },
      { path: "/library/:category", element: <LibraryFilesPage /> },
      { path: "/library/:category/:id", element: <LibraryFileViewer />, loader: libraryFileViewerLoader },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
])

function App() {
  return (
    <LanguageProvider>
      <RouterProvider router={router} />
    </LanguageProvider>
  )
}

export default App

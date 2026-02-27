import { createBrowserRouter, RouterProvider, Outlet, ScrollRestoration } from 'react-router-dom'
import { LanguageProvider } from './contexts/LanguageContext'
import { FooterProvider } from './contexts/FooterContext'
import DocumentTitle from './components/DocumentTitle'
import Footer from './components/Footer'
import ErrorBoundary from './components/ErrorBoundary'
import QueryPage from './QueryPage'
import RetrievePage from './RetrievePage'
import ConversationPage, { conversationPageLoader } from './ConversationPage'
import ShortURLRedirect, { shortURLLoader } from './ShortURLRedirect'
import LibraryCategoriesPage, { libraryCategoriesPageLoader } from './LibraryCategoriesPage'
import LibraryFilesPage, { libraryFilesPageLoader } from './LibraryFilesPage'
import LibraryFileViewer, { libraryFileViewerLoader } from './LibraryFileViewer'
import NotFoundPage from './NotFoundPage'

function RootLayout() {
  return (
    <LanguageProvider>
      <FooterProvider>
        <DocumentTitle />
        <div className="app">
          <Outlet />
          <Footer />
        </div>
        <ScrollRestoration />
      </FooterProvider>
    </LanguageProvider>
  )
}

const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      { path: "/", element: <QueryPage /> },
      { path: "/retrieve", element: <RetrievePage /> },
      { path: "/s/:slug", element: <ShortURLRedirect />, loader: shortURLLoader, errorElement: <ErrorBoundary /> },
      { path: "/conversation/:id", element: <ConversationPage />, loader: conversationPageLoader, errorElement: <ErrorBoundary /> },
      { path: "/library", element: <LibraryCategoriesPage />, loader: libraryCategoriesPageLoader, errorElement: <ErrorBoundary /> },
      { path: "/library/:category", element: <LibraryFilesPage />, loader: libraryFilesPageLoader, errorElement: <ErrorBoundary /> },
      { path: "/library/:category/:id", element: <LibraryFileViewer />, loader: libraryFileViewerLoader, errorElement: <ErrorBoundary /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
])

function App() {
  return <RouterProvider router={router} />
}

export default App

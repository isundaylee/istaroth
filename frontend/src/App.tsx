import { createBrowserRouter, RouterProvider, Outlet, ScrollRestoration } from 'react-router-dom'
import { LanguageProvider } from './contexts/LanguageContext'
import DocumentTitle from './components/DocumentTitle'
import ErrorBoundary from './components/ErrorBoundary'
import QueryPage from './QueryPage'
import ConversationPage, { conversationPageLoader } from './ConversationPage'
import LibraryCategoriesPage, { libraryCategoriesPageLoader } from './LibraryCategoriesPage'
import LibraryFilesPage, { libraryFilesPageLoader } from './LibraryFilesPage'
import LibraryFileViewer, { libraryFileViewerLoader } from './LibraryFileViewer'
import NotFoundPage from './NotFoundPage'

function RootLayout() {
  return (
    <LanguageProvider>
      <DocumentTitle />
      <Outlet />
      <ScrollRestoration  />
    </LanguageProvider>
  )
}

const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      { path: "/", element: <QueryPage /> },
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

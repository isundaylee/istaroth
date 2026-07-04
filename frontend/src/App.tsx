import { createBrowserRouter, RouterProvider, Outlet, ScrollRestoration } from 'react-router-dom'
import { LanguageProvider } from './contexts/LanguageContext'
import { FooterProvider } from './contexts/FooterContext'
import { ThemeProvider } from './contexts/ThemeContext'
import { MinimizedPopupProvider } from './contexts/MinimizedPopupContext'
import DocumentTitle from './components/DocumentTitle'
import KeyboardShortcuts from './components/KeyboardShortcuts'
import Footer from './components/Footer'
import ErrorBoundary from './components/ErrorBoundary'
import QueryPage from './QueryPage'
import ConversationPage, { conversationPageLoader } from './ConversationPage'
import HistoryPage, { historyPageLoader } from './HistoryPage'
import ShortURLRedirect, { shortURLLoader } from './ShortURLRedirect'
import LibraryLayout from './LibraryLayout'
import LibraryEntry, { libraryEntryLoader } from './LibraryEntry'
import HierarchyPage, { libraryCategoryLoader } from './HierarchyPage'
import LibraryFileViewer, { libraryFileViewerLoader } from './LibraryFileViewer'
import NotFoundPage from './NotFoundPage'
import styles from './RootLayout.module.css'

function RootLayout() {
  return (
    <LanguageProvider>
      <ThemeProvider>
      <FooterProvider>
        <MinimizedPopupProvider>
          <DocumentTitle />
          <KeyboardShortcuts />
          <div className={styles.app}>
            <main className={styles.main}>
              <Outlet />
            </main>
            <Footer />
          </div>
          <ScrollRestoration />
        </MinimizedPopupProvider>
      </FooterProvider>
      </ThemeProvider>
    </LanguageProvider>
  )
}

const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      { path: "/", element: <QueryPage /> },
      { path: "/s/:slug", element: <ShortURLRedirect />, loader: shortURLLoader, errorElement: <ErrorBoundary /> },
      { path: "/conversation/:id", element: <ConversationPage />, loader: conversationPageLoader, errorElement: <ErrorBoundary /> },
      { path: "/history", element: <HistoryPage />, loader: historyPageLoader, errorElement: <ErrorBoundary /> },
      {
        path: "/library",
        id: "library-root",
        element: <LibraryLayout />,
        loader: libraryEntryLoader,
        errorElement: <ErrorBoundary />,
        children: [
          { index: true, element: <LibraryEntry /> },
          {
            path: ":category",
            id: "library-category",
            loader: libraryCategoryLoader,
            errorElement: <ErrorBoundary />,
            children: [
              { index: true, element: <HierarchyPage /> },
              { path: "browse/*", element: <HierarchyPage /> },
              { path: ":id", element: <LibraryFileViewer />, loader: libraryFileViewerLoader },
            ],
          },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
])

function App() {
  return <RouterProvider router={router} />
}

export default App

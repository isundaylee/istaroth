import { createBrowserRouter, RouterProvider, Outlet, ScrollRestoration } from 'react-router-dom'
import { LanguageProvider } from './contexts/LanguageContext'
import { ErrorToastProvider } from './contexts/ErrorToastContext'
import { FooterProvider } from './contexts/FooterContext'
import { ThemeProvider } from './contexts/ThemeContext'
import { PopupCoordinatorProvider } from './contexts/PopupCoordinatorContext'
import DocumentTitle from './components/DocumentTitle'
import KeyboardShortcuts from './components/KeyboardShortcuts'
import Footer from './components/Footer'
import ErrorBoundary from './components/ErrorBoundary'
import QueryPage from './QueryPage'
import ConversationPage, { conversationPageLoader } from './ConversationPage'
import ConversationLayout from './ConversationLayout'
import ShortURLRedirect, { shortURLLoader } from './ShortURLRedirect'
import LibraryLayout, { libraryHierarchyLoader } from './LibraryLayout'
import LibraryEntry from './LibraryEntry'
import LibraryFileViewer, { libraryFileViewerLoader } from './LibraryFileViewer'
import NotFoundPage from './NotFoundPage'
import styles from './RootLayout.module.css'

function RootLayout() {
  return (
    <LanguageProvider>
      <ThemeProvider>
      <ErrorToastProvider>
      <FooterProvider>
        <PopupCoordinatorProvider>
          <DocumentTitle />
          <KeyboardShortcuts />
          <div className={styles.app}>
            <main className={styles.main}>
              <Outlet />
            </main>
            <Footer />
          </div>
          <ScrollRestoration />
        </PopupCoordinatorProvider>
      </FooterProvider>
      </ErrorToastProvider>
      </ThemeProvider>
    </LanguageProvider>
  )
}

const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      {
        element: <ConversationLayout />,
        children: [
          { path: "/", element: <QueryPage /> },
          { path: "/conversation/:id", element: <ConversationPage />, loader: conversationPageLoader, errorElement: <ErrorBoundary /> },
        ],
      },
      { path: "/s/:slug", element: <ShortURLRedirect />, loader: shortURLLoader, errorElement: <ErrorBoundary /> },
      {
        path: "/library",
        id: "library-root",
        element: <LibraryLayout />,
        loader: libraryHierarchyLoader,
        errorElement: <ErrorBoundary />,
        children: [
          { index: true, element: <LibraryEntry /> },
          {
            path: ":category",
            errorElement: <ErrorBoundary />,
            children: [
              { index: true, element: <LibraryEntry /> },
              { path: "browse/*", element: <LibraryEntry /> },
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

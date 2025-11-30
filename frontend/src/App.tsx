import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { LanguageProvider } from './contexts/LanguageContext'
import DocumentTitle from './components/DocumentTitle'
import QueryPage from './QueryPage'
import ConversationPage from './ConversationPage'
import LibraryCategoriesPage from './LibraryCategoriesPage'
import LibraryFilesPage from './LibraryFilesPage'
import LibraryFileViewer from './LibraryFileViewer'
import NotFoundPage from './NotFoundPage'

function App() {
  return (
    <LanguageProvider>
      <Router>
        <DocumentTitle />
        <Routes>
          <Route path="/" element={<QueryPage />} />
          <Route path="/conversation/:id" element={<ConversationPage />} />
          <Route path="/library" element={<LibraryCategoriesPage />} />
          <Route path="/library/:category" element={<LibraryFilesPage />} />
          <Route path="/library/:category/:id" element={<LibraryFileViewer />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Router>
    </LanguageProvider>
  )
}

export default App

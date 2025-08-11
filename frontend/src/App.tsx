import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import QueryPage from './QueryPage'
import ConversationPage from './ConversationPage'
import NotFoundPage from './NotFoundPage'

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<QueryPage />} />
        <Route path="/conversation/:id" element={<ConversationPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Router>
  )
}

export default App

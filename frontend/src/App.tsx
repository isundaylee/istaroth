import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import QueryPage from './QueryPage'
import ConversationPage from './ConversationPage'

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<QueryPage />} />
        <Route path="/conversation/:id" element={<ConversationPage />} />
      </Routes>
    </Router>
  )
}

export default App

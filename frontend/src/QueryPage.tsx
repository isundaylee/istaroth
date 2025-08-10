import { useState } from 'react'
import QueryForm from './QueryForm'

function QueryPage() {
  const [titleFadeOut, setTitleFadeOut] = useState(false)

  const handleTitleFadeOut = () => {
    if (!titleFadeOut) {
      setTitleFadeOut(true)
    }
  }


  return (
    <div className="app">
      <main className="main">
        <QueryForm onTitleFadeOut={handleTitleFadeOut} />

        <header className={`header${titleFadeOut ? ' fade-out' : ''}`}>
          <h1>伊斯塔露</h1>
          <img src="/istaroth-logo.png" alt="Istaroth Logo" className="logo" />
        </header>
      </main>
    </div>
  )
}

export default QueryPage

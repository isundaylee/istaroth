import { Link } from 'react-router-dom'
import Card from './components/Card'

function NotFoundPage() {
  return (
    <div className="app">
      <main className="main">
        <Card>
          <div style={{ textAlign: 'center', padding: '2rem 0' }}>
            <h1 style={{ fontSize: '4rem', margin: '0', color: '#666' }}>404</h1>
            <h2 style={{ margin: '1rem 0', color: '#333' }}>页面未找到</h2>
            <p style={{ margin: '1rem 0', color: '#666' }}>
              抱歉，您访问的页面不存在。
            </p>
            <Link
              to="/"
              className="back-link"
              style={{
                display: 'inline-block',
                marginTop: '1rem',
                padding: '0.5rem 1rem',
                backgroundColor: '#007bff',
                color: 'white',
                textDecoration: 'none',
                borderRadius: '4px',
                transition: 'background-color 0.2s'
              }}
              onMouseOver={(e) => e.currentTarget.style.backgroundColor = '#0056b3'}
              onMouseOut={(e) => e.currentTarget.style.backgroundColor = '#007bff'}
            >
              返回首页
            </Link>
          </div>
        </Card>
      </main>
    </div>
  )
}

export default NotFoundPage

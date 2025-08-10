import QueryForm from './QueryForm'
import Card from './components/Card'

function QueryPage() {
  return (
    <div className="app">
      <main className="main">
        <QueryForm />

        <div style={{
          textAlign: 'center',
          marginBottom: '40px'
        }}>
          <Card style={{
            backgroundColor: 'white',
            borderRadius: '12px',
            boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)',
            padding: '30px',
            margin: '0'
          }}>
            <h1 style={{ fontSize: '2.5rem', color: '#2c3e50', marginBottom: '15px' }}>
              伊斯塔露
            </h1>
            <img
              src="/istaroth-logo.png"
              alt="Istaroth Logo"
              style={{ width: '300px', height: '300px', borderRadius: '12px', margin: '0 auto', display: 'block' }}
            />
          </Card>
        </div>
      </main>
    </div>
  )
}

export default QueryPage

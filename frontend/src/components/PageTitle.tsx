interface PageTitleProps {
  children: React.ReactNode
  as?: 'h1' | 'h2' | 'h3'
  rightElement?: React.ReactNode
}

function PageTitle({ children, as: Component = 'h1', rightElement }: PageTitleProps) {
  return (
    <div style={{
      marginBottom: '2rem',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      position: rightElement ? 'relative' : undefined
    }}>
      <Component style={{
        margin: 0,
        fontSize: '2.5rem',
        color: '#2c3e50',
        textAlign: 'center'
      }}>
        {children}
      </Component>
      {rightElement && (
        <div style={{
          position: 'absolute',
          right: 0,
          top: '50%',
          transform: 'translateY(-50%)'
        }}>
          {rightElement}
        </div>
      )}
    </div>
  )
}

export default PageTitle

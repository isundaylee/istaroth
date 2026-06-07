interface PageTitleProps {
  children: React.ReactNode
  as?: 'h1' | 'h2' | 'h3'
}

function PageTitle({ children, as: Component = 'h1' }: PageTitleProps) {
  return (
    <div style={{
      marginBottom: '2rem',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center'
    }}>
      <Component style={{
        margin: 0,
        fontSize: 'var(--font-xl)',
        color: 'var(--color-heading)',
        textAlign: 'center'
      }}>
        {children}
      </Component>
    </div>
  )
}

export default PageTitle

import { forwardRef } from 'react'

interface CitationPopupProps {
  title: string
  content: string
  style?: React.CSSProperties
}

const CitationPopup = forwardRef<HTMLDivElement, CitationPopupProps>(
  ({ title, content, style }, ref) => {
    return (
      <div
        ref={ref}
        style={{
          position: 'fixed',
          background: 'white',
          border: '1px solid #ddd',
          borderRadius: '8px',
          boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
          maxWidth: '500px',
          minWidth: '300px',
          zIndex: 1000,
          animation: 'fadeIn 0.2s ease',
          pointerEvents: 'none',
          ...style
        }}
      >
        <div
          style={{
            padding: '12px 16px',
            background: '#3498db',
            color: 'white',
            fontWeight: 600,
            fontSize: '0.9rem',
            borderRadius: '8px 8px 0 0'
          }}
        >
          {title}
        </div>
        <div
          style={{
            padding: '16px',
            maxHeight: '300px',
            overflowY: 'auto',
            fontSize: '0.9rem',
            lineHeight: 1.6,
            color: '#333',
            whiteSpace: 'pre-wrap'
          }}
        >
          {content}
        </div>
      </div>
    )
  }
)

CitationPopup.displayName = 'CitationPopup'

export default CitationPopup

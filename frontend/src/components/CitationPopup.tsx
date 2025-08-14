import { forwardRef } from 'react'

interface CitationPopupProps {
  title: string
  content: string
  isSticky?: boolean
  onClose?: () => void
  style?: React.CSSProperties
}

const CitationPopup = forwardRef<HTMLDivElement, CitationPopupProps>(
  ({ title, content, isSticky = false, onClose, style }, ref) => {
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
          pointerEvents: 'auto',
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
            borderRadius: '8px 8px 0 0',
            position: 'relative',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}
        >
          <span>{title}</span>
          {isSticky && onClose && (
            <button
              onClick={onClose}
              style={{
                background: 'rgba(255, 255, 255, 0.2)',
                border: 'none',
                color: 'white',
                borderRadius: '25%',
                width: '22px',
                height: '22px',
                lineHeight: '22px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '16px',
                fontWeight: 'bold',
                transition: 'background-color 0.15s ease',
                marginLeft: '8px',
                paddingBottom: '1px',
                flexShrink: 0
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.3)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.2)'
              }}
              title="Close"
            >
              ×
            </button>
          )}
        </div>
        <div
          style={{
            padding: '16px',
            maxHeight: '300px',
            overflowY: 'auto',
            fontSize: '0.9rem',
            lineHeight: 1.6,
            color: '#333',
            whiteSpace: 'pre-wrap',
            scrollbarWidth: 'thin',
            scrollbarColor: '#3498db transparent'
          }}
          className="citation-popup-content"
        >
          {content}
        </div>
      </div>
    )
  }
)

CitationPopup.displayName = 'CitationPopup'

export default CitationPopup

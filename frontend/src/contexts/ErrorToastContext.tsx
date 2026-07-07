import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import Button from '../components/Button'
import { useT } from './LanguageContext'
import styles from './ErrorToast.module.css'

interface _Toast {
  id: number
  message: string
}

type _ShowError = (message: string) => void

const ErrorToastContext = createContext<_ShowError | null>(null)

/**
 * Site-wide error toasts. Components report failures via ``useErrorToast()``
 * instead of inlining an error box into their own layout; the provider owns
 * placement (a fixed top-center stack portaled to ``document.body``), spacing,
 * and dismissal. Toasts stay until dismissed; a message identical to one
 * already shown is not stacked again.
 */
export function ErrorToastProvider({ children }: { children: ReactNode }) {
  const t = useT()
  const [toasts, setToasts] = useState<_Toast[]>([])
  const nextIdRef = useRef(0)

  const showError = useCallback((message: string) => {
    setToasts((prev) =>
      prev.some((toast) => toast.message === message)
        ? prev
        : [...prev, { id: nextIdRef.current++, message }]
    )
  }, [])

  const dismiss = (id: number) => setToasts((prev) => prev.filter((toast) => toast.id !== id))

  return (
    <ErrorToastContext.Provider value={showError}>
      {children}
      {toasts.length > 0 &&
        createPortal(
          <div className={styles.stack}>
            {toasts.map((toast) => (
              <div key={toast.id} role="alert" className={styles.toast}>
                <p className={styles.message}>{toast.message}</p>
                <Button
                  type="button"
                  variant="icon"
                  size="xs"
                  onClick={() => dismiss(toast.id)}
                  aria-label={t('common.close')}
                  className={styles.close}
                >
                  <X aria-hidden />
                </Button>
              </div>
            ))}
          </div>,
          document.body
        )}
    </ErrorToastContext.Provider>
  )
}

export function useErrorToast(): _ShowError {
  const ctx = useContext(ErrorToastContext)
  if (!ctx) throw new Error('useErrorToast must be used within ErrorToastProvider')
  return ctx
}

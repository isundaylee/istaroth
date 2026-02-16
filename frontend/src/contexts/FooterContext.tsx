import { createContext, useContext, useState } from 'react'

type FooterContextValue = {
  extraContent: React.ReactNode | null
  setExtraContent: (content: React.ReactNode | null) => void
}

const FooterContext = createContext<FooterContextValue | null>(null)

export function FooterProvider({ children }: { children: React.ReactNode }) {
  const [extraContent, setExtraContent] = useState<React.ReactNode | null>(null)
  return (
    <FooterContext.Provider value={{ extraContent, setExtraContent }}>
      {children}
    </FooterContext.Provider>
  )
}

export function useFooter() {
  const ctx = useContext(FooterContext)
  if (!ctx) throw new Error('useFooter must be used within FooterProvider')
  return ctx
}

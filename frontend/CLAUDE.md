# Frontend Development Guide

## Localization System

React context-based i18n supporting Chinese (CHS) and English (ENG).

### Structure
```
src/i18n/          # Translation files (chs.ts, eng.ts, index.ts)
src/contexts/      # LanguageContext.tsx
```

### Usage
```tsx
import { useTranslation } from '../contexts/LanguageContext'

const { t, language, setLanguage } = useTranslation()
return <button>{t.common.submit}</button>
```

### Adding Translations
1. Add identical keys to both `chs.ts` and `eng.ts`
2. Use `t.feature.key` in components
3. TypeScript enforces matching structures

### Notes
- Auto-detects browser language, persists to localStorage
- Use nested keys for organization (e.g., `citation.*`, `query.*`)

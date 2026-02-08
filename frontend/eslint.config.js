import tseslint from 'typescript-eslint'

export default tseslint.config(
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      parser: tseslint.parser
    },
    rules: {
      'no-restricted-imports': ['error', {
        paths: [{
          name: 'react-router-dom',
          importNames: ['Link', 'useNavigate'],
          message: 'Use AppLink and useAppNavigate instead to preserve language query params.'
        }]
      }]
    }
  },
  {
    files: [
      'src/components/AppLink.tsx',
      'src/hooks/useAppNavigate.ts',
      'src/contexts/LanguageContext.tsx',
      'src/components/LanguageSwitcher.tsx'
    ],
    rules: {
      'no-restricted-imports': 'off'
    }
  }
)

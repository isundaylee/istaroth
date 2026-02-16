import { chs } from './chs'
import { eng } from './eng'

export const translations = { chs, eng }
export type Language = keyof typeof translations
export type TranslationKey = typeof chs

// Type helper for nested translation keys
export type NestedKeyOf<ObjectType extends object> = {
  [Key in keyof ObjectType & (string | number)]: ObjectType[Key] extends object
    ? `${Key}.${NestedKeyOf<ObjectType[Key]>}`
    : Key
}[keyof ObjectType & (string | number)]

export type TranslationPath = NestedKeyOf<TranslationKey>

export function translate(language: Language, path: string): string {
  const keys = path.split('.')
  let result: any = translations[language]

  for (const key of keys) {
    if (result && typeof result === 'object' && key in result) {
      result = result[key]
    } else {
      console.warn(`Translation key not found: ${path}`)
      return path
    }
  }

  return typeof result === 'string' ? result : path
}

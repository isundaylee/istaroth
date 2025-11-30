import type { Language } from '../i18n'

export const LANGUAGE_PARAM = 'lang'
export const DEFAULT_LANGUAGE: Language = 'chs'

export function getLanguageFromUrl(url: string): Language {
  const searchParams = new URL(url).searchParams
  const lang = searchParams.get(LANGUAGE_PARAM)
  return lang === 'eng' ? 'eng' : DEFAULT_LANGUAGE
}

export function buildUrlWithLanguage(pathname: string, search: string, language: Language): string {
  const params = new URLSearchParams(search)
  if (language === DEFAULT_LANGUAGE) {
    params.delete(LANGUAGE_PARAM)
  } else {
    params.set(LANGUAGE_PARAM, language)
  }
  const queryString = params.toString()
  return queryString ? `${pathname}?${queryString}` : pathname
}

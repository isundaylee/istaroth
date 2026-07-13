import { pinyin } from 'pinyin-pro'

// Any Han ideograph; we only pay the pinyin conversion for text that has one.
const HAS_HAN = /[一-鿿]/

// A lowercase blob combining the full pinyin and the first-letter initials of a
// title's Han characters, so a latin query can match a Chinese title by either
// its full spelling (e.g. "yunjin") or its initials (e.g. "yj"). Empty when the
// text has no Chinese, since the raw text is already searched directly.
export function pinyinSearchText(text: string): string {
  if (!HAS_HAN.test(text)) return ''
  const syllables = pinyin(text, { toneType: 'none', type: 'array', nonZh: 'removed' })
  return `${syllables.join('')} ${syllables.map((syllable) => syllable[0]).join('')}`
}

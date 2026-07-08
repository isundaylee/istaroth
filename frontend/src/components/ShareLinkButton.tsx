import { useState } from 'react'
import { Check, Share2, X } from 'lucide-react'
import { useT } from '../contexts/LanguageContext'
import Button from './Button'
import { createShortUrl } from '../utils/api'
import { copyToClipboard } from '../utils/clipboard'

// Icon button that creates (or reuses) a short URL for an in-app target path
// and copies it to the clipboard; the icon doubles as copy feedback.
export default function ShareLinkButton({ targetPath }: { targetPath: string }) {
  const t = useT()
  const [status, setStatus] = useState<'idle' | 'copied' | 'failed'>('idle')

  const copyShareUrl = async () => {
    try {
      const { slug } = await createShortUrl(targetPath)
      await copyToClipboard(`${window.location.origin}/s/${slug}`)
      setStatus('copied')
    } catch {
      setStatus('failed')
    }
    setTimeout(() => setStatus('idle'), 2000)
  }

  const title =
    status === 'copied'
      ? t('common.copied')
      : status === 'failed'
        ? t('common.copyFailed')
        : t('common.shareLink')

  return (
    <Button onClick={copyShareUrl} variant="icon" size="sm" title={title} aria-label={title}>
      {status === 'copied' ? <Check aria-hidden /> : status === 'failed' ? <X aria-hidden /> : <Share2 aria-hidden />}
    </Button>
  )
}

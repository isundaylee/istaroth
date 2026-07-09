import { useState } from 'react'
import { Check, Share2, X } from 'lucide-react'
import { useT } from '../contexts/LanguageContext'
import Button from './Button'
import { copyToClipboard } from '../utils/clipboard'

// Icon button that copies the share URL produced by getShareUrl to the
// clipboard; the icon doubles as copy feedback.
export default function ShareLinkButton({ getShareUrl }: { getShareUrl: () => Promise<string> }) {
  const t = useT()
  const [status, setStatus] = useState<'idle' | 'copied' | 'failed'>('idle')

  const copyShareUrl = async () => {
    try {
      await copyToClipboard(await getShareUrl())
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

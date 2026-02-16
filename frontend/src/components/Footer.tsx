import { useEffect, useState } from 'react'
import { useTranslation, useT } from '../contexts/LanguageContext'
import { useFooter } from '../contexts/FooterContext'

function Footer() {
  const { language } = useTranslation()
  const t = useT()
  const { extraContent } = useFooter()
  const [checkpointVersions, setCheckpointVersions] = useState<Record<string, string | null> | null>(null)

  useEffect(() => {
    fetch('/api/version')
      .then(res => res.ok ? res.json() : null)
      .then(data => { if (data) setCheckpointVersions(data.checkpoint_versions) })
      .catch(() => {})
  }, [])

  const rawVersion = checkpointVersions?.[language.toUpperCase()] ?? null
  const versionText = rawVersion ? `${t('footer.checkpointVersion')}: ${rawVersion.replace(/^checkpoint\//, '')}` : null

  if (!versionText && !extraContent) return null

  return (
    <footer style={{
      marginTop: '1rem',
      textAlign: 'center',
      fontSize: 'var(--font-xs)',
      color: '#999',
      lineHeight: 1.5
    }}>
      {extraContent && <div style={{ marginBottom: versionText ? '0.35rem' : 0 }}>{extraContent}</div>}
      {versionText}
    </footer>
  )
}

export default Footer

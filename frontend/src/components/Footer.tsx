import { useEffect, useState } from 'react'
import { useTranslation, useT } from '../contexts/LanguageContext'

function Footer() {
  const { language } = useTranslation()
  const t = useT()
  const [checkpointVersions, setCheckpointVersions] = useState<Record<string, string | null> | null>(null)

  useEffect(() => {
    fetch('/api/version')
      .then(res => res.ok ? res.json() : null)
      .then(data => { if (data) setCheckpointVersions(data.checkpoint_versions) })
      .catch(() => {})
  }, [])

  const rawVersion = checkpointVersions?.[language.toUpperCase()] ?? null
  const versionText = rawVersion ? `${t('footer.checkpointVersion')}: ${rawVersion.replace(/^checkpoint\//, '')}` : null

  if (!versionText) return null

  return (
    <footer style={{
      maxWidth: '800px',
      margin: '1rem auto 1rem',
      padding: '0 15px',
      textAlign: 'center',
      fontSize: '0.75rem',
      color: '#999',
    }}>
      {versionText}
    </footer>
  )
}

export default Footer

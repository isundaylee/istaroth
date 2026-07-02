import { useEffect, useState } from 'react'
import { useTranslation, useT } from '../contexts/LanguageContext'
import { useFooter } from '../contexts/FooterContext'
import appLinkStyles from './AppLink.module.css'

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

  return (
    <footer style={{
      marginTop: '1rem',
      textAlign: 'center',
      fontSize: 'var(--font-xs)',
      color: 'var(--color-text-muted)',
      lineHeight: 1.5
    }}>
      {extraContent && <div style={{ marginBottom: '0.35rem' }}>{extraContent}</div>}
      <div style={{ marginBottom: '0.35rem' }}>
        {t('query.title')} · {t('footer.tagline')}
      </div>
      <div>
        {versionText}
        {versionText && ' · '}
        <a
          href="https://github.com/isundaylee/istaroth"
          target="_blank"
          rel="noopener noreferrer"
          className={appLinkStyles.plain}
        >
          {t('meta.githubLink')}
        </a>
      </div>
    </footer>
  )
}

export default Footer

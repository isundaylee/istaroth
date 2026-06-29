import { useT } from '../contexts/LanguageContext'
import type { ProgressStepStart } from '../types/api'
import styles from './QueryProgress.module.css'

interface QueryProgressProps {
  steps: ProgressStepStart[]
  className?: string
}

function QueryProgress({ steps, className }: QueryProgressProps) {
  const t = useT()
  const stepLabel = (step: ProgressStepStart) => {
    if (step.kind === 'searching') {
      return `${t('query.progress.searching')} "${step.detail ?? ''}"`
    }
    return t(`query.progress.${step.kind}`)
  }

  return (
    <ul className={`${styles.progress}${className ? ` ${className}` : ''}`}>
      {steps.map((step) => (
        <li key={step.id} className={styles.item}>
          <span className={styles.loadingEllipsis}>{stepLabel(step)}</span>
        </li>
      ))}
    </ul>
  )
}

export default QueryProgress

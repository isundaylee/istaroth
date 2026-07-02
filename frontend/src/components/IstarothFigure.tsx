import { ReactNode } from 'react'
import clsx from 'clsx'
import greetUrl from '../assets/istaroth-greet.webp'
import thinkUrl from '../assets/istaroth-think.webp'
import styles from './IstarothFigure.module.css'

export type IstarothPose = 'greet' | 'think'

// The clock-tick ring carried over from the old home-page Dial — Istaroth is
// the God of Time, so her backdrop stays a slowly turning clock face (it spins
// faster while she "thinks"). Numerals are dropped: behind the character they
// read as clutter.
const RING_TICK_OUTER = 173

function Ring() {
  const ticks = Array.from({ length: 60 }, (_, i) => {
    const cardinal = i % 15 === 0
    const major = i % 5 === 0
    return {
      angle: i * 6,
      inner: cardinal ? 148 : major ? 155 : 161,
      width: cardinal ? 2 : 1,
      opacity: cardinal ? 0.85 : major ? 0.5 : 0.28,
    }
  })

  return (
    <svg className={styles.ring} viewBox="0 0 400 400" aria-hidden="true">
      <circle cx="200" cy="200" r="181" fill="none" stroke="var(--figure-line)" strokeWidth="1" />
      <circle cx="200" cy="200" r="117" fill="none" stroke="var(--figure-line)" strokeWidth="1" />
      <g className={styles.ringTicks}>
        {ticks.map((tick) => (
          <line
            key={tick.angle}
            x1="200"
            y1={200 - RING_TICK_OUTER}
            x2="200"
            y2={200 - tick.inner}
            stroke="var(--figure-gold)"
            strokeWidth={tick.width}
            strokeOpacity={tick.opacity}
            strokeLinecap="round"
            transform={`rotate(${tick.angle} 200 200)`}
          />
        ))}
      </g>
    </svg>
  )
}

interface IstarothFigureProps {
  pose: IstarothPose
  // Alt text for the character illustration.
  label: string
  // Speech-bubble overlay (upper left); the caller provides the content,
  // typically an interactive suggestion button.
  bubble?: ReactNode
  // Bottom-center overlay pill (the "thinking…" caption + progress steps).
  status?: ReactNode
  className?: string
}

// The Istaroth guide character over the clock ring. Both pose images stay
// mounted (so they're preloaded) and crossfade when `pose` changes; the
// container's fixed aspect ratio hard-cuts the artwork at its bottom edge so
// the figure reads as standing behind whatever sits under it.
function IstarothFigure({ pose, label, bubble, status, className }: IstarothFigureProps) {
  return (
    <div className={clsx(styles.figure, pose === 'think' && styles.thinking, className)}>
      {/* The artwork box owns the clipping so the bubble/status overlays can
          overhang the figure's edges without being cut. */}
      <div className={styles.artwork}>
        <Ring />
        <img
          src={greetUrl}
          alt={label}
          aria-hidden={pose !== 'greet'}
          className={clsx(styles.pose, styles.poseGreet)}
        />
        <img
          src={thinkUrl}
          alt={label}
          aria-hidden={pose !== 'think'}
          className={clsx(styles.pose, styles.poseThink)}
        />
      </div>
      {bubble && <div className={styles.bubble}>{bubble}</div>}
      {status && <div className={styles.status}>{status}</div>}
    </div>
  )
}

export default IstarothFigure

/* Inline SVG icons for icon-variant <Button>s. Text glyphs (×, ⛶, ⧉) sit on
   font-dependent baselines that misalign across platform fallback fonts, so
   these draw the same shapes on a fixed 24px grid with currentColor strokes,
   sized 1em to follow the button's per-size font-size. */

const svgProps = {
  width: '1em',
  height: '1em',
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
} as const

export function CloseIcon() {
  return (
    <svg {...svgProps}>
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  )
}

export function EnterFullscreenIcon() {
  return (
    <svg {...svgProps}>
      <path d="M9 4H6a2 2 0 0 0-2 2v3M15 4h3a2 2 0 0 1 2 2v3M9 20H6a2 2 0 0 1-2-2v-3M15 20h3a2 2 0 0 0 2-2v-3" />
    </svg>
  )
}

export function ExitFullscreenIcon() {
  return (
    <svg {...svgProps}>
      <path d="M4 9h3a2 2 0 0 0 2-2V4M20 9h-3a2 2 0 0 1-2-2V4M4 15h3a2 2 0 0 1 2 2v3M20 15h-3a2 2 0 0 0-2 2v3" />
    </svg>
  )
}

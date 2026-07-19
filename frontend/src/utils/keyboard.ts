/** Whether a keyboard shortcut should be suppressed because the target is a text-entry element. */
export function isEditable(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) {
    return false
  }
  return (
    target.tagName === 'INPUT' ||
    target.tagName === 'TEXTAREA' ||
    target.tagName === 'SELECT' ||
    target.isContentEditable
  )
}

/** Standard guard for single-key shortcuts: suppressed while typing or while a modifier is held. */
export function shouldIgnoreShortcut(e: KeyboardEvent): boolean {
  return isEditable(e.target) || e.metaKey || e.ctrlKey || e.altKey
}

/**
 * A dismissable surface (popup stack, drawer, dropdown, …) registered with the
 * central keyboard dispatcher (`components/KeyboardShortcuts`). Layers stack in
 * registration order, so the most recently opened surface is offered Escape and
 * single-key shortcuts first — one keypress dismisses one surface.
 */
export interface KeyboardLayer {
  /** Handle Escape; return false to pass it to the layer beneath (or the base blur behavior). */
  onEscape: () => boolean
  /** Resolve the layer's single-key shortcuts at event time. */
  shortcuts?: () => Record<string, () => void> | undefined
}

// Registrations hold refs (not snapshots) so handlers read fresh state at event
// time without re-registering — re-registering would reorder the stack.
interface _LayerRef {
  readonly current: KeyboardLayer
}
interface _ShortcutsRef {
  readonly current: Record<string, () => void>
}

const _layers: _LayerRef[] = []
const _globalShortcuts: _ShortcutsRef[] = []

/** Push a layer onto the stack; returns its unregister function. */
export function registerKeyboardLayer(layer: _LayerRef): () => void {
  _layers.push(layer)
  return () => {
    const index = _layers.indexOf(layer)
    if (index !== -1) _layers.splice(index, 1)
  }
}

/** Register single-key shortcuts active beneath all layers (e.g. PageShell's `s`); returns the unregister function. */
export function registerGlobalShortcuts(shortcuts: _ShortcutsRef): () => void {
  _globalShortcuts.push(shortcuts)
  return () => {
    const index = _globalShortcuts.indexOf(shortcuts)
    if (index !== -1) _globalShortcuts.splice(index, 1)
  }
}

/** Offer Escape to layers top-down; true once one handles it. */
export function dispatchEscape(): boolean {
  for (let i = _layers.length - 1; i >= 0; i--) {
    if (_layers[i].current.onEscape()) return true
  }
  return false
}

/** The topmost layer shortcut for `key`, falling back to global registrations. */
export function findShortcut(key: string): (() => void) | undefined {
  for (let i = _layers.length - 1; i >= 0; i--) {
    const handler = _layers[i].current.shortcuts?.()?.[key]
    if (handler) return handler
  }
  for (let i = _globalShortcuts.length - 1; i >= 0; i--) {
    const handler = _globalShortcuts[i].current[key]
    if (handler) return handler
  }
  return undefined
}

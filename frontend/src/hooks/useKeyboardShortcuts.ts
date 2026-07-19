import { useEffect, useRef } from 'react'
import { KeyboardLayer, registerGlobalShortcuts, registerKeyboardLayer } from '../utils/keyboard'

/**
 * Register a dismissable layer with the central keyboard dispatcher while
 * `active`. The layer's position in the stack is fixed at activation time
 * (handlers are read through a ref, so they stay fresh without re-registering).
 */
export function useKeyboardLayer(active: boolean, layer: KeyboardLayer): void {
  const ref = useRef(layer)
  ref.current = layer
  useEffect(() => (active ? registerKeyboardLayer(ref) : undefined), [active])
}

/** Register single-key shortcuts active beneath all layers; pass null to deactivate. */
export function useGlobalShortcuts(shortcuts: Record<string, () => void> | null): void {
  const ref = useRef(shortcuts ?? {})
  ref.current = shortcuts ?? {}
  const active = shortcuts !== null
  useEffect(() => (active ? registerGlobalShortcuts(ref) : undefined), [active])
}

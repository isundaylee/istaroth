import { useLayoutEffect, useRef, type ReactNode } from 'react'

interface ComposerProps {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  placeholder?: string
  disabled?: boolean
  rows?: number
  // Enter submits (Shift+Enter inserts a newline). When false, only Cmd/Ctrl+Enter
  // submits and a bare Enter inserts a newline.
  submitOnEnter?: boolean
  // Footer left slot: model/preset selects, search-mode toggle, etc.
  controls?: ReactNode
  // Footer right slot: the submit button (type="submit").
  actions: ReactNode
}

const resizeTextarea = (textarea: HTMLTextAreaElement) => {
  textarea.style.height = 'auto'
  textarea.style.height = `${textarea.scrollHeight}px`
}

// The shared search/ask input box: a bordered composer with an auto-resizing
// textarea on top and a footer holding caller-supplied controls and a submit
// button. Used by the Q&A QueryForm and the Retrieve page.
function Composer({
  value,
  onChange,
  onSubmit,
  placeholder,
  disabled,
  rows = 2,
  submitOnEnter = false,
  controls,
  actions,
}: ComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Layout effects (not useEffect) so the textarea is focused and sized to its
  // content before the browser paints — otherwise the box visibly jumps from the
  // `rows` height to the measured height on every mount.
  useLayoutEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.focus()
      resizeTextarea(textareaRef.current)
    }
  }, [])

  useLayoutEffect(() => {
    if (textareaRef.current) resizeTextarea(textareaRef.current)
  }, [value])

  return (
    <form
      className="query-form"
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit()
      }}
    >
      <div className="query-composer">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            const shouldSubmit = submitOnEnter
              ? e.key === 'Enter' && !e.shiftKey
              : e.key === 'Enter' && (e.metaKey || e.ctrlKey)
            if (shouldSubmit) {
              e.preventDefault()
              e.currentTarget.form?.requestSubmit()
            }
          }}
          placeholder={placeholder}
          disabled={disabled}
          className="query-textarea"
          rows={rows}
        />
        <div className="query-composer-footer">
          {controls}
          {actions}
        </div>
      </div>
    </form>
  )
}

export default Composer

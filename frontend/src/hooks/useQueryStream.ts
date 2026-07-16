import { useCallback, useState } from 'react'
import { useT } from '../contexts/LanguageContext'
import { useErrorToast } from '../contexts/ErrorToastContext'
import { useAppNavigate } from './useAppNavigate'
import { consumeQueryStream, postQueryStream } from '../utils/queryStream'
import type { QueryRequest, ProgressStepStart } from '../types/api'

interface UseQueryStreamResult {
  /** Pipeline steps that have started but not yet ended, in start order. */
  activeSteps: ProgressStepStart[]
  /** Accumulated answer text so far; empty until the first chunk arrives. */
  streamedAnswer: string
  /**
   * Whether answer text has started arriving (the view swaps to the
   * conversation layout at this point). Derived from ``streamedAnswer`` — the
   * backend only emits non-empty chunk text.
   */
  streaming: boolean
  loading: boolean
  /** The question of the in-flight request; empty when idle. */
  submittedQuestion: string
  /** Submit a query and drive the stream to completion. */
  submit: (request: QueryRequest) => Promise<void>
  /**
   * Clear all stream state, including ``loading``. Needed by pages that stay
   * mounted across the post-``done`` navigation (a conversation-to-conversation
   * re-ask only changes the route param, so the component instance — and this
   * hook's state — survives); call it when the new loader data arrives.
   */
  reset: () => void
}

/**
 * Owns the query stream lifecycle: POSTing ``/api/query/stream``, consuming its
 * NDJSON events, and navigating to the saved conversation on ``done``. Exposes
 * the in-flight steps and the progressively streamed answer so a page can swap
 * to the conversation view the moment answer text starts arriving.
 */
export function useQueryStream(): UseQueryStreamResult {
  const t = useT()
  const showError = useErrorToast()
  const navigate = useAppNavigate()
  const [loading, setLoading] = useState(false)
  const [activeSteps, setActiveSteps] = useState<ProgressStepStart[]>([])
  const [streamedAnswer, setStreamedAnswer] = useState('')
  const [submittedQuestion, setSubmittedQuestion] = useState('')

  const reset = useCallback(() => {
    setLoading(false)
    setActiveSteps([])
    setStreamedAnswer('')
    setSubmittedQuestion('')
  }, [])

  const submit = useCallback(async (request: QueryRequest) => {
    reset()
    setLoading(true)
    setSubmittedQuestion(request.question)

    try {
      const result = await postQueryStream(request, t('query.errors.unknown'))
      if ('error' in result) {
        showError(result.error)
        setLoading(false)
        return
      }

      await consumeQueryStream(result.body, {
        onStepStart: (step) => setActiveSteps((prev) => [...prev, step]),
        onStepEnd: (id) => setActiveSteps((prev) => prev.filter((step) => step.id !== id)),
        // Accumulate answer text; ``streaming`` follows from a non-empty buffer.
        // Steps are left as-is here — the display gates on ``streaming`` so a
        // late step_start (e.g. CHS proper-noun extraction firing after the last
        // chunk) never repaints the step indicator over the growing answer.
        onAnswerChunk: (text) => setStreamedAnswer((prev) => prev + text),
        onDone: (result) => {
          // The streamed view and the canonical conversation view are the same
          // component with the same text, so this swap is visually a no-op that
          // reveals proper-noun highlights and share/export affordances. A plain
          // push (not replace) keeps the pre-submit entry — '/' or the previous
          // conversation — in history so Back returns to it. Loading stays true
          // so the composer remains disabled until the route actually changes;
          // a page that survives the navigation (ConversationPage on a re-ask)
          // calls ``reset`` once the new conversation's loader data lands.
          navigate(`/conversation/${result.conversation_uuid}`)
        },
        onError: (message) => {
          // Tear down the streaming view and restore the composer.
          reset()
          showError(message)
        },
        noConnectionError: t('query.errors.noConnection'),
        unknownError: t('query.errors.unknown'),
      })
    } catch {
      reset()
      showError(t('query.errors.noConnection'))
    }
  }, [t, showError, navigate, reset])

  return { activeSteps, streamedAnswer, streaming: streamedAnswer !== '', loading, submittedQuestion, submit, reset }
}

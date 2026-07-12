# Interaction protocol

Use native form controls because the injected review SDK keeps them interactive while leaving surrounding content annotatable.

Wrap each question in a form with a stable `data-review-question` value. On submit, read its current values and call:

```js
window.htmlReview.queuePrompt(prompt, {
  tag: "answer",
  text: summary,
  element: form,
  data: { question: questionId, answer },
});
```

`prompt` must be a complete instruction an agent can act on. `text` is the compact queued-item label. `element` associates the answer with the question. The wrapper's `data-review-question` value supplies a stable queue key, so submitting the same question again replaces its unsent answer.

Replacement keys apply only to structured answers. Inline annotations always pass `queueKey: ""`, so every annotation remains independently queued even when its target is inside a question form. Never let an annotation inherit the surrounding question's key.

Do not queue from `change`, `input`, or option-click handlers. Those interactions remain reversible local state. Queue exactly once from the form's submit action.

The injected SDK handles keyboard shortcuts. `Command+Enter` or `Ctrl+Enter` calls `requestSubmit()` on the focused `form[data-review-question]` or queues the open annotation. In the shell composer it queues the general note. `Command+S` or `Ctrl+S` prevents the browser Save dialog and sends all queued feedback. `Escape` closes the open annotation box, clears its temporary selection styling, and queues nothing. Do not override these keys in artifact scripts.

The surrounding review shell owns the final send action, allowing the user to combine answers and annotations. Ordinary text and containers need no attributes. Add `data-review-action` only to a non-native clickable widget that should operate instead of being annotated.

The injected SDK ignores `html`, `body`, and `main` so clicks on page-level whitespace do nothing. Add `data-review-ignore` to any additional decorative or structural element that should never open an annotation box.

When opened directly without the review server, guard the API and show a small status message rather than throwing:

```js
if (!window.htmlReview?.queuePrompt) {
  status.textContent = "Open this page through the review session to queue feedback.";
  return;
}
```

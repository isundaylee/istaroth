---
name: html-review
description: Create a simple, modern HTML review page and run a local browser feedback loop with inline element/text annotations and structured questions. Use when the user wants to discuss or iterate on a design, plan, comparison, scope decision, content draft, or other topic that is easier to review visually than in chat.
---

# HTML Review

Create one focused, self-contained HTML page, open it with the bundled local review server, and iterate on returned annotations and answers. Prefer this lightweight review surface over a dashboard or full application.

## Workflow

1. Inspect the subject project for relevant design tokens or visual conventions. Use them only when they improve fidelity; otherwise use the bundled neutral template.
2. Copy `assets/review-template.html` to `tmp-local/reviews/<short-name>.html`. Create the destination directory when needed. Keep generated review artifacts out of tracked source directories.
3. Replace the template's sample content and questions. Keep the page self-contained unless local assets materially help.
4. Read [interaction-protocol.md](references/interaction-protocol.md) before adding or changing controls.
5. Run `scripts/review.py open <html-file>` to start or resume the local session. Use `--no-open` when a browser cannot run on the agent host. Give the user the printed URL when they need to open it themselves.
6. Run `scripts/review.py poll <html-file>` and keep the poll attached to the active turn. If it is interrupted, run it again; submitted feedback persists.
7. Address returned annotations, answers, and layout errors in the HTML, then poll again with a concise update. Continue until the user ends the session or says the review is complete.
8. Run `scripts/review.py end <html-file>` when the review is complete.

## Page standard

- Default to a guided review: present one or two explicit questions with clear choices and short tradeoffs. Use an open annotation-only canvas only when structured choices would be artificial.
- Present one clear title, a one-sentence purpose, the material under review, and only the questions needed for the current iteration.
- Use a calm neutral palette, system fonts, generous spacing, subtle borders, and one restrained accent color. Support light and dark color schemes.
- Keep the main column between `680px` and `900px`; add a side-by-side comparison only when it materially helps a choice.
- Use short cards or sections, not nested panels. Avoid decorative gradients, oversized hero text, charts, navigation, and ornamental badges.
- Use native radios, checkboxes, selects, inputs, and textareas. Keep each question independently submit-able with one `Queue answer` button.
- Support `Command+Enter` and `Ctrl+Enter` to queue the active question, annotation, or general note. Support `Command+S` and `Ctrl+S` to send all queued feedback. Use `Escape` to dismiss the open annotation box without queuing it.
- Preserve inline annotation: do not intercept ordinary clicks on non-control content and do not add `data-review-action` except to a custom interactive element.
- Keep page-background and outer-layout whitespace inert. The runtime ignores `html`, `body`, `main`, and elements marked `data-review-ignore` as annotation targets.
- Make every feedback target understandable in isolation through headings and nearby context.
- Do not rely on remote fonts, frameworks, or CDNs. The page must remain useful when opened directly.
- Verify keyboard focus, mobile layout, long text wrapping, and absence of horizontal overflow.

## Review behavior

- Use structured controls for concrete choices and inline annotations for localized comments or selected text.
- Keep selection changes local until the user presses that question's `Queue answer` button.
- Queue an actionable sentence that includes the question and selected answer, plus structured `data` when useful.
- Do not auto-send feedback. Let the user inspect queued items and use the review shell's `Send to agent` control.
- Treat the HTML as disposable working material. Put durable outcomes back into the appropriate project files or conversation after review.

## Runtime and safety

Use only the bundled standard-library Python runtime. It serves the selected artifact, injects the annotation SDK in memory, stores feedback beside the disposable artifact, and never modifies the source HTML. It makes no network requests and binds to `127.0.0.1` by default. Do not use `--host 0.0.0.0`, `--host ::`, or another externally reachable interface without explicit user approval.

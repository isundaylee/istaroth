// navigator.clipboard is only exposed in secure contexts (HTTPS or localhost),
// so it is undefined when the app is served over plain HTTP by hostname. Fall
// back to a temporary-textarea execCommand copy there.
export async function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard) {
    return navigator.clipboard.writeText(text)
  }
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  try {
    if (!document.execCommand('copy')) {
      throw new Error('copy command was unsuccessful')
    }
  } finally {
    document.body.removeChild(textarea)
  }
}

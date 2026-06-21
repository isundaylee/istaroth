const CLIENT_ID_KEY = 'istaroth_client_id'

// Build a v4 UUID from getRandomValues rather than crypto.randomUUID(): the
// latter is only exposed in secure contexts (HTTPS or localhost) and so is
// undefined when the dev stack is reached over plain HTTP by hostname.
// getRandomValues is an equally strong CSPRNG and works in insecure contexts.
function _randomUUID(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0'))
  return `${hex.slice(0, 4).join('')}-${hex.slice(4, 6).join('')}-${hex.slice(6, 8).join('')}-${hex.slice(8, 10).join('')}-${hex.slice(10, 16).join('')}`
}

// Returns a stable anonymous identifier for this browser, generating and
// persisting one on first use. Used to scope a user's conversation history
// without requiring any registration or login.
export function getClientId(): string {
  let clientId = localStorage.getItem(CLIENT_ID_KEY)
  if (!clientId) {
    clientId = _randomUUID()
    localStorage.setItem(CLIENT_ID_KEY, clientId)
  }
  return clientId
}

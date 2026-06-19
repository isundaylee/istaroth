const CLIENT_ID_KEY = 'istaroth_client_id'

// Returns a stable anonymous identifier for this browser, generating and
// persisting one on first use. Used to scope a user's conversation history
// without requiring any registration or login.
export function getClientId(): string {
  let clientId = localStorage.getItem(CLIENT_ID_KEY)
  if (!clientId) {
    clientId = crypto.randomUUID()
    localStorage.setItem(CLIENT_ID_KEY, clientId)
  }
  return clientId
}

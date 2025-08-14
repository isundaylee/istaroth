/**
 * API request and response types for the frontend.
 *
 * IMPORTANT: Keep these types in sync with istaroth/backend/models.py
 * Any changes to request/response structures should be reflected in both files.
 */

export interface QueryResponse {
  question: string
  answer: string
  conversation_id: string
  language: string
}

export interface ErrorResponse {
  error: string
}

export interface ModelsResponse {
  models: string[]
}

export interface ConversationResponse {
  uuid: string
  language: string
  question: string
  answer: string
  model: string
  k: number
  created_at: number
  generation_time_seconds: number
}

export interface ExampleQuestionRequest {
  language: string
}

export interface ExampleQuestionResponse {
  question: string
  language: string
}

export interface CitationResponse {
  file_id: string
  chunk_index: number
  content: string
  metadata: Record<string, any>
}

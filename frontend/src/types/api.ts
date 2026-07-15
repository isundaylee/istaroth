/**
 * API request and response types for the frontend.
 *
 * These types are automatically generated from the OpenAPI specification.
 * DO NOT manually edit these types - they are kept in sync with the backend.
 *
 * To update types:
 * 1. Run: PYTHONPATH=. uv run python scripts/generate_openapi.py
 * 2. Run: npm run generate-types
 */

import type { components } from './api-generated'

// Export the schema types directly from the generated OpenAPI types
export type QueryRequest = components['schemas']['QueryRequest']
export type QueryResponse = components['schemas']['QueryResponse']
export type ModelsResponse = components['schemas']['ModelsResponse']
export type ConversationResponse = components['schemas']['ConversationResponse']
export type ConversationSummary = components['schemas']['ConversationSummary']
export type ConversationListResponse = components['schemas']['ConversationListResponse']
export type ExampleQuestionResponse = components['schemas']['ExampleQuestionResponse']
export type CitationResponse = components['schemas']['CitationResponse']
export type CitationBatchRequest = components['schemas']['CitationBatchRequest']
export type CitationBatchResponse = components['schemas']['CitationBatchResponse']
export type CitationError = components['schemas']['CitationError']
export type LibraryRetrieveRequest = components['schemas']['LibraryRetrieveRequest']
export type LibraryRetrieveResponse = components['schemas']['LibraryRetrieveResponse']
export type ShortURLResponse = components['schemas']['ShortURLResponse']
export type LibraryFileInfo = components['schemas']['LibraryFileInfo']
export type LibraryFileResponse = components['schemas']['LibraryFileResponse']
export type ProperNounsResponse = components['schemas']['ProperNounsResponse']
export type LibraryHierarchyResponse = components['schemas']['LibraryHierarchyResponse']
export type LibraryCategoryHierarchy = components['schemas']['LibraryCategoryHierarchy']
export type HierarchyNode = components['schemas']['HierarchyNode']

// Additional types that may not be in the OpenAPI spec but are used by the frontend
export interface ErrorResponse {
  error: string
}

// Progress events streamed (newline-delimited JSON) by POST /api/query/stream.
export type ProgressStepStart = components['schemas']['QueryStreamStepStart']
export type ProgressStepEnd = components['schemas']['QueryStreamStepEnd']
export type ProgressAnswerChunk = components['schemas']['QueryStreamAnswerChunk']
export type ProgressDone = components['schemas']['QueryStreamDone']
export type ProgressError = components['schemas']['QueryStreamError']

export type ProgressMessage =
  | ProgressStepStart
  | ProgressStepEnd
  | ProgressAnswerChunk
  | ProgressDone
  | ProgressError

export interface ExampleQuestionRequest {
  language: string
}

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
export type LibraryRetrieveRequest = components['schemas']['LibraryRetrieveRequest']
export type LibraryRetrieveResponse = components['schemas']['LibraryRetrieveResponse']
export type ShortURLResponse = components['schemas']['ShortURLResponse']
export type LibraryCategoriesResponse = components['schemas']['LibraryCategoriesResponse']
export type LibraryFileInfo = components['schemas']['LibraryFileInfo']
export type LibraryFilesResponse = components['schemas']['LibraryFilesResponse']
export type LibraryFileResponse = components['schemas']['LibraryFileResponse']
export type QuestHierarchyResponse = components['schemas']['QuestHierarchyResponse']
export type QuestSeriesResponse = components['schemas']['QuestSeriesResponse']
export type QuestHierarchyType = components['schemas']['QuestHierarchyType']
export type QuestHierarchySeries = components['schemas']['QuestHierarchySeries']
export type QuestHierarchyChapter = components['schemas']['QuestHierarchyChapter']
export type QuestHierarchyQuest = components['schemas']['QuestHierarchyQuest']
export type CoopHierarchyResponse = components['schemas']['CoopHierarchyResponse']
export type CoopCharacterResponse = components['schemas']['CoopCharacterResponse']
export type CoopHierarchyCharacter = components['schemas']['CoopHierarchyCharacter']
export type CoopHierarchyChapter = components['schemas']['CoopHierarchyChapter']
export type CoopHierarchyQuest = components['schemas']['CoopHierarchyQuest']

// Additional types that may not be in the OpenAPI spec but are used by the frontend
export interface ErrorResponse {
  error: string
}

// Progress events streamed (newline-delimited JSON) by POST /api/query/stream.
export type ProgressStepStart = components['schemas']['QueryStreamStepStart']
export type ProgressStepEnd = components['schemas']['QueryStreamStepEnd']
export type ProgressDone = components['schemas']['QueryStreamDone']
export type ProgressError = components['schemas']['QueryStreamError']

export type ProgressMessage =
  | ProgressStepStart
  | ProgressStepEnd
  | ProgressDone
  | ProgressError

export interface ExampleQuestionRequest {
  language: string
}

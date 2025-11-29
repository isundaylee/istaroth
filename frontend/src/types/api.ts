/**
 * API request and response types for the frontend.
 *
 * These types are automatically generated from the OpenAPI specification.
 * DO NOT manually edit these types - they are kept in sync with the backend.
 *
 * To update types:
 * 1. Run: PYTHONPATH=. env/bin/python scripts/generate_openapi.py
 * 2. Run: npm run generate-types
 */

import type { components } from './api-generated'

// Export the schema types directly from the generated OpenAPI types
export type QueryRequest = components['schemas']['QueryRequest']
export type QueryResponse = components['schemas']['QueryResponse']
export type ModelsResponse = components['schemas']['ModelsResponse']
export type ConversationResponse = components['schemas']['ConversationResponse']
export type ExampleQuestionResponse = components['schemas']['ExampleQuestionResponse']
export type CitationResponse = components['schemas']['CitationResponse']

// Additional types that may not be in the OpenAPI spec but are used by the frontend
export interface ErrorResponse {
  error: string
}

export interface ExampleQuestionRequest {
  language: string
}

// Library API types (will be in generated types after OpenAPI spec regeneration)
export interface LibraryCategoriesResponse {
  categories: string[]
}

export interface LibraryFilesResponse {
  files: string[]
}

export interface LibraryFileResponse {
  category: string
  filename: string
  content: string
}

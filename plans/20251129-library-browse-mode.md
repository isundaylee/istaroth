# Library Browse Mode Implementation (Phased)

## Overview
Add a new browse mode to the web app that allows users to browse and read full text files organized by category. Implemented in 3 phases with testing/commits between each.

## Phase 1: Navigation Bar
**Goal**: Add navigation component to switch between Q&A and library pages

### Frontend Changes
- Create Navigation component (`frontend/src/components/Navigation.tsx`)
  - Links to home (`/`) and library (`/library`)
  - Include language switcher
- Add Navigation to QueryPage and ConversationPage
- Create placeholder LibraryPage component
- Add `/library` route to App.tsx

## Phase 2: Categories and File Listing
**Goal**: Show list of categories and files within selected category

### Backend Changes
- Add Library Router (`istaroth/services/backend/routers/library.py`)
  - `GET /api/library/categories?language={lang}` - List all categories
  - `GET /api/library/files/{category}?language={lang}` - List files in category
- Add Request/Response Models (`istaroth/services/backend/models.py`)
  - `LibraryCategoriesResponse` - List of category names
  - `LibraryFilesResponse` - List of filenames in a category
- Register router in `app.py`
- Get checkpoint path from `ISTAROTH_DOCUMENT_STORE_SET`
- Text files: `{checkpoint_path}/text/{language}/agd/{category}/*.txt`
- Categories discovered by scanning subdirectories

### Frontend Changes
- Update LibraryPage to show categories
- Add file listing view when category selected
- Add translations for categories and file listing

## Phase 3: Text Viewer
**Goal**: Display full text content in reading-friendly format

### Backend Changes
- Add endpoint: `GET /api/library/file/{category}/{filename}?language={lang}`
- Add `LibraryFileResponse` model

### Frontend Changes
- Add file viewer to LibraryPage
- Display full text content in reading-friendly format
- Add translations for text viewer

## Implementation Details
- Text directory: `{checkpoint_path}/text/{language}/agd/{category}/*.txt`
- Checkpoint path from `ISTAROTH_DOCUMENT_STORE_SET`
- Files listed alphabetically
- UTF-8 encoding
- Error handling (404 for missing files/categories)
- Language selection affects all endpoints

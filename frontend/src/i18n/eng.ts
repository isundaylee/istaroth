export const eng = {
  common: {
    loading: 'Loading...',
    error: 'Error',
    back: 'Back to Home',
    submit: 'Submit',
    copy: 'Copy',
    copied: 'Copied',
    copyFailed: 'Copy failed',
    shareLink: 'Copy Share Link',
    close: 'Close',
    expand: 'Expand',
    download: 'Download',
    unexpectedError: 'An unexpected error occurred'
  },

  meta: {
    title: 'Istaroth - Genshin Impact Knowledge Assistant',
    description: 'Explore the mysterious legends and profound lore of Teyvat. An intelligent knowledge base built from Genshin Impact game texts, ready to answer all your questions about characters, history, culture, and worldview.',
    githubLink: 'GitHub'
  },

  query: {
    title: 'Istaroth',
    placeholder: 'Enter your question about Genshin Impact lore...',
    exampleLoading: 'Loading example question...',
    submitButton: 'Ask',
    submitting: 'Answering',
    retrievalPresetLabel: 'Retrieval thoroughness',
    retrievalPresets: {
      fast: 'Focused',
      balanced: 'Balanced',
      thorough: 'Thorough'
    },
    modelSelectLabel: 'Model speed',
    // Each model carries a short `speed` label (shown alone in the collapsed
    // composer) and a full `name` (shown inside the open dropdown).
    models: {
      'gemini-3_1-flash-lite-preview': { speed: 'Ultra Fast', name: 'gemini-3.1-flash-lite-preview' },
      'zai-org_GLM-4_7-Flash': { speed: 'Fast', name: 'GLM-4.7-Flash' },
      'deepseek-ai_DeepSeek-V4-Flash': { speed: 'Fast', name: 'DeepSeek-V4-Flash' },
      'gemini-3-flash-preview:minimal': { speed: 'Fast', name: 'gemini-3-flash (minimal thinking)' },
      'gemini-3-flash-preview:high': { speed: 'Fast', name: 'gemini-3-flash (high thinking)' },
      'gpt-5-nano': { speed: 'Fast', name: 'gpt-5-nano' },
      'gpt-5-mini': { speed: 'Medium', name: 'gpt-5-mini' },
      'gemini-3_1-pro-preview': { speed: 'Slow', name: 'gemini-3.1-pro-preview' }
    },
    errors: {
      unknown: 'An unknown error occurred',
      noConnection: 'Unable to connect to server',
      modelsLoadFailed: 'Failed to load available models. Please refresh the page to try again'
    },
    progress: {
      normalizing: 'Normalizing query',
      augmenting: 'Generating queries',
      searching: 'Searching',
      generating: 'Generating response',
      extracting_proper_nouns: 'Extracting proper nouns'
    },
    hero: {
      figureAlt: 'Istaroth',
      greeting: 'Hello, Traveler! What would you like to know?',
      tryAsking: 'Try asking: ',
      thinking: 'Istaroth is thinking'
    }
  },

  conversation: {
    question: 'Question',
    askAnother: 'Ask another question',
    export: 'Export Image',
    exporting: 'Exporting...',
    metadata: {
      conversation: 'Conversation',
      time: 'Time',
      language: 'Language',
      model: 'Model',
      generationTime: 'Generation Time',
      seconds: 's',
      inputChars: 'input chars',
      chunks: 'chunks',
      files: 'files'
    },
    errors: {
      invalidId: 'Invalid conversation ID',
      emptyData: 'Server returned empty conversation data',
      loadFailed: 'Failed to load conversation',
      exportFailed: 'PNG export failed, please try again',
      notFound: 'Conversation content element not found'
    },
    exportImage: {
      alt: 'Exported conversation screenshot'
    }
  },

  notFound: {
    title: '404',
    heading: 'Page Not Found',
    message: 'Sorry, the page you are looking for does not exist.',
    backButton: 'Back to Home'
  },

  citation: {
    source: 'Source',
    loading: 'Loading...',
    notLoaded: 'Content not loaded',
    error: 'Error',
    networkError: 'Network error fetching citation',
    fetchFailed: 'Failed to fetch citation',
    loadingButton: 'Loading...',
    loadAllChunks: 'Load full text',
    enterFullscreen: 'Enter fullscreen',
    exitFullscreen: 'Exit fullscreen',
    close: 'Close',
    current: 'cited',
    list: {
      title: 'Cited Works'
    },
    openInLibrary: 'Open in library'
  },

  theme: {
    toggleDark: 'Switch to dark mode',
    toggleLight: 'Switch to light mode'
  },

  language: {
    toggle: 'Switch to Chinese'
  },

  navigation: {
    home: 'Q&A',
    library: 'Library'
  },

  history: {
    title: 'History',
    newQuestion: 'New question',
    today: 'Today',
    yesterday: 'Yesterday',
    empty: 'No conversations yet. Your past questions will appear here.',
    loadMore: 'Load more',
    errors: {
      loadFailed: 'Failed to load conversation history'
    }
  },

  keyboard: {
    title: 'Keyboard shortcuts',
    focusSearch: 'Focus search box',
    deselect: 'Blur the focused input',
    goQuery: 'Go to Q&A',
    goLibrary: 'Go to Library',
    citationFullscreen: 'Toggle fullscreen for the open citation popup',
    citationLoadContext: 'Load full context in the open citation popup',
    help: 'Toggle this help',
    close: 'Close'
  },

  footer: {
    checkpointVersion: 'Text Data Version',
    tagline: 'A knowledge base built from Genshin Impact texts'
  },

  library: {
    title: 'Library',
    frontDesk: {
      title: 'Teyvat Library',
      subtitle: 'The quests, books, character stories, and legends of Teyvat, gathered here.',
      openContents: 'Open contents',
      search: 'Search the archive',
      continueReading: 'Continue reading',
      matches: 'matches',
      noRecents: 'Recently read texts will appear here.'
    },
    search: {
      placeholder: 'Enter text to find related documents',
      submitButton: 'Search',
      submitting: 'Searching...',
      searchMode: 'Search mode',
      searchModeBm25: 'Keyword',
      searchModeSemantic: 'Semantic',
      noResults: 'No documents found',
      errors: {
        unknown: 'An unknown error occurred',
        noConnection: 'Failed to connect to server'
      }
    },
    backToFiles: 'Back to Files',
    versionBadge: '(Added in {version})',
    versionBadgeRange: '(Added across {version})',
    newBadge: 'NEW',
    errors: {
      loadFailed: 'Failed to load',
      unknown: 'An unknown error occurred',
      invalidCategory: 'Invalid category'
    },
    noFileName: 'Untitled',
    breadcrumbAriaLabel: 'Breadcrumb',
    filterPlaceholder: 'Filter by title...',
    noFilterResults: 'No documents match your filter',
    filterMoreHidden: 'more matches not shown',
    navMenu: 'Contents',
    selection: {
      keywordSearch: 'Keyword search',
      ask: 'Ask',
      searching: 'Searching...',
      noResults: 'No matching documents found',
      score: 'Score',
      openLibrarySearch: 'Search in the library',
      openConversation: 'Open saved conversation',
      errors: {
        searchFailed: 'Search failed',
        noConnection: 'Failed to connect to server'
      }
    }
  }
}

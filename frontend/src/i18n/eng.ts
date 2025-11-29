export const eng = {
  common: {
    loading: 'Loading...',
    error: 'Error',
    back: 'Back to Home',
    submit: 'Submit',
    copy: 'Copy',
    copied: 'Copied',
    copyFailed: 'Copy failed',
    close: 'Close',
    download: 'Download'
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
    submitting: 'Answering...',
    models: {
      'gemini-2_5-flash-lite': 'Ultra Fast (gemini-2.5-flash-lite)',
      'gemini-2_5-flash': 'Fast (gemini-2.5-flash)',
      'gpt-5-nano': 'Fast (gpt-5-nano)',
      'gpt-5-mini': 'Medium (gpt-5-mini)',
      'gemini-2_5-pro': 'Slow (gemini-2.5-pro)',
      'gemini-3-pro-preview': 'Slow (gemini-3-pro-preview)'
    },
    errors: {
      unknown: 'An unknown error occurred',
      noConnection: 'Unable to connect to server',
      modelsLoadFailed: 'Failed to load available models. Please refresh the page to try again'
    }
  },

  conversation: {
    question: 'Question',
    answer: 'Answer',
    shareLink: 'Copy Share Link',
    export: 'Export Image',
    exporting: 'Exporting...',
    metadata: {
      conversation: 'Conversation',
      time: 'Time',
      language: 'Language',
      model: 'Model',
      generationTime: 'Generation Time',
      seconds: 's'
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
    loadPrevious: '↑ Load Previous',
    loadNext: '↓ Load Next',
    loadChunk: 'Load Chunk',
    loadChunkUp: '↑ Load Chunk',
    loadChunkDown: '↓ Load Chunk',
    loadAllChunks: 'Load All Chunks',
    enterFullscreen: 'Enter fullscreen',
    exitFullscreen: 'Exit fullscreen',
    close: 'Close',
    chunk: 'Chunk',
    current: 'current',
    list: {
      title: 'Cited Works'
    }
  },

  navigation: {
    home: 'Q&A',
    library: 'Library'
  },

  library: {
    title: 'Library',
    placeholder: 'Library feature coming soon...',
    selectCategory: 'Select Category',
    backToCategories: 'Back to Categories',
    noFiles: 'No files in this category',
    categories: {
      artifact_sets: 'Artifact Sets',
      character_stories: 'Character Stories',
      material_types: 'Material Types',
      quest: 'Quests',
      readable: 'Readables',
      subtitles: 'Subtitles',
      talk_groups: 'Talk Groups',
      talks: 'Talks',
      voicelines: 'Voicelines'
    },
    errors: {
      loadFailed: 'Failed to load',
      unknown: 'An unknown error occurred'
    }
  }
}

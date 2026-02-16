export const chs = {
  common: {
    loading: '加载中...',
    error: '错误',
    back: '返回首页',
    submit: '提交',
    copy: '复制',
    copied: '已复制',
    copyFailed: '复制失败',
    close: '关闭',
    download: '下载',
    unexpectedError: '发生了意外错误'
  },

  meta: {
    title: '伊斯塔露 - 原神知识助手',
    description: '探索提瓦特大陆的神秘传说与深邃背景故事。基于原神游戏文本构建的智能知识库，为您解答关于角色、历史、文化和世界观的所有疑问。',
    githubLink: 'GitHub'
  },

  query: {
    title: '伊斯塔露',
    placeholder: '请输入关于原神背景故事的问题...',
    exampleLoading: '正在加载示例问题...',
    submitButton: '提问',
    submitting: '回答中...',
    models: {
      'gemini-2_5-flash-lite': '超快速 (gemini-2.5-flash-lite)',
      'gemini-2_5-flash': '快速 (gemini-2.5-flash)',
      'gpt-5-nano': '快速 (gpt-5-nano)',
      'gpt-5-mini': '中速 (gpt-5-mini)',
      'gemini-2_5-pro': '慢速 (gemini-2.5-pro)',
      'gemini-3-pro-preview': '慢速 (gemini-3-pro-preview)'
    },
    errors: {
      unknown: '发生了未知错误',
      noConnection: '无法连接到服务器',
      modelsLoadFailed: '无法加载可用模型列表，请刷新页面重试'
    }
  },

  conversation: {
    question: '问题',
    answer: '回答',
    shareLink: '复制分享链接',
    export: '导出图片',
    exporting: '导出中...',
    metadata: {
      conversation: '对话',
      time: '时间',
      language: '语言',
      model: '模型',
      generationTime: '生成时间',
      seconds: '秒'
    },
    errors: {
      invalidId: '无效的对话ID',
      emptyData: '服务器返回了空的对话数据',
      loadFailed: '无法加载对话',
      exportFailed: '导出PNG失败，请重试',
      notFound: '对话内容元素未找到'
    },
    exportImage: {
      alt: '导出的对话截图'
    }
  },

  notFound: {
    title: '404',
    heading: '页面未找到',
    message: '抱歉，您访问的页面不存在。',
    backButton: '返回首页'
  },

  citation: {
    source: '来源',
    loading: '加载中...',
    notLoaded: '内容未加载',
    error: '错误',
    networkError: '网络错误获取引用',
    fetchFailed: '获取引用失败',
    loadingButton: '载入中...',
    loadPrevious: '↑ 载入上一段',
    loadNext: '↓ 载入下一段',
    loadChunk: '载入段落',
    loadChunkUp: '↑ 载入段落',
    loadChunkDown: '↓ 载入段落',
    loadAllChunks: '载入全部段落',
    enterFullscreen: '进入全屏',
    exitFullscreen: '退出全屏',
    close: '关闭',
    chunk: '片段',
    current: '当前',
    list: {
      title: '引用文献'
    },
    openInLibrary: '在图书馆中打开'
  },

  navigation: {
    home: '问答',
    retrieve: '检索',
    library: '图书馆'
  },

  retrieve: {
    title: '关键词检索',
    placeholder: '输入文本以查找相关文档',
    submitButton: '搜索',
    submitting: '搜索中...',
    semantic: '语义搜索',
    searchModeBm25: '仅关键词',
    searchModeSemantic: '语义',
    noResults: '未找到相关文档',
    errors: {
      unknown: '发生未知错误',
      noConnection: '无法连接到服务器'
    }
  },

  footer: {
    checkpointVersion: '文本数据版本'
  },

  library: {
    title: '图书馆',
    placeholder: '图书馆功能即将推出...',
    selectCategory: '选择分类',
    backToCategories: '返回分类',
    backToFiles: '返回文件列表',
    noFiles: '该分类下没有文件',
    categories: {
      agd_artifact_set: '圣遗物套装',
      agd_book: '书籍',
      agd_weapon: '武器',
      agd_wings: '风之翼',
      agd_costume: '服装',
      agd_character_story: '角色故事',
      agd_material_type: '材料类型',
      agd_quest: '任务',
      agd_readable: '可读文本',
      agd_subtitle: '字幕',
      agd_talk_group: '对话组',
      agd_talk: '对话',
      agd_voiceline: '语音台词'
    },
    errors: {
      loadFailed: '加载失败',
      unknown: '发生未知错误',
      invalidCategory: '无效分类'
    },
    noFileName: '未命名',
    filterPlaceholder: '按标题筛选...',
    noFilterResults: '没有匹配的文档',
    previous: '上一篇',
    next: '下一篇'
  }
}

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
    download: '下载'
  },

  meta: {
    title: '伊斯塔露 - 原神知识助手',
    description: '探索提瓦特大陆的神秘传说与深邃背景故事。基于原神游戏文本构建的智能知识库，为您解答关于角色、历史、文化和世界观的所有疑问。'
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
      'gemini-2_5-pro': '慢速 (gemini-2.5-pro)'
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
    enterFullscreen: '进入全屏',
    exitFullscreen: '退出全屏',
    close: '关闭'
  }
}

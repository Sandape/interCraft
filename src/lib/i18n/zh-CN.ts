/** zh-CN — 简中 i18n bundle,集中管理用户可见文案。 */
export const zhCN = {
  interview: {
    restore: '面试已恢复，继续你的回答',
    setup: {
      resumeLabel: '使用简历',
      resumePlaceholder: '不使用简历',
      noResume: '暂无可用简历',
      createResumeCta: '前往创建',
    },
  },
  errorCoach: {
    starting: '正在启动强化辅导…',
    failed: '启动失败，请重试',
    timeout: '启动超时，请重试',
  },
  export: {
    empty: '简历内容为空，请先添加简历块',
    failed: '导出失败',
    unavailable: '导出服务暂不可用，请稍后重试',
    notFound: '导出服务未启动 (404)',
    unauthorized: '会话已过期，请重新登录',
    invalid: '导出参数无效',
  },
  login: {
    welcomeBack: '欢迎回来',
  },
  register: {
    createAccount: '创建账号',
  },
} as const

export type ZhCN = typeof zhCN

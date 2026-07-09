export const onePageMarkdown = `# 林溪 - AI 应用工程师

::: left
icon:phone 13800000000
icon:email linxi@example.com
:::

## 个人总结

5 年 AI 应用与全栈工程经验，专注 **RAG、Agent 工作流、企业知识库、评测体系**。

## 技能

- RAG / Agent / Prompt Engineering
- TypeScript / React / Vite / Playwright
`;

export const nearOnePageMarkdown = `# 林溪 - AI 应用工程师

::: left
icon:phone 13800000000
icon:email linxi@example.com
:::

## 工作经历

### 星环智能科技有限公司（2023.04 - 至今）

${Array.from({ length: 18 }, (_, i) => `- 项目成果 ${i + 1}：推动 AI 简历链路稳定落地，提升交付质量。`).join("\n")}

## 项目经历

### JD 定制化简历优化助手

${Array.from({ length: 8 }, (_, i) => `- 关键能力 ${i + 1}：支持差异对比、引用溯源和质量回归。`).join("\n")}
`;

export const infeasibleMarkdown = `# 林溪 - AI 应用工程师

## 大量经历

${Array.from({ length: 96 }, (_, i) => `- 详细经历 ${i + 1}：这是一条必须保留的简历内容，智能一页不得隐藏或删除。`).join("\n")}
`;

import { defaultResumeDataV2 } from "../../schema/defaults";
import type { ResumeDataV2 } from "../../schema/data";

export const formatLabMarkdown = `# 林溪 - Markdown 渲染测试

::: left
icon:phone 13800000000
icon:email linxi@example.com
:::

::: right
[icon:github https://github.com/example-linxi](https://github.com/example-linxi)
:::

## 文本格式

普通文本、*斜体文本*、**加粗文本**、***加粗斜体***、~~删除线文本~~、[普通链接](https://example.com)、\`内联代码\`。

## 表格格式

| 模块 | 职责 | 结果 |
| --- | --- | --- |
| JD 解析 | 抽取岗位关键词 | 准确率 88% |
`;

export function makeResumeV3Data(overrides: Partial<ResumeDataV2["metadata"]["markdown"]> = {}): ResumeDataV2 {
  return {
    ...defaultResumeDataV2,
    metadata: {
      ...defaultResumeDataV2.metadata,
      markdown: {
        ...defaultResumeDataV2.metadata.markdown,
        sourceMarkdown: formatLabMarkdown,
        ...overrides,
      },
    },
  };
}

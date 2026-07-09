import { describe, expect, it } from "vitest";
import { renderMarkdown } from "../index";

const fixture = `# 林溪

::: left
icon:phone 13800000000
icon:email linxi@example.com
:::

::: right
[icon:github GitHub](https://github.com/example-linxi)
:::

## 文本格式

普通文本、*斜体文本*、**加粗文本**、***加粗斜体***、~~删除线文本~~、[普通链接](https://example.com)、\`内联代码\`。

> 引用文本

---

- 一级无序项目
  - 二级缩进项目
- [x] 已完成任务项

1. 第一条

| 模块 | 职责 |
| --- | --- |
| JD 解析 | 抽取岗位关键词 |

![图片占位](https://placehold.co/80x40/png)
`;

describe("Muji-compatible Markdown dialect", () => {
  it("renders headings, containers, icons, lists, task-list literals, table, and image", () => {
    const result = renderMarkdown(fixture, {
      themeId: "muji-default-autumn",
      lineHeight: 19,
    });

    expect(result.html).toContain("<h1");
    expect(result.html).toContain("<h2");
    expect(result.html).toContain("lr-container");
    expect(result.html).toContain("13800000000");
    expect(result.html).toContain("GitHub");
    expect(result.html).toContain("<s>删除线文本</s>");
    expect(result.html).toContain("<code>内联代码</code>");
    expect(result.html).toContain("[x] 已完成任务项");
    expect(result.html).toContain("<table");
    expect(result.html).toContain('<img src="https://placehold.co/80x40/png"');
  });
});

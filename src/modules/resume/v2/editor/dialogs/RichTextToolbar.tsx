/**
 * RichTextToolbar — toolbar buttons for the Tiptap-based RichTextEditor.
 *
 * Provides formatting controls: bold, italic, heading, lists, link, etc.
 * The parent editor passes the editor instance and fullscreen toggle.
 * This file was missing from the repo and is recreated here as a
 * functional stub.
 */
import type { Editor } from "@tiptap/react";
import {
  Bold,
  Italic,
  Strikethrough,
  Code,
  Heading1,
  Heading2,
  List,
  ListOrdered,
  Quote,
  Link,
  Image,
  Fullscreen,
  Minus,
} from "lucide-react";

/** URL validation regex — http/https only (FR-065). */
export const LINK_ALLOWED = /^https?:\/\//i;

interface ToolbarProps {
  editor: Editor | null;
  isFullscreen: boolean;
  onToggleFullscreen: () => void;
  onError?: (msg: string) => void;
}

function ToolBtn({
  onClick,
  active,
  title,
  children,
}: {
  onClick: () => void;
  active?: boolean;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className={
        "inline-flex h-7 w-7 items-center justify-center rounded text-xs transition-colors " +
        (active
          ? "bg-primary-100 text-primary-700 dark:bg-primary-500/20 dark:text-primary-300"
          : "text-ink-2 hover:bg-surface-muted hover:text-ink-1 dark:hover:bg-dark-surface-muted")
      }
    >
      {children}
    </button>
  );
}

export function RichTextToolbar({
  editor,
  isFullscreen,
  onToggleFullscreen,
  onError,
}: ToolbarProps) {
  if (!editor) return null;

  return (
    <div
      className="flex flex-wrap items-center gap-0.5 border-b border-surface-border px-2 py-1.5"
      data-testid="rich-text-toolbar"
    >
      <ToolBtn
        title="加粗"
        active={editor.isActive("bold")}
        onClick={() => editor.chain().focus().toggleBold().run()}
      >
        <Bold className="h-3.5 w-3.5" />
      </ToolBtn>
      <ToolBtn
        title="斜体"
        active={editor.isActive("italic")}
        onClick={() => editor.chain().focus().toggleItalic().run()}
      >
        <Italic className="h-3.5 w-3.5" />
      </ToolBtn>
      <ToolBtn
        title="删除线"
        active={editor.isActive("strike")}
        onClick={() => editor.chain().focus().toggleStrike().run()}
      >
        <Strikethrough className="h-3.5 w-3.5" />
      </ToolBtn>
      <ToolBtn
        title="行内代码"
        active={editor.isActive("code")}
        onClick={() => editor.chain().focus().toggleCode().run()}
      >
        <Code className="h-3.5 w-3.5" />
      </ToolBtn>

      <span className="mx-0.5 h-4 w-px bg-surface-border" />

      <ToolBtn
        title="标题 1"
        active={editor.isActive("heading", { level: 1 })}
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
      >
        <Heading1 className="h-3.5 w-3.5" />
      </ToolBtn>
      <ToolBtn
        title="标题 2"
        active={editor.isActive("heading", { level: 2 })}
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
      >
        <Heading2 className="h-3.5 w-3.5" />
      </ToolBtn>

      <span className="mx-0.5 h-4 w-px bg-surface-border" />

      <ToolBtn
        title="无序列表"
        active={editor.isActive("bulletList")}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
      >
        <List className="h-3.5 w-3.5" />
      </ToolBtn>
      <ToolBtn
        title="有序列表"
        active={editor.isActive("orderedList")}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
      >
        <ListOrdered className="h-3.5 w-3.5" />
      </ToolBtn>
      <ToolBtn
        title="引用"
        active={editor.isActive("blockquote")}
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
      >
        <Quote className="h-3.5 w-3.5" />
      </ToolBtn>

      <span className="mx-0.5 h-4 w-px bg-surface-border" />

      <ToolBtn
        title="分隔线"
        active={false}
        onClick={() => editor.chain().focus().setHorizontalRule().run()}
      >
        <Minus className="h-3.5 w-3.5" />
      </ToolBtn>
      <ToolBtn
        title="插入链接"
        active={editor.isActive("link")}
        onClick={() => {
          const url = window.prompt("链接 URL (http/https):");
          if (!url) return;
          if (!LINK_ALLOWED.test(url)) {
            window.alert("只支持 http/https 链接");
            return;
          }
          editor.chain().focus().setLink({ href: url }).run();
        }}
      >
        <Link className="h-3.5 w-3.5" />
      </ToolBtn>
      <ToolBtn
        title="插入图片"
        active={false}
        onClick={() => {
          const url = window.prompt("图片 URL (http/https):");
          if (!url) return;
          if (!LINK_ALLOWED.test(url)) {
            onError?.("只支持 http/https 图片");
            return;
          }
          onError?.("当前版本暂未启用图片插入。");
        }}
      >
        <Image className="h-3.5 w-3.5" />
      </ToolBtn>

      <div className="ml-auto">
        <ToolBtn
          title={isFullscreen ? "退出全屏" : "全屏"}
          active={isFullscreen}
          onClick={onToggleFullscreen}
        >
          <Fullscreen className="h-3.5 w-3.5" />
        </ToolBtn>
      </div>
    </div>
  );
}

export default RichTextToolbar;

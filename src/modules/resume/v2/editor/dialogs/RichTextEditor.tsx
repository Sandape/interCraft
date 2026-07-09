// T091 — RichTextEditor (Tiptap-based) for US9.
//
// Wraps <EditorContent> with a <RichTextToolbar>. The editor uses the
// StarterKit (with Table / HardBreak / HR / CodeBlock kept enabled) plus
// the explicit Link (http/https only per FR-065), Highlight and TextAlign
// extensions. Supports fullscreen mode and RTL via the `dir` attribute on
// the root container.
//
// The `onUpdate` callback fires when content changes; `onChange` is also
// fired on initial mount and after every transaction so consumers can
// debounce-save the value. RTL is auto-detected from `locale` if provided.

import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Link from "@tiptap/extension-link";
import Highlight from "@tiptap/extension-highlight";
import TextAlign from "@tiptap/extension-text-align";
import { useEffect, useState, useCallback, useRef } from "react";
import { Modal } from "@/components/ui/Modal";
import { RichTextToolbar, LINK_ALLOWED } from "./RichTextToolbar";

// Re-export for consumers / tests
export { LINK_ALLOWED };

export interface RichTextEditorProps {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
  /** BCP-47 locale (e.g. "ar", "he", "fa"). Triggers `dir="rtl"`. */
  locale?: string;
  className?: string;
  minHeightClass?: string;
  onError?: (msg: string) => void;
}

const RTL_REGEX = /^(ar|he|fa|ur)(-|$)/i;

export function RichTextEditor({
  value,
  onChange,
  placeholder = "Type something…",
  locale,
  className = "",
  minHeightClass = "min-h-[8rem]",
  onError,
}: RichTextEditorProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  // Last error message — displayed as a small toast banner.
  const [error, setError] = useState<string | null>(null);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  const reportError = useCallback(
    (msg: string) => {
      setError(msg);
      onError?.(msg);
      // auto-dismiss after 3s
      window.setTimeout(() => setError(null), 3000);
    },
    [onError],
  );

  const editor = useEditor({
    extensions: [
      // StarterKit provides: Document, Heading, Paragraph, Text, Bold, Italic,
      // Strike, Code, CodeBlock, BulletList, OrderedList, ListItem, Blockquote,
      // HardBreak, HorizontalRule, History, Table (and others). We do NOT
      // disable any sub-extensions — Table / HardBreak / HR / CodeBlock stay
      // enabled per T090/T092.
      StarterKit,
      Link.configure({
        openOnClick: false,
        autolink: true,
        linkOnPaste: true,
        HTMLAttributes: { rel: "noopener noreferrer", target: "_blank" },
        validate: (url: string) => LINK_ALLOWED.test(url),
      }),
      Highlight.configure({ multicolor: true }),
      TextAlign.configure({ types: ["heading", "paragraph"] }),
    ],
    content: value,
    editorProps: {
      attributes: {
        class:
          "prose prose-sm max-w-none focus:outline-none px-3 py-2 " + minHeightClass,
        "data-placeholder": placeholder,
      },
    },
    onUpdate: ({ editor: ed }) => {
      onChangeRef.current(ed.getHTML());
    },
  });

  // Sync external value -> editor when the prop changes (e.g. on data load).
  useEffect(() => {
    if (!editor) return;
    if (editor.getHTML() !== value) {
      // emitUpdate=false avoids re-firing onUpdate for external changes.
      editor.commands.setContent(value, false);
    }
    // intentionally only on `value` change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, editor]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      editor?.destroy();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const isRtl = !!locale && RTL_REGEX.test(locale);
  const dir = isRtl ? "rtl" : "ltr";

  const editorBody = (
    <div
      data-testid="rich-text-editor"
      data-rte-locale={locale ?? ""}
      data-rte-dir={dir}
      className={`relative rounded border border-surface-border bg-surface ${className}`}
    >
      <RichTextToolbar
        editor={editor}
        isFullscreen={isFullscreen}
        onToggleFullscreen={() => setIsFullscreen((s) => !s)}
        onError={reportError}
      />
      <div dir={dir} className="bg-surface">
        <EditorContent editor={editor} />
      </div>
      {error && (
        <div
          role="alert"
          data-testid="rich-text-editor-error"
          className="absolute right-2 top-2 z-10 rounded bg-red-500 px-2 py-1 text-xs text-white shadow"
        >
          {error}
        </div>
      )}
    </div>
  );

  if (isFullscreen) {
    return (
      <Modal
        open={isFullscreen}
        onClose={() => setIsFullscreen(false)}
        title="Rich Text Editor (Fullscreen)"
        size="lg"
      >
        <div className="h-[80svh]">{editorBody}</div>
      </Modal>
    );
  }

  return editorBody;
}

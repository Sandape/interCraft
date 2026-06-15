import { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'
import { getStyleById, DEFAULT_STYLE_ID } from '@/lib/resume-styles'

interface ResumePreviewProps {
  markdown: string
  styleId?: string
  className?: string
}

/** Sections that belong in the sidebar for two-column layouts */
const SIDEBAR_SECTIONS = ['个人简介', '简介', 'summary', '技能', 'skills', '教育背景', '教育', 'education']

export default function ResumePreview({
  markdown,
  styleId = DEFAULT_STYLE_ID,
  className = '',
}: ResumePreviewProps) {
  const style = useMemo(() => getStyleById(styleId) ?? getStyleById(DEFAULT_STYLE_ID)!, [styleId])

  const renderContent = (md: string) => (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeRaw]}
      components={{
        h1: ({ children, ...props }) => (
          <h1 className="resume-name" {...props}>{children}</h1>
        ),
        h2: ({ children, ...props }) => (
          <div className="resume-section">
            <h2 {...props}>{children}</h2>
          </div>
        ),
        h3: ({ children, ...props }) => (
          <div className="resume-section">
            <h3 {...props}>{children}</h3>
          </div>
        ),
        p: ({ children, ...props }) => {
          const text = typeof children === 'string' ? children : ''
          if (text && /[·@]/.test(text) && text.length < 100) {
            return <p className="resume-contact" {...props}>{children}</p>
          }
          return <p {...props}>{children}</p>
        },
        em: ({ children, ...props }) => {
          const text = typeof children === 'string' ? children : ''
          if (text) {
            return <span className="meta-line" {...props}>{children}</span>
          }
          return <em {...props}>{children}</em>
        },
        ul: ({ children, ...props }) => (
          <ul className="resume-section" {...props}>{children}</ul>
        ),
      }}
    >
      {md}
    </ReactMarkdown>
  )

  const isEmpty = !markdown?.trim()

  // Split markdown into sidebar + main sections for two-column layout
  const { sidebarMd, mainMd } = useMemo(() => {
    if (isEmpty || style.layoutType !== 'two-column') return { sidebarMd: '', mainMd: '' }

    const lines = markdown.split('\n')
    const sections: { heading: string; content: string[] }[] = []
    let currentHeading = ''
    let currentContent: string[] = []

    for (const line of lines) {
      if (/^##\s/.test(line)) {
        if (currentHeading) {
          sections.push({ heading: currentHeading, content: currentContent })
        }
        currentHeading = line.replace(/^##\s+/, '').trim()
        currentContent = []
      } else {
        currentContent.push(line)
      }
    }
    if (currentHeading) {
      sections.push({ heading: currentHeading, content: currentContent })
    }

    // Everything before the first H2 is the "header" (name + contact)
    let headerEndIdx = 0
    for (let i = 0; i < lines.length; i++) {
      if (/^##\s/.test(lines[i])) {
        headerEndIdx = i
        break
      }
    }

    const headerLines = lines.slice(0, headerEndIdx)
    const sidebarSections: string[] = []
    const mainSections: string[] = []

    for (const section of sections) {
      const headingLower = section.heading.toLowerCase()
      const isSidebar = SIDEBAR_SECTIONS.some((k) =>
        headingLower.includes(k.toLowerCase()),
      )
      const sectionText = `## ${section.heading}\n${section.content.join('\n')}`
      if (isSidebar) {
        sidebarSections.push(sectionText)
      } else {
        mainSections.push(sectionText)
      }
    }

    return {
      sidebarMd: headerLines.join('\n') + '\n' + sidebarSections.join('\n'),
      mainMd: mainSections.join('\n'),
    }
  }, [markdown, isEmpty, style.layoutType])

  return (
    <div className={`resume-preview-container overflow-auto h-full bg-ink-4/5 ${className}`}>
      {isEmpty ? (
        <div className={`${style.cssClass} flex items-center justify-center`}>
          <div className="text-ink-muted text-sm text-center py-20">
            {style.id === 'editorial' ? (
              <span style={{ fontFamily: 'Georgia, serif' }}>
                预览区域 — 在左侧编辑器中输入 Markdown 内容
              </span>
            ) : (
              <>预览区域 — 在左侧编辑器中输入 Markdown 内容</>
            )}
          </div>
        </div>
      ) : style.layoutType === 'two-column' ? (
        <div className={style.cssClass}>
          {(sidebarMd.trim() || mainMd.trim()) ? (
            <>
              <div className="resume-sidebar">{renderContent(sidebarMd)}</div>
              <div className="resume-main">{renderContent(mainMd)}</div>
            </>
          ) : (
            renderContent(markdown)
          )}
        </div>
      ) : (
        <div className={style.cssClass}>{renderContent(markdown)}</div>
      )}
    </div>
  )
}

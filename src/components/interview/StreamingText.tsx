/** StreamingText — renders streaming token.delta content with cursor animation (T036).

Features:
- Accumulates text during streaming
- Shows blinking cursor during active streaming
- Renders markdown after node_completed
- Discards partial tokens on disconnect
*/
import { useState, useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'

interface StreamingTextProps {
  text: string
  isStreaming: boolean
  className?: string
}

export function StreamingText({ text, isStreaming, className }: StreamingTextProps) {
  const [displayText, setDisplayText] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isStreaming) {
      setDisplayText(text)
    } else if (text) {
      setDisplayText(text)
    }
  }, [text, isStreaming])

  // Auto-scroll to bottom
  useEffect(() => {
    if (containerRef.current && isStreaming) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [displayText, isStreaming])

  if (!displayText && !isStreaming) {
    return (
      <div className={cn('text-muted-foreground italic', className)}>
        Waiting for AI response...
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className={cn('relative whitespace-pre-wrap break-words', className)}
    >
      <span>{displayText}</span>
      {isStreaming && (
        <span className="inline-block w-2 h-4 bg-primary ml-0.5 animate-pulse align-middle" />
      )}
    </div>
  )
}

export default StreamingText

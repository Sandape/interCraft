/**
 * Color picker — react-color ChromePicker integrated with theme --bg variable.
 * Spec 027 US3. Ported from 木及简历 (D:\Project\react-resume-site\src\pages\ColorPicker.tsx).
 */
import { useEffect, useRef, useState } from 'react'
import { ChromePicker } from 'react-color'
import { Droplet } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { applyColor } from '@/modules/resume/themes'
import { cn } from '@/lib/utils'

interface ColorPickerProps {
  currentColor: string
  onColorChange: (hex: string) => void | Promise<void>
  className?: string
}

export default function ColorPicker({
  currentColor,
  onColorChange,
  className = '',
}: ColorPickerProps) {
  const [open, setOpen] = useState(false)
  const wrapperRef = useRef<HTMLDivElement>(null)

  // Outside-click handler
  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('click', handleClick)
    return () => document.removeEventListener('click', handleClick)
  }, [open])

  async function handleChange(hex: string) {
    applyColor(hex)
    await onColorChange(hex)
  }

  return (
    <div ref={wrapperRef} className={cn('relative', className)}>
      <Button
        variant="ghost"
        leftIcon={
          <div
            className="h-3.5 w-3.5 rounded-sm border border-surface-border"
            style={{ background: currentColor }}
          />
        }
        onClick={() => setOpen((v) => !v)}
        data-testid="color-picker-button"
      >
        颜色
      </Button>
      {open && (
        <div
          className="absolute right-0 top-full mt-1 z-50 shadow-lg"
          data-testid="color-picker-panel"
        >
          <ChromePicker
            color={currentColor}
            onChange={(color) => {
              // Live preview during drag (no debounce)
              applyColor(color.hex)
            }}
            onChangeComplete={(color) => {
              void handleChange(color.hex)
            }}
            disableAlpha
          />
        </div>
      )}
    </div>
  )
}

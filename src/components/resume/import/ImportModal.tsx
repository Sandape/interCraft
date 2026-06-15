import { useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload, AlertTriangle, FileText, Loader2 } from 'lucide-react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useCreateBranch } from '@/hooks/mutations/useBranchMutations'
import { getResumeBlockRepository } from '@/repositories/types'
import {
  validateMarkdownFile,
  readMarkdownFile,
  parseMarkdownImport,
  type ImportResult,
} from '@/lib/markdown-parser'
import { cn } from '@/lib/utils'

interface ImportModalProps {
  open: boolean
  onClose: () => void
}

export default function ImportModal({ open, onClose }: ImportModalProps) {
  const navigate = useNavigate()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const createBranch = useCreateBranch()

  const [file, setFile] = useState<File | null>(null)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [branchName, setBranchName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [step, setStep] = useState<'select' | 'preview'>('select')
  const [importing, setImporting] = useState(false)
  const [importProgress, setImportProgress] = useState('')

  function resetState() {
    setFile(null)
    setImportResult(null)
    setBranchName('')
    setError(null)
    setStep('select')
    setImporting(false)
    setImportProgress('')
  }

  const handleClose = useCallback(() => {
    resetState()
    onClose()
  }, [onClose])

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0]
    if (!selected) return

    setError(null)

    const validationError = validateMarkdownFile(selected)
    if (validationError) {
      setError(validationError.message)
      return
    }

    setFile(selected)
    readMarkdownFile(selected)
      .then((content) => {
        const result = parseMarkdownImport(content, selected.name)
        setImportResult(result)
        setBranchName(result.suggestedName)
        setStep('preview')
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : '文件读取失败'
        setError(msg)
      })
  }

  async function handleImport() {
    if (!importResult || !branchName.trim()) return

    setImporting(true)
    setError(null)

    try {
      setImportProgress('正在创建分支…')
      const branch = await new Promise<any>((resolve, reject) => {
        createBranch.mutate(
          {
            name: branchName.trim(),
            company: null,
            position: null,
            parent_id: null,
          },
          {
            onSuccess: (data) => resolve(data),
            onError: (err) => reject(err),
          },
        )
      })

      const repo = getResumeBlockRepository()
      setImportProgress(`正在导入 ${importResult.blocks.length} 个模块…`)

      for (let i = 0; i < importResult.blocks.length; i++) {
        await repo.create(branch.id, importResult.blocks[i])
        setImportProgress(`已导入 ${i + 1}/${importResult.blocks.length} 个模块…`)
      }

      handleClose()
      navigate(`/resume/${branch.id}`)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '导入失败'
      setError(msg)
      setImporting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="导入 Markdown 简历"
      description="选择一份 .md 文件，系统将解析内容并创建新的简历分支"
      size="md"
      footer={
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={handleClose} disabled={importing}>
            取消
          </Button>
          {step === 'preview' && (
            <Button
              variant="primary"
              disabled={!branchName.trim() || importing}
              onClick={handleImport}
            >
              {importing ? '导入中…' : '开始导入'}
            </Button>
          )}
        </div>
      }
    >
      <div className="space-y-3">
        {/* File picker area */}
        <div
          className={cn(
            'border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors',
            error
              ? 'border-red-300 dark:border-red-700 bg-red-50 dark:bg-red-900/10'
              : file
                ? 'border-brand-300 dark:border-brand-700 bg-brand-50 dark:bg-brand-900/10'
                : 'border-surface-border dark:border-dark-surface-border hover:border-brand-400 hover:bg-brand-50/50 dark:hover:bg-brand-900/5',
          )}
          onClick={() => fileInputRef.current?.click()}
        >
          {importing ? (
            <div className="flex flex-col items-center gap-2">
              <Loader2 className="h-6 w-6 text-brand-500 animate-spin" />
              <p className="text-sm text-ink-2">{importProgress}</p>
            </div>
          ) : file && importResult ? (
            <div className="flex flex-col items-center gap-1">
              <FileText className="h-6 w-6 text-brand-500" />
              <p className="text-sm font-medium text-ink-1">{file.name}</p>
              <p className="text-2xs text-ink-3">
                {(file.size / 1024).toFixed(1)} KB · {importResult.blocks.length} 个模块
              </p>
              {importResult.warnings.length > 0 && (
                <div className="mt-2 flex items-start gap-1.5 text-2xs text-amber-600 bg-amber-50 dark:bg-amber-900/20 rounded px-2 py-1.5 text-left">
                  <AlertTriangle className="h-3 w-3 flex-shrink-0 mt-px" />
                  <span>{importResult.warnings[0]}</span>
                </div>
              )}
            </div>
          ) : error ? (
            <div className="flex flex-col items-center gap-1">
              <AlertTriangle className="h-6 w-6 text-red-500" />
              <p className="text-sm text-red-600">{error}</p>
              <p className="text-2xs text-ink-3 mt-1">点击重新选择文件</p>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-1">
              <Upload className="h-6 w-6 text-ink-muted" />
              <p className="text-sm text-ink-2">点击选择 Markdown 文件</p>
              <p className="text-2xs text-ink-3">仅支持 .md 格式，大小不超过 100KB</p>
            </div>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".md,.markdown"
            className="hidden"
            onChange={handleFileChange}
            disabled={importing}
          />
        </div>

        {/* Branch name input (shown after file parsed) */}
        {step === 'preview' && importResult && !importing && (
          <div>
            <label className="block text-xs font-medium text-ink-2 mb-1.5">
              分支名称
            </label>
            <Input
              value={branchName}
              onChange={(e) => setBranchName(e.target.value)}
              placeholder="请输入分支名称"
              autoFocus
            />
            {importResult.blocks.length > 0 && (
              <p className="text-2xs text-ink-3 mt-1.5">
                将创建 {importResult.blocks.length} 个模块：
                {importResult.blocks.map((b, i) => (
                  <span key={i} className="ml-1 inline-block bg-surface-muted dark:bg-dark-surface-muted rounded px-1 py-px">
                    {b.type}
                  </span>
                ))}
              </p>
            )}
          </div>
        )}
      </div>
    </Modal>
  )
}

import { CheckCircle2, Circle, Trash2 } from 'lucide-react'
import { TaskStatusChip } from './TaskStatusChip'
import type { Task } from '@/repositories/TaskRepository'

const STATUS_ICON: Record<string, React.ReactNode> = {
  todo: <Circle className="h-4 w-4 text-ink-muted" />,
  doing: <Circle className="h-4 w-4 text-brand-500" />,
  done: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
}

export function TaskList({
  tasks,
  onStatusChange,
  onDelete,
}: {
  tasks: Task[]
  onStatusChange?: (id: string, status: string) => void
  onDelete?: (id: string) => void
}) {
  if (tasks.length === 0) {
    return <p className="text-xs text-ink-3 py-4 text-center">暂无任务</p>
  }

  return (
    <div className="divide-y divide-surface-border dark:divide-dark-surface-border">
      {tasks.map((task) => (
        <div key={task.id} className="flex items-center gap-3 py-2.5 group">
          <button
            className="flex-shrink-0 cursor-pointer hover:opacity-80"
            onClick={() => {
              const next = task.status === 'todo' ? 'doing' : task.status === 'doing' ? 'done' : 'todo'
              onStatusChange?.(task.id, next)
            }}
            title="切换状态"
          >
            {STATUS_ICON[task.status] ?? STATUS_ICON.todo}
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm text-ink-1 truncate">{task.title}</span>
              <TaskStatusChip status={task.status} />
            </div>
            {task.description_md && (
              <p className="text-xs text-ink-3 mt-0.5 line-clamp-1">{task.description_md}</p>
            )}
          </div>
          {onDelete && (
            <button
              onClick={() => onDelete(task.id)}
              className="p-1 rounded opacity-0 group-hover:opacity-100 text-ink-3 hover:text-red-500 transition-all"
              title="删除"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      ))}
    </div>
  )
}

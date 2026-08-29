import React from 'react'

export interface ProgressBarProps {
  completed: number
  total: number
  variant?: 'blue' | 'purple' | 'emerald' | 'amber' | 'rose'
  height?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
  label?: string
  className?: string
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  completed,
  total,
  variant = 'blue',
  height = 'md',
  showLabel = false,
  label,
  className = '',
}) => {
  const percentage = total > 0 ? Math.min(100, Math.max(0, (completed / total) * 100)) : 0

  const variantClasses = {
    blue: 'bg-blue-600 dark:bg-blue-500',
    purple: 'bg-purple-600 dark:bg-purple-500',
    emerald: 'bg-emerald-600 dark:bg-emerald-500',
    amber: 'bg-amber-500 dark:bg-amber-400',
    rose: 'bg-rose-600 dark:bg-rose-500',
  }

  const heightClasses = {
    sm: 'h-1.5',
    md: 'h-2',
    lg: 'h-3',
  }

  return (
    <div className={`w-full ${className}`}>
      {showLabel && (
        <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400 mb-1">
          <span>{label || 'Progress'}</span>
          <span className="font-mono">{completed} / {total} ({Math.round(percentage)}%)</span>
        </div>
      )}
      <div className={`w-full ${heightClasses[height]} bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden`}>
        <div
          className={`h-full ${variantClasses[variant]} transition-all duration-300 rounded-full`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  )
}
